import json
import logging
import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

from .models import Document, DocumentChunk, ChatMessage, StudyMaterial, QuizAttempt
from .forms import DocumentUploadForm
from .rag.extractor import extract_and_clean_document
from .rag.chunker import chunk_document_pages
from .rag.embeddings import get_embedding_generator
from .rag.vector_store import FaissVectorStore
from .rag.retriever import DocumentRetriever
from .rag.generator import RagGenerator
from .rag.study_generator import StudyMaterialGenerator
from .rag.rate_limiter import is_rate_limit_error, RateLimitExceededError

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def index_view(request):
    """
    Renders the responsive single-page RAG interface.
    Passes existing documents and upload form.
    """
    documents = Document.objects.all().order_by('-uploaded_at')
    active_doc_id = request.GET.get('doc') or request.session.get('active_doc_id')
    
    active_document = None
    if active_doc_id:
        active_document = documents.filter(id=active_doc_id).first()
    if not active_document and documents.exists():
        active_document = documents.first()

    form = DocumentUploadForm()

    context = {
        'documents': documents,
        'active_document': active_document,
        'form': form,
        'gemini_model': getattr(settings, 'GEMINI_GENERATION_MODEL', 'gemini-3.5-flash-lite'),
        'embedding_model': getattr(settings, 'GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001'),
        'chunk_size': getattr(settings, 'CHUNK_SIZE', 800),
        'chunk_overlap': getattr(settings, 'CHUNK_OVERLAP', 150),
        'top_k': getattr(settings, 'TOP_K_CHUNKS', 4),
        'has_api_key': bool(getattr(settings, 'GEMINI_API_KEY', '')),
    }
    return render(request, 'rag_assistant/index.html', context)


@require_POST
def upload_document_view(request):
    """
    Handles PDF/TXT document upload via AJAX.
    Extracts text, splits into overlapping chunks, generates embeddings,
    and indexes them into a document-scoped FAISS vector store.
    """
    form = DocumentUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = [err for error_list in form.errors.values() for err in error_list]
        return JsonResponse({'success': False, 'error': " ".join(errors)}, status=400)

    uploaded_file = form.cleaned_data['file']
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower().lstrip('.')

    # 1. Create Document model instance
    doc = Document.objects.create(
        file=uploaded_file,
        original_filename=filename,
        file_type=ext,
        file_size_bytes=uploaded_file.size,
    )

    try:
        # 2. Extract and clean raw document text
        pages_data, total_pages = extract_and_clean_document(doc.file.path, ext)
        doc.total_pages = total_pages

        # 3. Split into overlapping chunks
        chunk_size = getattr(settings, 'CHUNK_SIZE', 800)
        chunk_overlap = getattr(settings, 'CHUNK_OVERLAP', 150)
        chunks_data = chunk_document_pages(
            pages_data,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        if not chunks_data:
            doc.delete()
            return JsonResponse({
                'success': False,
                'error': "No meaningful text could be extracted or chunked from the file."
            }, status=400)

        # 4. Bulk save chunks to Django Database
        chunk_objects = [
            DocumentChunk(
                document=doc,
                chunk_index=item['chunk_index'],
                content=item['content'],
                page_number=item['page_number'],
            )
            for item in chunks_data
        ]
        DocumentChunk.objects.bulk_create(chunk_objects)

        # 5. Generate embeddings for all chunks via Gemini API
        embedding_generator = get_embedding_generator()
        chunk_texts = [item['content'] for item in chunks_data]
        embeddings = embedding_generator.embed_texts(chunk_texts)

        # 6. Build and persist document-scoped FAISS vector index
        vector_store = FaissVectorStore(dimension=embeddings.shape[1])
        index_path = doc.get_index_path()
        vector_store.create_and_save_index(embeddings, index_path)

        # 7. Finalize document record
        doc.total_chunks = len(chunks_data)
        doc.index_filename = f"{doc.id}.faiss"
        doc.save(update_fields=['total_chunks', 'total_pages', 'index_filename'])

        # Store active document in session
        request.session['active_doc_id'] = str(doc.id)

        return JsonResponse({
            'success': True,
            'message': f"Document '{filename}' indexed successfully into {len(chunks_data)} chunks!",
            'document': {
                'id': str(doc.id),
                'filename': doc.original_filename,
                'file_type': doc.file_type.upper(),
                'size': doc.formatted_size,
                'total_chunks': doc.total_chunks,
                'total_pages': doc.total_pages,
            }
        })

    except ValueError as e:
        # Document validation / extraction error (corrupted, password-protected, unreadable)
        doc.delete()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except RateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded while indexing document: {e}")
        doc.delete()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=429)
    except Exception as e:
        logger.exception("Error during document processing and indexing")
        # Cleanup incomplete document and files
        doc.delete()
        if is_rate_limit_error(e):
            return JsonResponse({
                'success': False,
                'error': (
                    "Gemini API rate limit reached (Free Tier limit: 100 requests/minute). "
                    "Please wait about 30 seconds before uploading again."
                )
            }, status=429)
        return JsonResponse({
            'success': False,
            'error': f"Processing failed: {str(e)}"
        }, status=500)


@require_POST
def query_document_view(request):
    """
    RAG Pipeline Endpoint:
    1. Validates document and query
    2. Embeds query and performs FAISS vector similarity search (real retrieval)
    3. Conditioned on retrieved chunks, invokes Gemini API with grounding system prompt
    4. Returns grounded answer alongside exact source passages
    """
    # Parse payload (JSON or form-data)
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body.'}, status=400)
        doc_id = data.get('document_id')
        query = data.get('query', '').strip()
    else:
        doc_id = request.POST.get('document_id')
        query = request.POST.get('query', '').strip()

    if not doc_id:
        return JsonResponse({'success': False, 'error': 'Document ID is required.'}, status=400)
    if not query:
        return JsonResponse({'success': False, 'error': 'Please enter a question to ask.'}, status=400)

    # Fetch document
    try:
        document = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found.'}, status=404)

    try:
        # Step 0: Assemble conversation history to support multi-turn follow-ups & pronoun resolution
        recent_messages = list(document.chat_messages.order_by('-created_at')[:8])
        recent_messages.reverse()
        conversation_history = []
        for msg in recent_messages:
            conversation_history.append({'role': 'user', 'content': msg.question})
            conversation_history.append({'role': 'assistant', 'content': msg.answer})

        retriever = DocumentRetriever()

        # Context-aware query formulation for vector retrieval if this is a follow-up
        retrieval_query = query
        is_doc_level = retriever.is_document_level_query(query)

        if not is_doc_level:
            follow_up_cues = {
                'it', 'its', 'they', 'them', 'their', 'this', 'that', 'these', 'those',
                'he', 'she', 'the previous', 'above', 'why', 'how', 'explain', 'tell me more',
                'elaborate', 'second', 'third', 'first', 'last', 'step', 'difference', 'compare',
                'what about', 'example'
            }
            words = set(query.lower().replace('?', ' ').replace('.', ' ').split())
            if (len(words) <= 6 or bool(words & follow_up_cues)) and recent_messages:
                last_user_q = recent_messages[-1].question
                retrieval_query = f"{last_user_q} {query}"

        # Step 1: Real Retrieval (Embed query -> search FAISS -> fetch top-k chunks)
        sources, is_confident, top_score = retriever.retrieve(document, retrieval_query)

        # Step 2: Augment Prompt & Generate Answer with Gemini
        generator = RagGenerator()
        generation_result = generator.generate_answer(
            query=query,
            sources=sources,
            is_confident=is_confident,
            top_score=top_score,
            conversation_history=conversation_history,
            document_title=document.original_filename
        )

        # Step 3: Persist chat interaction
        chat_msg = ChatMessage.objects.create(
            document=document,
            question=query,
            answer=generation_result['answer'],
            is_grounded=generation_result['is_grounded'],
            retrieved_sources=generation_result['sources']
        )

        return JsonResponse({
            'success': True,
            'message_id': str(chat_msg.id),
            'question': query,
            'answer': generation_result['answer'],
            'sources': generation_result['sources'],
            'is_grounded': generation_result['is_grounded'],
            'is_general_knowledge': generation_result.get('is_general_knowledge', False),
            'top_score': generation_result['top_score'],
        })

    except Exception as e:
        logger.exception("Error during RAG retrieval and generation")
        return JsonResponse({
            'success': False,
            'error': f"Query failed: {str(e)}"
        }, status=500)


@require_GET
def document_history_view(request, doc_id):
    """
    Returns previous chat messages for the selected document.
    """
    document = get_object_or_404(Document, id=doc_id)
    messages = document.chat_messages.all().order_by('created_at')

    data = [
        {
            'id': str(m.id),
            'question': m.question,
            'answer': m.answer,
            'is_grounded': m.is_grounded,
            'sources': m.retrieved_sources,
            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M'),
        }
        for m in messages
    ]
    return JsonResponse({'success': True, 'history': data})


@require_POST
def delete_document_view(request, doc_id):
    """
    Deletes an uploaded document, its chunks, and its FAISS index file.
    """
    document = get_object_or_404(Document, id=doc_id)
    filename = document.original_filename
    document.delete()

    if request.session.get('active_doc_id') == str(doc_id):
        request.session.pop('active_doc_id', None)

    return JsonResponse({
        'success': True,
        'message': f"Document '{filename}' and associated vector index were removed."
    })


@require_GET
def document_list_view(request):
    """
    Returns current list of indexed documents.
    """
    docs = Document.objects.all().order_by('-uploaded_at')
    return JsonResponse({
        'success': True,
        'documents': [
            {
                'id': str(d.id),
                'filename': d.original_filename,
                'file_type': d.file_type.upper(),
                'size': d.formatted_size,
                'total_chunks': d.total_chunks,
                'total_pages': d.total_pages,
                'uploaded_at': d.uploaded_at.strftime('%b %d, %Y %H:%M'),
            }
            for d in docs
        ]
    })


@require_GET
def get_study_materials_view(request, doc_id):
    """
    Returns existing cached study materials (flashcards, short notes,
    important topics, and quiz) for the specified document.
    """
    document = get_object_or_404(Document, id=doc_id)
    try:
        material = document.study_material
        if not (material.flashcards or material.quiz or material.short_notes):
            return JsonResponse({'success': True, 'exists': False})

        return JsonResponse({
            'success': True,
            'exists': True,
            'flashcards': material.flashcards,
            'short_notes': material.short_notes,
            'important_topics': material.important_topics,
            'quiz': material.quiz,
            'updated_at': material.updated_at.strftime('%b %d, %Y %H:%M'),
        })
    except StudyMaterial.DoesNotExist:
        return JsonResponse({'success': True, 'exists': False})


@require_POST
def generate_study_materials_view(request, doc_id):
    """
    Triggers Gemini to extract and synthesize Flashcards, Short Notes,
    Important Topics, and Quiz test from document content with customizable counts.
    """
    document = get_object_or_404(Document, id=doc_id)
    force = request.POST.get('force', 'false').lower() == 'true'
    flashcard_count = int(request.POST.get('flashcard_count', 10))
    quiz_count = int(request.POST.get('quiz_count', 5))
    feature = request.POST.get('feature', 'all')

    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            force = body.get('force', force)
            flashcard_count = int(body.get('flashcard_count', flashcard_count))
            quiz_count = int(body.get('quiz_count', quiz_count))
            feature = body.get('feature', feature)
        except Exception:
            pass

    try:
        generator = StudyMaterialGenerator()
        result = generator.get_or_generate_study_material(
            document,
            force_regenerate=force,
            flashcard_count=flashcard_count,
            quiz_count=quiz_count,
            feature=feature
        )
        return JsonResponse(result)
    except Exception as e:
        logger.exception("Failed to generate study materials")
        if is_rate_limit_error(e):
            return JsonResponse({
                'success': False,
                'error': "Gemini API rate limit reached (Free Tier limit: 100 requests/minute). Please wait 30 seconds and try again."
            }, status=429)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET", "POST"])
def generate_quiz_view(request, doc_id):
    """
    Generates fresh, non-repeating quiz questions tailored to the requested
    question count, difficulty level, and target topic.
    Avoids recent questions tracked in StudyMaterial.seen_quiz_questions.
    """
    document = get_object_or_404(Document, id=doc_id)

    count = 5
    difficulty = 'mixed'
    topic = 'all'

    if request.method == 'POST':
        if request.content_type == 'application/json':
            try:
                body = json.loads(request.body)
                count = int(body.get('count', count))
                difficulty = body.get('difficulty', difficulty)
                topic = body.get('topic', topic)
            except Exception:
                pass
        else:
            count = int(request.POST.get('count', count))
            difficulty = request.POST.get('difficulty', difficulty)
            topic = request.POST.get('topic', topic)
    else:
        count = int(request.GET.get('count', count))
        difficulty = request.GET.get('difficulty', difficulty)
        topic = request.GET.get('topic', topic)

    try:
        study_mat, _ = StudyMaterial.objects.get_or_create(document=document)
        avoid_questions = list(study_mat.seen_quiz_questions or [])

        generator = StudyMaterialGenerator()
        fresh_questions = generator.generate_quiz(
            document=document,
            count=count,
            difficulty=difficulty,
            topic=topic,
            avoid_questions=avoid_questions
        )

        new_q_texts = [q['question'] for q in fresh_questions if 'question' in q]
        updated_seen = (avoid_questions + new_q_texts)[-60:]
        study_mat.seen_quiz_questions = updated_seen
        study_mat.quiz = fresh_questions
        study_mat.save(update_fields=['seen_quiz_questions', 'quiz', 'updated_at'])

        return JsonResponse({
            'success': True,
            'quiz': fresh_questions,
            'count': len(fresh_questions),
            'difficulty': difficulty,
            'topic': topic,
        })
    except Exception as e:
        logger.exception("Failed to generate fresh quiz questions")
        if is_rate_limit_error(e):
            return JsonResponse({
                'success': False,
                'error': "Gemini API rate limit reached (Free Tier limit: 100 requests/minute). Please wait 30 seconds and try again."
            }, status=429)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
def submit_quiz_view(request, doc_id):
    """
    Analyzes quiz answers after submission:
    - Calculates overall and topic-wise accuracy.
    - Identifies weak topics based on incorrect answers and low performance (<60%).
    - Avoids labeling topics as weak when insufficient answers are available.
    - Generates actionable study recommendations.
    - Tracks performance across multiple attempts to show progress over time.
    """
    document = get_object_or_404(Document, id=doc_id)

    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body)
        else:
            payload = request.POST

        questions = payload.get('questions', [])
        user_answers = payload.get('user_answers', {})
        difficulty = payload.get('difficulty', 'mixed')
        target_topic = payload.get('target_topic', '')

        if not questions:
            if hasattr(document, 'study_material') and document.study_material.quiz:
                questions = document.study_material.quiz
            else:
                return JsonResponse({'success': False, 'error': 'No questions found for this attempt.'}, status=400)

        # 1. Grade individual questions and compute topic stats
        total_questions = len(questions)
        score = 0
        topic_stats = {}
        graded_questions = []

        for q in questions:
            q_id = str(q.get('id', ''))
            user_choice = user_answers.get(q_id)
            if user_choice is None:
                try:
                    user_choice = user_answers.get(int(q_id))
                except (ValueError, TypeError):
                    pass

            try:
                user_choice = int(user_choice) if user_choice is not None else None
            except (ValueError, TypeError):
                user_choice = None

            correct_index = int(q.get('correct_index', 0))
            is_correct = (user_choice == correct_index)
            if is_correct:
                score += 1

            topic = q.get('topic') or 'General Comprehension'
            if topic not in topic_stats:
                topic_stats[topic] = {'correct': 0, 'total': 0}

            topic_stats[topic]['total'] += 1
            if is_correct:
                topic_stats[topic]['correct'] += 1

            graded_questions.append({
                'id': q.get('id'),
                'question': q.get('question'),
                'options': q.get('options'),
                'correct_index': correct_index,
                'user_choice': user_choice,
                'is_correct': is_correct,
                'topic': topic,
                'difficulty': q.get('difficulty', 'medium'),
                'explanation': q.get('explanation', '')
            })

        # 2. Overall accuracy
        percentage = round((score / total_questions) * 100, 1) if total_questions > 0 else 0.0

        # 3. Topic-wise accuracy & Weak Topic analysis
        topic_scores = {}
        weak_topics = []
        recommendations = []

        for topic, stats in topic_stats.items():
            tot = stats['total']
            cor = stats['correct']
            t_acc = round((cor / tot) * 100, 1) if tot > 0 else 0.0

            topic_scores[topic] = {
                'correct': cor,
                'total': tot,
                'percentage': t_acc
            }

            # Avoid labeling topics as weak when insufficient answers are available:
            # Topic evaluated only if at least 1 question attempted for that topic.
            # Marked weak if accuracy is below 60%.
            if tot >= 1 and t_acc < 60.0:
                rec_text = f"Review the document passages discussing '{topic}' and test your recall."
                weak_topics.append({
                    'topic': topic,
                    'accuracy': t_acc,
                    'correct': cor,
                    'total': tot,
                    'reason': f"Scored {cor}/{tot} ({t_acc:.0f}%) on {topic} questions.",
                    'recommendation': rec_text
                })
                recommendations.append(f"Focus study on {topic}: accuracy is currently {t_acc:.0f}%.")

        if not weak_topics:
            if percentage >= 80.0:
                recommendations.append("Excellent mastery! You scored above 80% across all evaluated topics.")
            else:
                recommendations.append("Solid attempt! Review the question explanations to solidify edge cases.")

        # 4. Check historical progress and calculate improvement delta
        previous_attempts = QuizAttempt.objects.filter(document=document).order_by('-created_at')
        delta = None
        if previous_attempts.exists():
            last_attempt = previous_attempts.first()
            delta = round(percentage - last_attempt.percentage, 1)

        # 5. Persist QuizAttempt record
        attempt = QuizAttempt.objects.create(
            document=document,
            score=score,
            total_questions=total_questions,
            percentage=percentage,
            difficulty=difficulty,
            target_topic=target_topic or '',
            topic_scores=topic_scores,
            weak_topics=weak_topics,
            recommendations=recommendations,
            questions_snapshot=questions,
            user_answers=user_answers
        )

        # 6. Retrieve recent attempt history for this document
        history = [
            {
                'id': str(att.id),
                'score': att.score,
                'total_questions': att.total_questions,
                'percentage': att.percentage,
                'difficulty': att.difficulty,
                'target_topic': att.target_topic or 'All Topics',
                'weak_count': len(att.weak_topics),
                'created_at': att.created_at.strftime('%b %d, %H:%M'),
            }
            for att in QuizAttempt.objects.filter(document=document).order_by('-created_at')[:8]
        ]

        return JsonResponse({
            'success': True,
            'attempt_id': str(attempt.id),
            'score': score,
            'total_questions': total_questions,
            'percentage': percentage,
            'delta': delta,
            'topic_scores': topic_scores,
            'weak_topics': weak_topics,
            'recommendations': recommendations,
            'graded_questions': graded_questions,
            'history': history,
        })

    except Exception as e:
        logger.exception("Failed to submit and evaluate quiz")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
def quiz_history_view(request, doc_id):
    """
    Returns attempt history and weak topic evolution for the document.
    """
    document = get_object_or_404(Document, id=doc_id)
    attempts = document.quiz_attempts.all().order_by('-created_at')[:10]

    history = [
        {
            'id': str(att.id),
            'score': att.score,
            'total_questions': att.total_questions,
            'percentage': att.percentage,
            'difficulty': att.difficulty,
            'target_topic': att.target_topic or 'All Topics',
            'weak_count': len(att.weak_topics),
            'topic_scores': att.topic_scores,
            'created_at': att.created_at.strftime('%b %d, %H:%M'),
        }
        for att in attempts
    ]
    return JsonResponse({'success': True, 'history': history})

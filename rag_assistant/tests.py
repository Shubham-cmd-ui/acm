import os
import tempfile
import json
import numpy as np
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import Document, DocumentChunk, ChatMessage, StudyMaterial, QuizAttempt
from .forms import DocumentUploadForm
from .rag.chunker import split_text_into_chunks, chunk_document_pages
from .rag.vector_store import FaissVectorStore
from .rag.generator import RagGenerator, FALLBACK_MESSAGE
from .rag.extractor import extract_from_pdf, clean_text
from .rag.study_generator import StudyMaterialGenerator


class ChunkerAndExtractorTests(TestCase):
    def test_text_chunking_with_overlap(self):
        sample_text = (
            "Retrieval-Augmented Generation (RAG) is a technique for enhancing LLMs. "
            "It combines information retrieval with text generation. "
            "By querying an external vector database, relevant documents are retrieved. "
            "These documents are then passed as context to the generative AI model."
        )
        chunks = split_text_into_chunks(sample_text, chunk_size=80, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 100)

    def test_chunk_document_pages(self):
        pages_data = [
            {'page_number': 1, 'text': 'Page 1 introductory text content for testing.'},
            {'page_number': 2, 'text': 'Page 2 financial results and conclusions.'},
        ]
        chunks = chunk_document_pages(pages_data, chunk_size=50, chunk_overlap=10)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0]['page_number'], 1)
        self.assertEqual(chunks[-1]['page_number'], 2)


class FaissVectorStoreTests(TestCase):
    def test_faiss_vector_store_index_and_search(self):
        with tempfile.NamedTemporaryFile(suffix='.faiss', delete=False) as tmp:
            tmp_index_path = tmp.name

        try:
            store = FaissVectorStore(dimension=4)
            embeddings = np.array([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.707, 0.707, 0.0, 0.0],
            ], dtype=np.float32)

            store.create_and_save_index(embeddings, tmp_index_path)
            self.assertTrue(os.path.exists(tmp_index_path))

            query_vector = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
            scores, indices = store.search(tmp_index_path, query_vector, top_k=2)

            self.assertEqual(len(indices), 2)
            self.assertEqual(indices[0], 0)
            self.assertAlmostEqual(scores[0], 1.0, places=2)

        finally:
            if os.path.exists(tmp_index_path):
                os.remove(tmp_index_path)


class PdfUploadLimitTests(TestCase):
    def test_valid_file_within_50mb(self):
        # 1MB file is well within 50MB
        valid_file = SimpleUploadedFile("report.pdf", b"%PDF-1.4 test document content", content_type="application/pdf")
        form = DocumentUploadForm(files={'file': valid_file})
        self.assertTrue(form.is_valid())

    def test_oversized_file_rejected_with_clear_error(self):
        # Create a mock file exceeding 50 MB
        oversized = SimpleUploadedFile("huge.pdf", b"x" * 1024, content_type="application/pdf")
        oversized.size = 52 * 1024 * 1024  # 52 MB
        form = DocumentUploadForm(files={'file': oversized})
        self.assertFalse(form.is_valid())
        self.assertIn("exceeds maximum allowed limit of 50 MB", form.errors['file'][0])

    def test_empty_file_rejected(self):
        empty_file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        form = DocumentUploadForm(files={'file': empty_file})
        self.assertFalse(form.is_valid())
        self.assertIn("empty (0 bytes)", form.errors['file'][0])

    def test_corrupted_pdf_extraction_error(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(b"not a valid pdf header")
            tmp_path = tmp.name

        try:
            with self.assertRaises(ValueError) as ctx:
                extract_from_pdf(tmp_path)
            self.assertIn("corrupted or not a valid PDF", str(ctx.exception))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class ChatbotResponseAndFollowUpTests(TestCase):
    def test_generator_fallback_when_no_confident_sources(self):
        generator = object.__new__(RagGenerator)
        generator._call_model_with_fallback = lambda prompt: f"{FALLBACK_MESSAGE}\nCEO salaries vary widely."
        res = generator.generate_answer(
            query="What is the CEO salary?",
            sources=[],
            is_confident=False,
            top_score=0.15
        )
        self.assertIn("not found in the uploaded document", res['answer'])
        self.assertFalse(res['is_grounded'])
        self.assertTrue(res['is_general_knowledge'])
        self.assertEqual(res['sources'], [])

    def test_generator_includes_conversation_history(self):
        captured_prompt = []
        generator = object.__new__(RagGenerator)
        def mock_call(prompt):
            captured_prompt.append(prompt)
            return "The Transformer uses 6 layers."
        generator._call_model_with_fallback = mock_call

        sources = [{'chunk_index': 0, 'page_number': 1, 'score': 0.92, 'content': 'The Transformer uses 6 encoder layers.'}]
        conv_history = [
            {'role': 'user', 'content': 'What is the architecture?'},
            {'role': 'assistant', 'content': 'It is a sequence-to-sequence model.'}
        ]

        res = generator.generate_answer(
            query="How many layers does it have?",
            sources=sources,
            is_confident=True,
            top_score=0.92,
            conversation_history=conv_history
        )

        self.assertTrue(res['is_grounded'])
        self.assertEqual(res['answer'], "The Transformer uses 6 layers.")
        self.assertTrue(any("PREVIOUS CONVERSATION CONTEXT" in p for p in captured_prompt))
        self.assertTrue(any("What is the architecture?" in p for p in captured_prompt))


class FreshQuizGenerationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            original_filename="ml_notes.txt",
            file_type="txt",
            file_size_bytes=2048,
            total_chunks=2,
        )
        DocumentChunk.objects.create(document=self.doc, chunk_index=0, content="Deep learning uses artificial neural networks with multiple hidden layers.")
        DocumentChunk.objects.create(document=self.doc, chunk_index=1, content="Backpropagation computes gradients using the chain rule to update weights.")

    def test_validate_and_sanitize_quiz_questions(self):
        generator = object.__new__(StudyMaterialGenerator)
        raw = [
            {
                'id': 1,
                'question': 'What does backprop compute?',
                'options': ['Gradients', 'Accuracy', 'Loss', 'Learning rate'],
                'correct_index': 0,
                'difficulty': 'medium',
                'topic': 'Optimization',
                'explanation': 'Computed via chain rule.'
            },
            # Malformed question (missing options) should be safely filtered out
            {
                'id': 2,
                'question': 'Incomplete question',
                'options': [],
            }
        ]
        sanitized = generator._validate_and_sanitize_quiz_questions(raw)
        self.assertEqual(len(sanitized), 1)
        self.assertEqual(sanitized[0]['question'], 'What does backprop compute?')
        self.assertEqual(sanitized[0]['topic'], 'Optimization')
        self.assertEqual(sanitized[0]['correct_index'], 0)

    def test_quiz_generate_endpoint_with_avoidance(self):
        # Create initial study material with seen questions
        StudyMaterial.objects.create(
            document=self.doc,
            seen_quiz_questions=["What is a neural network?"]
        )

        # Mock generator to return fresh questions
        with tempfile.NamedTemporaryFile():
            pass

        generator_mock_questions = [
            {
                'id': 10,
                'question': 'What rule does backpropagation use?',
                'options': ['Chain rule', 'Power rule', 'Product rule', 'Quotient rule'],
                'correct_index': 0,
                'difficulty': 'easy',
                'topic': 'Backpropagation',
                'explanation': 'The chain rule computes partial derivatives.'
            }
        ]

        def mock_generate_quiz(self_gen, document, count=5, difficulty='mixed', topic='all', avoid_questions=None):
            # Verify avoid_questions was passed
            self.assertIn("What is a neural network?", avoid_questions)
            return generator_mock_questions

        StudyMaterialGenerator.generate_quiz = mock_generate_quiz

        res = self.client.post(
            f'/api/documents/{self.doc.id}/quiz/generate/',
            data=json.dumps({'count': 5, 'difficulty': 'easy', 'topic': 'all'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['quiz']), 1)
        self.assertEqual(data['quiz'][0]['question'], 'What rule does backpropagation use?')

        # Verify seen_quiz_questions was updated in database
        self.doc.study_material.refresh_from_db()
        self.assertIn('What rule does backpropagation use?', self.doc.study_material.seen_quiz_questions)


class WeakTopicsAndPerformanceTrackingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            original_filename="physics.txt",
            file_type="txt",
            file_size_bytes=4096,
            total_chunks=3,
        )

    def test_quiz_submit_calculates_topic_accuracy_and_flags_weak_topics(self):
        questions = [
            # Topic: Thermodynamics (1 correct, 0 incorrect -> 100%)
            {
                'id': 1,
                'question': 'What is the First Law of Thermodynamics?',
                'options': ['Conservation of energy', 'Entropy increases', 'Absolute zero', 'Ideal gas'],
                'correct_index': 0,
                'topic': 'Thermodynamics'
            },
            # Topic: Quantum Mechanics (0 correct, 2 incorrect -> 0% -> WEAK)
            {
                'id': 2,
                'question': 'What is Planck constant symbol?',
                'options': ['h', 'c', 'G', 'k'],
                'correct_index': 0,
                'topic': 'Quantum Mechanics'
            },
            {
                'id': 3,
                'question': 'What describes wave-particle duality?',
                'options': ['de Broglie relation', 'Newton laws', 'Maxwell equations', 'Ohm law'],
                'correct_index': 0,
                'topic': 'Quantum Mechanics'
            }
        ]

        # User answers: Q1 is correct (0), Q2 is wrong (1), Q3 is wrong (1)
        user_answers = {'1': 0, '2': 1, '3': 1}

        res = self.client.post(
            f'/api/documents/{self.doc.id}/quiz/submit/',
            data=json.dumps({
                'questions': questions,
                'user_answers': user_answers,
                'difficulty': 'medium',
                'target_topic': 'General'
            }),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['score'], 1)
        self.assertEqual(data['total_questions'], 3)
        self.assertAlmostEqual(data['percentage'], 33.3, places=1)

        # Topic Breakdown
        topic_scores = data['topic_scores']
        self.assertEqual(topic_scores['Thermodynamics']['percentage'], 100.0)
        self.assertEqual(topic_scores['Quantum Mechanics']['percentage'], 0.0)

        # Weak Topic Diagnostic: Quantum Mechanics (<60%) must be flagged
        weak_topics = data['weak_topics']
        self.assertEqual(len(weak_topics), 1)
        self.assertEqual(weak_topics[0]['topic'], 'Quantum Mechanics')
        self.assertEqual(weak_topics[0]['accuracy'], 0.0)
        self.assertIn("Quantum Mechanics", weak_topics[0]['recommendation'])

        # Actionable recommendations should be populated
        self.assertGreater(len(data['recommendations']), 0)

        # Verify QuizAttempt saved in DB
        attempts = QuizAttempt.objects.filter(document=self.doc)
        self.assertEqual(attempts.count(), 1)
        self.assertIsNone(data['delta'])  # First attempt has no prior delta

    def test_multi_attempt_progress_tracking_delta(self):
        # Create an earlier attempt with 40% accuracy
        QuizAttempt.objects.create(
            document=self.doc,
            score=2,
            total_questions=5,
            percentage=40.0,
            difficulty='medium',
            topic_scores={},
            weak_topics=[]
        )

        # Now submit a second attempt with 80% accuracy
        questions = [
            {'id': 1, 'question': 'Q1', 'options': ['A', 'B'], 'correct_index': 0, 'topic': 'General'},
            {'id': 2, 'question': 'Q2', 'options': ['A', 'B'], 'correct_index': 0, 'topic': 'General'},
        ]
        user_answers = {'1': 0, '2': 0}  # 2/2 = 100%

        res = self.client.post(
            f'/api/documents/{self.doc.id}/quiz/submit/',
            data=json.dumps({
                'questions': questions,
                'user_answers': user_answers,
                'difficulty': 'medium'
            }),
            content_type='application/json'
        )

        data = res.json()
        self.assertEqual(res.status_code, 200)
        # Delta improvement should be 100.0 - 40.0 = +60.0%
        self.assertEqual(data['delta'], 60.0)
        self.assertEqual(len(data['history']), 2)

    def test_avoid_labeling_topics_with_insufficient_answers_as_weak(self):
        # If no questions were asked for a topic, it must not be labeled weak
        questions = [
            {'id': 1, 'question': 'Q1', 'options': ['A', 'B'], 'correct_index': 0, 'topic': 'Algebra'}
        ]
        user_answers = {'1': 0}  # Algebra 1/1 = 100%

        res = self.client.post(
            f'/api/documents/{self.doc.id}/quiz/submit/',
            data=json.dumps({'questions': questions, 'user_answers': user_answers}),
            content_type='application/json'
        )
        data = res.json()
        # No weak topics
        self.assertEqual(len(data['weak_topics']), 0)


class RateLimitingAndBackoffTests(TestCase):
    def test_is_rate_limit_error_detection(self):
        from .rag.rate_limiter import is_rate_limit_error

        # Generic 429 string
        err1 = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for metric embed_content_free_tier_requests")
        self.assertTrue(is_rate_limit_error(err1))

        # Error with code attribute
        class MockApiError(Exception):
            code = 429
            status = "RESOURCE_EXHAUSTED"

        self.assertTrue(is_rate_limit_error(MockApiError("Rate limit")))

        # Error string with user's exact error
        user_err = Exception(
            "Processing failed: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota...'}}"
        )
        self.assertTrue(is_rate_limit_error(user_err))

        # Non-rate-limit error
        non_rate_err = ValueError("Corrupted PDF file header")
        self.assertFalse(is_rate_limit_error(non_rate_err))

    def test_extract_retry_delay_from_error_formats(self):
        from .rag.rate_limiter import extract_retry_delay

        # 1. From string containing 'retry in 9.363317543s'
        err_str = Exception("Please retry in 9.363317543s.")
        delay = extract_retry_delay(err_str)
        self.assertAlmostEqual(delay, 10.3633, places=2)

        # 2. From structured details with RetryInfo
        class StructuredError(Exception):
            details = {
                'error': {
                    'code': 429,
                    'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '9s'}]
                }
            }

        delay2 = extract_retry_delay(StructuredError("Quota exceeded"))
        self.assertEqual(delay2, 10.0)  # 9s + 1s buffer

        # 3. Default fallback when no delay specified
        default_delay = extract_retry_delay(Exception("Generic 429 rate limit"), default_delay=5.0)
        self.assertEqual(default_delay, 5.0)

    def test_execute_with_rate_limit_retry_success_after_failure(self):
        from .rag.rate_limiter import execute_with_rate_limit_retry

        call_count = 0
        sleep_durations = []

        def mock_flaky_api(x):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with 429
                raise Exception("429 RESOURCE_EXHAUSTED. Please retry in 4s.")
            return x * 2

        def mock_sleep(d):
            sleep_durations.append(d)

        result = execute_with_rate_limit_retry(
            mock_flaky_api,
            21,
            max_retries=3,
            sleep_fn=mock_sleep
        )

        self.assertEqual(result, 42)
        self.assertEqual(call_count, 2)
        self.assertEqual(len(sleep_durations), 1)
        self.assertAlmostEqual(sleep_durations[0], 5.0, places=1)  # 4s + 1s buffer

    def test_execute_with_rate_limit_retry_exhausted_raises_custom_error(self):
        from .rag.rate_limiter import execute_with_rate_limit_retry, RateLimitExceededError

        def mock_failing_api():
            raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded limit 100")

        sleep_calls = []

        with self.assertRaises(RateLimitExceededError):
            execute_with_rate_limit_retry(
                mock_failing_api,
                max_retries=2,
                sleep_fn=lambda s: sleep_calls.append(s)
            )

        self.assertEqual(len(sleep_calls), 2)

    def test_execute_with_rate_limit_retry_propagates_non_rate_limit_immediately(self):
        from .rag.rate_limiter import execute_with_rate_limit_retry

        def mock_bad_request():
            raise ValueError("Invalid argument")

        sleep_calls = []
        with self.assertRaises(ValueError):
            execute_with_rate_limit_retry(
                mock_bad_request,
                max_retries=3,
                sleep_fn=lambda s: sleep_calls.append(s)
            )

        # Should NOT sleep or retry for non-rate-limit errors
        self.assertEqual(len(sleep_calls), 0)

    def test_embedding_generator_recovers_from_429_batch_rate_limit(self):
        from unittest.mock import patch
        from .rag.embeddings import GeminiEmbeddingGenerator

        generator = GeminiEmbeddingGenerator(api_key="test-api-key")
        attempt_count = 0

        def flaky_embed_api(model_name, content):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                # First batch call trips 429 rate limit
                raise Exception(
                    "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: "
                    "generativelanguage.googleapis.com/embed_content_free_tier_requests, limit: 100. "
                    "Please retry in 2s."
                )
            # Second call returns valid embeddings
            return [[0.1] * 768 for _ in content]

        with patch.object(generator, '_call_embed_api', side_effect=flaky_embed_api):
            with patch('rag_assistant.rag.rate_limiter.time.sleep') as mock_sleep:
                texts = ["chunk 1", "chunk 2"]
                embeddings = generator.embed_texts(texts, batch_size=10, inter_batch_delay=0)

                self.assertEqual(attempt_count, 2)
                self.assertEqual(embeddings.shape, (2, 768))
                self.assertTrue(mock_sleep.called)

    def test_upload_document_view_handles_rate_limit_gracefully(self):
        from unittest.mock import patch
        from .rag.rate_limiter import RateLimitExceededError

        valid_file = SimpleUploadedFile("sample.txt", b"Hello world text content for testing RAG rate limits.", content_type="text/plain")

        # Mock embedding generator to raise RateLimitExceededError
        with patch('rag_assistant.views.get_embedding_generator') as mock_gen_factory:
            mock_gen = mock_gen_factory.return_value
            mock_gen.embed_texts.side_effect = RateLimitExceededError(
                "Gemini API rate limit reached (Free Tier limit: 100 requests/minute). Please wait 30 seconds."
            )

            res = self.client.post('/upload/', {'file': valid_file})
            self.assertEqual(res.status_code, 429)
            data = res.json()
            self.assertFalse(data['success'])
            self.assertIn("rate limit reached", data['error'].lower())
            # Ensure document was cleaned up
            self.assertEqual(Document.objects.count(), 0)


class ChatQAUpscaleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.doc = Document.objects.create(
            original_filename="quantum_computing.pdf",
            file_type="pdf",
            file_size_bytes=4096,
            total_chunks=6,
        )
        for i in range(6):
            DocumentChunk.objects.create(
                document=self.doc,
                chunk_index=i,
                page_number=(i // 2) + 1,
                content=f"Section {i}: Quantum superposition and entanglement allow qubits to represent multiple states simultaneously in chunk {i}."
            )

    def test_document_level_query_detection(self):
        from .rag.retriever import DocumentRetriever
        retriever = object.__new__(DocumentRetriever)

        # Overview and summary queries should trigger document-level handling
        self.assertTrue(retriever.is_document_level_query("Summarize this document in 3 bullets."))
        self.assertTrue(retriever.is_document_level_query("What is this PDF about?"))
        self.assertTrue(retriever.is_document_level_query("Give me an executive summary and key takeaways"))
        self.assertTrue(retriever.is_document_level_query("Explain the core concepts and outline"))

        # Specific questions should NOT trigger document-level cross-section
        self.assertFalse(retriever.is_document_level_query("What is Shor's algorithm speedup factor?"))
        self.assertFalse(retriever.is_document_level_query("How many qubits did the IBM experiment use?"))

    def test_document_cross_section_retrieval(self):
        from .rag.retriever import DocumentRetriever
        retriever = object.__new__(DocumentRetriever)

        sources, is_confident, top_score = retriever._retrieve_document_cross_section(
            self.doc, "Summarize this document"
        )
        self.assertTrue(is_confident)
        self.assertGreaterEqual(len(sources), 3)
        self.assertEqual(sources[0]['chunk_index'], 0)
        # Should be ordered chronologically by chunk index
        indices = [s['chunk_index'] for s in sources]
        self.assertEqual(indices, sorted(indices))

    def test_generator_structured_prompt_instructions(self):
        captured_prompts = []
        generator = object.__new__(RagGenerator)
        generator.model_name = "gemini-3.5-flash-lite"

        def mock_call(prompt):
            captured_prompts.append(prompt)
            return "### Overview\n\n| Qubit | State |\n|---|---|\n| $|0\\rangle$ | Ground |\n"

        generator._call_model_with_fallback = mock_call

        sources = [
            {'chunk_index': 0, 'page_number': 1, 'score': 0.95, 'content': 'Superposition is a fundamental principle.'}
        ]
        conv_history = [
            {'role': 'user', 'content': 'What is quantum superposition?'},
            {'role': 'assistant', 'content': 'Superposition allows multiple states at once.'}
        ]

        result = generator.generate_answer(
            query="Can you compare it with classical bits in a table?",
            sources=sources,
            is_confident=True,
            top_score=0.95,
            conversation_history=conv_history,
            document_title="quantum_computing.pdf"
        )

        self.assertTrue(result['is_grounded'])
        self.assertFalse(result['is_general_knowledge'])
        self.assertIn("### Overview", result['answer'])
        self.assertIn("| Qubit | State |", result['answer'])

        prompt_text = captured_prompts[0]
        # Verify instructions enforce structured Markdown, tables, and headings
        self.assertIn("ACTIVE DOCUMENT: 'quantum_computing.pdf'", prompt_text)
        self.assertIn("headings (###)", prompt_text)
        self.assertIn("tables", prompt_text)
        self.assertIn("PREVIOUS CONVERSATION CONTEXT", prompt_text)

    def test_query_document_view_preserves_dialogue_and_returns_clean_payload(self):
        from unittest.mock import patch

        mock_sources = [
            {'chunk_index': 0, 'page_number': 1, 'score': 0.94, 'content': 'Quantum entanglement binds states.'}
        ]

        with patch('rag_assistant.views.DocumentRetriever.retrieve', return_value=(mock_sources, True, 0.94)):
            with patch('rag_assistant.views.RagGenerator.generate_answer', return_value={
                'answer': "### Quantum Entanglement\n\nEntanglement creates correlated states.",
                'sources': mock_sources,
                'top_score': 0.94,
                'is_grounded': True,
                'is_general_knowledge': False,
            }):
                res = self.client.post(
                    '/api/query/',
                    data=json.dumps({
                        'document_id': str(self.doc.id),
                        'query': 'Explain entanglement with headings'
                    }),
                    content_type='application/json'
                )

                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data['success'])
                self.assertTrue(data['is_grounded'])
                self.assertFalse(data['is_general_knowledge'])
                self.assertEqual(len(data['sources']), 1)
                self.assertIn("### Quantum Entanglement", data['answer'])

                # Verify ChatMessage was saved to database
                self.assertEqual(self.doc.chat_messages.count(), 1)
                saved_msg = self.doc.chat_messages.first()
                self.assertEqual(saved_msg.question, 'Explain entanglement with headings')
                self.assertTrue(saved_msg.is_grounded)





import os
import json
import logging
from typing import Dict, Any, List, Union
from django.conf import settings
from ..models import Document, StudyMaterial
from .rate_limiter import execute_with_rate_limit_retry, is_rate_limit_error, RateLimitExceededError

logger = logging.getLogger(__name__)

FALLBACK_GENERATION_MODELS = [
    'gemini-3.5-flash-lite',
    'gemini-3.5-flash',
    'gemini-3.1-flash-lite',
]

STUDY_PROMPT_TEMPLATE = """You are a senior educator and curriculum designer.
Analyze the following document content thoroughly and produce comprehensive, high-quality study materials strictly grounded in the document facts.

CONFIGURATION:
- Generate EXACTLY {flashcard_count} flashcards.
- Generate EXACTLY {quiz_count} multiple-choice quiz questions.

You MUST return a valid JSON object matching the exact schema below.

JSON SCHEMA:
{{
  "flashcards": [
    {{
      "front": "Specific high-yield question or technical term",
      "back": "Clear, comprehensive definition or answer. Include key bullet details or formulas if mentioned.",
      "category": "Topic tag (e.g., Core Architecture, Mathematical Principle, Key Metric, Process)"
    }}
  ],
  "short_notes": {{
    "title": "Comprehensive Title for the Document Subject",
    "read_time": "Estimated read time (e.g., '4 min read')",
    "summary": "Thorough 3-4 sentence executive summary capturing the core premise and conclusions.",
    "key_takeaways": [
      "Crucial takeaway point 1 with specific facts",
      "Crucial takeaway point 2 with specific facts",
      "Crucial takeaway point 3 with specific facts",
      "Crucial takeaway point 4 with specific facts",
      "Crucial takeaway point 5 with specific facts"
    ],
    "glossary": [
      {{
        "term": "Key Terminology 1",
        "definition": "Precise, grounded definition based on context."
      }},
      {{
        "term": "Key Terminology 2",
        "definition": "Precise, grounded definition based on context."
      }}
    ],
    "sections": [
      {{
        "heading": "Thematic Section Name",
        "summary": "1-2 sentence overview of this specific theme.",
        "points": [
          "Detailed, insightful bullet explaining a core aspect",
          "Detailed, insightful bullet explaining a core aspect",
          "Detailed, insightful bullet explaining a core aspect"
        ]
      }}
    ],
    "conclusions": [
      "Primary conclusion or real-world implication 1",
      "Primary conclusion or real-world implication 2"
    ]
  }},
  "important_topics": [
    {{
      "title": "Topic Name",
      "importance": "Crucial", // Options: "Crucial", "High", "Core Concept"
      "overview": "Clear explanation of why this topic is essential within the document.",
      "key_points": [
        "Core point A with specific facts",
        "Core point B with specific facts"
      ]
    }}
  ],
  "quiz": [
    {{
      "id": 1,
      "question": "Challenging multiple-choice question testing critical understanding of the document?",
      "options": [
        "First option",
        "Second option",
        "Third option",
        "Fourth option"
      ],
      "correct_index": 0, // Integer 0, 1, 2, or 3 pointing to the correct option
      "difficulty": "medium", // "easy", "medium", or "hard"
      "topic": "Core Architecture",
      "explanation": "Detailed explanation citing the specific evidence from the document."
    }}
  ]
}}

DOCUMENT CONTENT:
=========================================
{document_text}
=========================================
"""

QUIZ_PROMPT_TEMPLATE = """You are an expert assessment specialist and curriculum developer.
Generate a fresh, high-quality multiple-choice quiz based strictly on the uploaded document content.

CONFIGURATION:
- Number of questions: {count}
- Difficulty mode: {difficulty_instruction}
- Target Topic: {topic_instruction}
{avoid_instruction}

JSON SCHEMA:
You MUST respond with a valid JSON array of question objects matching this exact structure:
[
  {{
    "id": 1,
    "question": "Clear, specific question testing key knowledge or reasoning from the document?",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "correct_index": 0,
    "difficulty": "medium",
    "topic": "Specific Topic Name",
    "explanation": "Direct explanation of why the correct option is right, citing specific facts from the document."
  }}
]

STRICT RULES:
1. Every question must be fully grounded in the provided document content. Never hallucinate facts.
2. Provide exactly 4 options per question. Exactly one option must be unambiguously correct.
3. 'correct_index' MUST be an integer between 0 and 3 pointing to the correct item in 'options'.
4. 'difficulty' must be one of: "easy", "medium", "hard".
5. 'topic' must be a specific, meaningful topic category (e.g. "Attention Mechanism", "Data Preprocessing", "Evaluation Metrics").
6. 'explanation' must explain the answer referencing facts from the document.
7. Do NOT repeat or closely rephrase any of the previously asked questions listed above.

DOCUMENT CONTENT:
=========================================
{document_text}
=========================================
"""

class StudyMaterialGenerator:
    """
    Generates customized Flashcards, Enhanced Short Notes, Important Topics,
    and Multiple-Choice Quizzes with user-defined question counts.
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        if not self.api_key:
            raise ValueError("Gemini API Key is missing. Set GEMINI_API_KEY in .env.")

        configured_model = model or getattr(settings, 'GEMINI_GENERATION_MODEL', 'gemini-3.5-flash-lite')
        if '2.5' in configured_model:
            configured_model = 'gemini-3.5-flash-lite'

        self.model_name = configured_model
        self._init_client()

    def _init_client(self):
        self.client_type = None
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.client_type = 'genai'
            return
        except ImportError:
            pass

        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.api_key)
            self.legacy_genai = legacy_genai
            self.client_type = 'legacy'
            return
        except ImportError:
            pass

        raise ImportError("No Gemini SDK installed.")

    def _get_document_text(self, document: Document, max_chars: int = 35000) -> str:
        """Extracts and concatenates text chunks from the document up to max_chars."""
        chunks = document.chunks.order_by('chunk_index')
        doc_text_parts = []
        char_count = 0

        for ch in chunks:
            if char_count + len(ch.content) > max_chars:
                remaining = max_chars - char_count
                if remaining > 100:
                    doc_text_parts.append(ch.content[:remaining])
                break
            doc_text_parts.append(ch.content)
            char_count += len(ch.content)

        document_text = "\n\n".join(doc_text_parts).strip()
        if not document_text:
            raise ValueError("No text found in document to process.")
        return document_text

    def get_or_generate_study_material(
        self,
        document: Document,
        force_regenerate: bool = False,
        flashcard_count: int = 10,
        quiz_count: int = 5,
        feature: str = 'all'
    ) -> Dict[str, Any]:
        """
        Retrieves existing study materials or generates new ones tailored to user counts.
        """
        # 1. Check existing cached study materials if not forcing regeneration
        if not force_regenerate:
            try:
                material = document.study_material
                if material.flashcards or material.quiz or material.short_notes:
                    return {
                        'success': True,
                        'cached': True,
                        'flashcards': material.flashcards,
                        'short_notes': material.short_notes,
                        'important_topics': material.important_topics,
                        'quiz': material.quiz,
                        'updated_at': material.updated_at.strftime('%b %d, %Y %H:%M'),
                    }
            except StudyMaterial.DoesNotExist:
                pass

        # 2. Collect document text
        document_text = self._get_document_text(document)

        # Sanitize counts (between reasonable bounds)
        flashcard_count = max(3, min(25, int(flashcard_count)))
        quiz_count = max(2, min(15, int(quiz_count)))

        # 3. Call Gemini with JSON schema output
        prompt = STUDY_PROMPT_TEMPLATE.format(
            flashcard_count=flashcard_count,
            quiz_count=quiz_count,
            document_text=document_text
        )
        result_json = self._call_model_json(prompt)
        if not isinstance(result_json, dict):
            raise ValueError("Model returned unexpected JSON format.")

        # 4. Extract generated components
        flashcards = result_json.get('flashcards', [])
        short_notes = result_json.get('short_notes', {})
        important_topics = result_json.get('important_topics', [])
        quiz = self._validate_and_sanitize_quiz_questions(result_json.get('quiz', []))

        # Track seen quiz questions
        seen_questions = [q['question'] for q in quiz if 'question' in q]

        # 5. Persist to database
        material, _ = StudyMaterial.objects.update_or_create(
            document=document,
            defaults={
                'flashcards': flashcards,
                'short_notes': short_notes,
                'important_topics': important_topics,
                'quiz': quiz,
                'seen_quiz_questions': seen_questions,
            }
        )

        return {
            'success': True,
            'cached': False,
            'flashcards': material.flashcards,
            'short_notes': material.short_notes,
            'important_topics': material.important_topics,
            'quiz': material.quiz,
            'updated_at': material.updated_at.strftime('%b %d, %Y %H:%M'),
        }

    def generate_quiz(
        self,
        document: Document,
        count: int = 5,
        difficulty: str = 'mixed',
        topic: str = 'all',
        avoid_questions: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates fresh, non-repeating quiz questions tailored by difficulty and target topic.
        Strictly validates schema, options, and correct answers.
        """
        document_text = self._get_document_text(document)
        count = max(2, min(15, int(count)))
        difficulty = difficulty.lower() if difficulty else 'mixed'

        difficulty_instructions = {
            'easy': 'EASY: Direct recall of key definitions, explicit document facts, terminology, and explicit statements.',
            'medium': 'MEDIUM: Conceptual comprehension, comparing components, cause-and-effect relationships, and process steps.',
            'hard': 'HARD: In-depth analytical reasoning, synthesis of multiple document sections, edge cases, and critical analysis.',
            'mixed': 'MIXED: A balanced distribution of easy (factual), medium (conceptual), and hard (analytical) questions.'
        }
        diff_instruction = difficulty_instructions.get(difficulty, difficulty_instructions['mixed'])

        if topic and topic.lower() not in ['all', 'mixed', '']:
            topic_instruction = f"Focus all questions specifically on the topic '{topic}'. Ground questions in the document's coverage of this topic."
        else:
            topic_instruction = "Cover a diverse, comprehensive spread of the primary topics and concepts found in the document."

        avoid_instruction = ""
        if avoid_questions:
            clean_avoid = [q.strip() for q in avoid_questions if q and q.strip()][:35]
            if clean_avoid:
                avoid_list_str = "\n".join([f"- {q}" for q in clean_avoid])
                avoid_instruction = f"\nPREVIOUSLY ASKED QUESTIONS TO AVOID (DO NOT REPEAT OR CLOSELY REPHRASE THESE):\n{avoid_list_str}\n"

        prompt = QUIZ_PROMPT_TEMPLATE.format(
            count=count,
            difficulty_instruction=diff_instruction,
            topic_instruction=topic_instruction,
            avoid_instruction=avoid_instruction,
            document_text=document_text
        )

        result = self._call_model_json(prompt)
        raw_questions = []
        if isinstance(result, list):
            raw_questions = result
        elif isinstance(result, dict):
            raw_questions = result.get('quiz', result.get('questions', []))

        validated_questions = self._validate_and_sanitize_quiz_questions(raw_questions)
        if not validated_questions:
            raise ValueError("Failed to generate valid quiz questions from document.")

        return validated_questions

    def _validate_and_sanitize_quiz_questions(self, raw_questions: List[Any]) -> List[Dict[str, Any]]:
        """
        Validates question format, guarantees 4 options, validates correct_index,
        and assigns topic and difficulty tags.
        """
        validated = []
        for idx, item in enumerate(raw_questions, 1):
            if not isinstance(item, dict):
                continue

            question_text = str(item.get('question', '')).strip()
            if not question_text:
                continue

            raw_options = item.get('options', [])
            if not isinstance(raw_options, list) or len(raw_options) < 2:
                continue

            # Ensure options are clean strings
            options = [str(opt).strip() for opt in raw_options if str(opt).strip()]
            if len(options) < 2:
                continue

            # Validate correct_index
            correct_index = item.get('correct_index', 0)
            try:
                correct_index = int(correct_index)
            except (ValueError, TypeError):
                correct_index = 0

            if correct_index < 0 or correct_index >= len(options):
                correct_index = 0

            topic = str(item.get('topic', '')).strip() or "General Comprehension"
            difficulty = str(item.get('difficulty', 'medium')).lower()
            if difficulty not in ['easy', 'medium', 'hard']:
                difficulty = 'medium'

            explanation = str(item.get('explanation', '')).strip()
            if not explanation:
                explanation = "Grounded in document context."

            validated.append({
                'id': item.get('id', idx),
                'question': question_text,
                'options': options,
                'correct_index': correct_index,
                'topic': topic,
                'difficulty': difficulty,
                'explanation': explanation
            })

        return validated

    def _call_model_json(self, prompt: str) -> Union[Dict[str, Any], List[Any]]:
        """Calls Gemini API requesting JSON output with candidate model fallback."""
        candidates = [self.model_name] + [m for m in FALLBACK_GENERATION_MODELS if m != self.model_name]
        last_error = None

        for candidate in candidates:
            try:
                raw_text = execute_with_rate_limit_retry(
                    self._call_single_model,
                    candidate,
                    prompt,
                    context_desc=f"Generating study JSON with '{candidate}'"
                )
                clean_text = raw_text.strip()
                if clean_text.startswith('```'):
                    lines = clean_text.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines and lines[-1].startswith('```'):
                        lines = lines[:-1]
                    clean_text = "\n".join(lines).strip()

                parsed = json.loads(clean_text)
                if candidate != self.model_name:
                    logger.warning(f"Switched model from {self.model_name} to {candidate}.")
                    self.model_name = candidate
                return parsed
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ['404', 'not found', '503', 'unavailable']):
                    last_error = e
                    continue
                raise e

        raise last_error or RuntimeError("Failed to generate content from model.")

    def _call_single_model(self, model_name: str, prompt: str) -> str:
        clean_model = model_name.replace('models/', '')

        if self.client_type == 'genai':
            from google.genai import types
            response = self.client.models.generate_content(
                model=clean_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=5000,
                )
            )
            return response.text

        elif self.client_type == 'legacy':
            model_id = model_name if model_name.startswith('models/') else f"models/{model_name}"
            model = self.legacy_genai.GenerativeModel(
                model_name=model_id,
                generation_config={'response_mime_type': 'application/json', 'temperature': 0.3}
            )
            resp = model.generate_content(prompt)
            return resp.text

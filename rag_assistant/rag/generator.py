import os
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings

from .rate_limiter import execute_with_rate_limit_retry, is_rate_limit_error, RateLimitExceededError

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "ℹ️ This information is not found in the uploaded document. Here is the answer based on general AI knowledge:"

SYSTEM_INSTRUCTION = """You are LearningHub's Senior AI Document Intelligence & Learning Assistant, operating with the analytical rigor, clarity, and structural elegance of premier AI systems (ChatGPT, Gemini, and Claude).

YOUR CORE MISSION:
Deliver accurate, deeply grounded, beautifully formatted, and engaging answers based on the uploaded learning materials, with seamless conversation context awareness and transparent demarcation between document facts and general knowledge.

RESPONSE STRUCTURE & FORMATTING RULES:
1. DIRECT OPENING (NO FILLER):
   - Answer the user's specific question directly in the very first sentence without conversational pleasantries, generic filler, or throat-clearing (never begin with "Sure!", "Based on the provided text...", "According to the document...", or "I hope this helps!").
   - Lead immediately with the factual answer, thesis, or summary conclusion.

2. SOPHISTICATED MARKDOWN FORMATTING:
   - Headings: Use '### ' and '#### ' to partition multi-part answers logically.
   - Bullet Points: Use '- **Concept**: Detailed explanation...' for key takeaways, features, pros/cons, and core points.
   - Numbered Sequences: Use '1. ', '2. ' for chronological steps, workflows, algorithms, or instructional procedures.
   - Comparison & Structured Tables: Whenever comparing concepts, metrics, categories, or tabular data, ALWAYS format as clean GitHub-flavored Markdown tables:
     | Feature / Concept | Description | Document Finding |
     |---|---|---|
     | Concept A | ... | ... |
   - Code Blocks: When showing code, SQL queries, CLI commands, or syntax, ALWAYS use fenced code blocks with the exact language tag:
     ```python
     # Python implementation
     ```
   - Mathematical Notation: Format formulas and equations cleanly using KaTeX math notation (e.g., $E = mc^2$ or $$\\text{Loss} = -\\sum y \\log(\\hat{y})$$).
   - Highlights & Bold Terms: Bold key terms, numbers, dates, and conclusions for maximum visual readability.

3. ADAPTIVE LENGTH & DEPTH:
   - Strictly honor any user directive (e.g., "in one sentence", "in 3 bullets", "summarize", "detailed breakdown", "step by step").
   - For broad inquiries (e.g., summaries, explanations, reviews), produce thorough, well-structured, multi-section answers with concrete examples.
   - For specific factual questions, keep the answer crisp, focused, and concise.

4. ACCURACY & NO HALLUCINATION:
   - Ground document-related answers strictly and faithfully in the provided DOCUMENT CONTEXT PASSAGES.
   - Never fabricate facts, citations, numbers, or conclusions.
   - When information is completely absent from the document:
     * Clearly state at the very top:
       > ℹ️ **Not found in document:** This information is not mentioned in the uploaded document. Here is the answer based on general AI knowledge:
     * Then provide a helpful, comprehensive response using general AI knowledge.
   - When information is partially in the document:
     * Answer using document facts first, then provide a clearly labeled section for supplementary general knowledge.

5. CONVERSATION CONTEXT & FOLLOW-UP RESOLUTION:
   - Use dialogue history to resolve pronouns ("it", "they", "that formula"), relative references ("the third point", "explain that table further"), and build progressively upon prior answers.
"""

FALLBACK_GENERATION_MODELS = [
    'gemini-3.5-flash-lite',
    'gemini-3.5-flash',
    'gemini-3.1-flash-lite',
]

class RagGenerator:
    """
    Constructs contextual prompts with retrieved source chunks and conversation history.
    Produces high-quality, structured, grounded answers matching ChatGPT/Claude standards.
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
            self.legacy_model = legacy_genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_INSTRUCTION
            )
            self.client_type = 'legacy'
            return
        except ImportError:
            pass

        raise ImportError("No Google Gemini SDK found. Install 'google-genai' via pip.")

    def format_context(self, sources: List[Dict[str, Any]]) -> str:
        """Formats retrieved chunks into a numbered context block for the model."""
        blocks = []
        for i, s in enumerate(sources, 1):
            page_info = f"Page {s['page_number']}" if s.get('page_number') else "Document Body"
            score_info = f"Relevance: {int(s.get('score', 0) * 100)}%"
            header = f"[Passage {i} | {page_info} | Chunk #{s['chunk_index']} | {score_info}]"
            content = s['content'].strip()
            blocks.append(f"{header}\n{content}")

        return "\n\n".join(blocks)

    def generate_answer(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        is_confident: bool,
        top_score: float,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        document_title: str = "Uploaded Document"
    ) -> Dict[str, Any]:
        """
        Executes generation:
        1. If relevant sources exist, grounds response directly in document context with rich Markdown.
        2. Incorporates conversation history for multi-turn coherence and pronoun resolution.
        3. If topic is absent from document, transparently answers using Gemini AI general knowledge.
        4. Adjusts structure and depth to match ChatGPT, Gemini, and Claude standards.
        """
        history_block = ""
        if conversation_history:
            recent_turns = conversation_history[-8:]
            formatted_turns = []
            for msg in recent_turns:
                role = "Student/User" if msg.get('role') == 'user' else "LearningHub Tutor"
                formatted_turns.append(f"{role}: {msg.get('content', '').strip()}")
            if formatted_turns:
                history_block = (
                    "PREVIOUS CONVERSATION CONTEXT (use to resolve follow-ups, pronouns & continuity):\n"
                    "--------------------------------------------------------------------\n"
                    + "\n".join(formatted_turns) + "\n"
                    "--------------------------------------------------------------------\n\n"
                )

        # Case A: Low vector confidence or zero chunks match document
        if not sources or not is_confident:
            general_prompt = (
                f"{history_block}"
                f"ACTIVE DOCUMENT: '{document_title}'\n\n"
                f"USER QUESTION: {query}\n\n"
                f"INSTRUCTION:\n"
                f"The user question is not answered in the uploaded document '{document_title}'.\n"
                f"Start your response on the first line with:\n"
                f"'{FALLBACK_MESSAGE}'\n\n"
                f"Then answer directly, concisely, and comprehensively based on general AI knowledge using structured Markdown (### headings, bold labels, tables, or code where helpful)."
            )
            try:
                raw_text = self._call_model_with_fallback(general_prompt)
                return {
                    'answer': raw_text.strip(),
                    'sources': [],
                    'top_score': top_score,
                    'is_grounded': False,
                    'is_general_knowledge': True,
                }
            except Exception as e:
                return {
                    'answer': f"This topic was not found in the document, and general AI query encountered an issue: {str(e)}",
                    'sources': [],
                    'top_score': top_score,
                    'is_grounded': False,
                    'is_general_knowledge': True,
                }

        # Case B: Context passages retrieved from document
        context_str = self.format_context(sources)
        prompt = (
            f"{history_block}"
            f"ACTIVE DOCUMENT: '{document_title}'\n\n"
            f"DOCUMENT CONTEXT PASSAGES:\n"
            f"=========================================\n"
            f"{context_str}\n"
            f"=========================================\n\n"
            f"USER QUESTION: {query}\n\n"
            f"INSTRUCTION FOR GENERATION:\n"
            f"1. Answer directly and factually using the document context passages above.\n"
            f"2. Structure your answer cleanly with Markdown headings (###), bold bullet labels, numbered steps for procedures, and tables for comparisons or structured data.\n"
            f"3. Include syntax-highlighted code blocks with language tags if code or technical syntax is asked.\n"
            f"4. If the document covers parts of the question but omits certain specifics, answer what the document states first, then provide supplementary general AI knowledge clearly marked in a separate callout section.\n"
            f"5. Maintain seamless dialogue continuity based on the conversation history.\n\n"
            f"STRUCTURED ANSWER:"
        )

        try:
            raw_text = self._call_model_with_fallback(prompt)
            answer_text = raw_text.strip()

            is_grounded = True
            is_general_knowledge = False

            # Check if model triggered general knowledge fallback phrase
            lower_ans = answer_text.lower()
            if any(phrase in lower_ans for phrase in ["not found in the uploaded document", "not found in document", "not mentioned in the uploaded document", "general ai knowledge"]):
                # If fallback phrase is triggered at the start
                if lower_ans.startswith("> ℹ️") or lower_ans.startswith("ℹ️") or "not found" in lower_ans[:140]:
                    is_grounded = False
                    is_general_knowledge = True

            return {
                'answer': answer_text,
                'sources': sources if is_grounded else [],
                'top_score': top_score,
                'is_grounded': is_grounded,
                'is_general_knowledge': is_general_knowledge,
            }

        except Exception as e:
            if is_rate_limit_error(e):
                err_msg = "Gemini API rate limit reached (Free Tier limit: 100 requests/minute). Please wait a few moments before asking again."
            else:
                err_msg = f"AI Generation error: {str(e)}. Please check your GEMINI_API_KEY."
            return {
                'answer': err_msg,
                'sources': sources,
                'top_score': top_score,
                'is_grounded': False,
                'is_general_knowledge': False,
            }

    def _call_model_with_fallback(self, prompt: str) -> str:
        """Invokes Gemini with automatic candidate model fallback if retired or unavailable, with rate limit retries."""
        candidates = [self.model_name] + [m for m in FALLBACK_GENERATION_MODELS if m != self.model_name]
        last_error = None

        for candidate in candidates:
            try:
                result = execute_with_rate_limit_retry(
                    self._call_model,
                    candidate,
                    prompt,
                    context_desc=f"Generating content with '{candidate}'"
                )
                if candidate != self.model_name:
                    logger.warning(f"Generation model '{self.model_name}' unavailable. Switched to '{candidate}'.")
                    self.model_name = candidate
                return result
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ['404', 'not found', '503', 'unavailable', 'no longer available']):
                    last_error = e
                    continue
                raise e

        raise last_error or RuntimeError("All candidate generation models failed.")

    def _call_model(self, model_name: str, prompt: str) -> str:
        clean_model = model_name.replace('models/', '')

        if self.client_type == 'genai':
            from google.genai import types
            response = self.client.models.generate_content(
                model=clean_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.25,
                    max_output_tokens=4096,
                )
            )
            return response.text

        elif self.client_type == 'legacy':
            model_id = model_name if model_name.startswith('models/') else f"models/{model_name}"
            model = self.legacy_genai.GenerativeModel(
                model_name=model_id,
                system_instruction=SYSTEM_INSTRUCTION
            )
            response = model.generate_content(
                prompt,
                generation_config={'temperature': 0.25, 'max_output_tokens': 4096}
            )
            return response.text

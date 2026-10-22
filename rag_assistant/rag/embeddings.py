import os
import time
import logging
import numpy as np
from typing import List, Union
from django.conf import settings

from .rate_limiter import execute_with_rate_limit_retry, RateLimitExceededError

logger = logging.getLogger(__name__)

# Fallback candidate models in order of preference
FALLBACK_EMBEDDING_MODELS = [
    'gemini-embedding-001',
    'gemini-embedding-2',
]

class GeminiEmbeddingGenerator:
    """
    Generates dense vector embeddings using Google's Gemini Embedding API.
    Supports gemini-embedding-001 with batching, L2 normalization, and automatic model fallback.
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        if not self.api_key:
            raise ValueError(
                "Gemini API Key is missing. Please set GEMINI_API_KEY in your .env file or environment."
            )

        configured_model = model or getattr(settings, 'GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001')
        # If user configured deprecated text-embedding-004, default to gemini-embedding-001
        if 'text-embedding-004' in configured_model:
            configured_model = 'gemini-embedding-001'

        self.model_name = configured_model
        self._init_client()

    def _init_client(self):
        """Initialize either modern google-genai or google-generativeai."""
        self.client_type = None

        # 1. Try modern unified google-genai SDK
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.client_type = 'genai'
            return
        except ImportError:
            pass

        # 2. Try legacy google-generativeai SDK
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.api_key)
            self.legacy_genai = legacy_genai
            self.client_type = 'legacy'
            return
        except ImportError:
            pass

        raise ImportError(
            "Neither 'google-genai' nor 'google-generativeai' is installed. "
            "Please install dependencies with: pip install google-genai"
        )

    def _normalize_vector(self, vec: np.ndarray) -> np.ndarray:
        """L2 normalizes a vector so dot product equals cosine similarity."""
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return (vec / norm).astype(np.float32)

    def embed_texts(self, texts: List[str], batch_size: int = 20, inter_batch_delay: float = 0.5) -> np.ndarray:
        """
        Embed a list of text strings in paced batches with exponential backoff on rate limits.
        Returns a 2D float32 numpy array of shape (len(texts), embedding_dim).
        """
        if not texts:
            return np.empty((0, 3072), dtype=np.float32)

        # Sanitize texts: replace empty or whitespace-only strings with a non-empty token
        cleaned_texts = [t if t and t.strip() else " " for t in texts]

        all_embeddings = []
        total_batches = (len(cleaned_texts) + batch_size - 1) // batch_size

        for b_idx, i in enumerate(range(0, len(cleaned_texts), batch_size), start=1):
            batch = cleaned_texts[i:i + batch_size]
            
            # Pacing delay between batches to avoid burst rate limit violations
            if b_idx > 1 and inter_batch_delay > 0:
                time.sleep(inter_batch_delay)

            batch_vectors = self._embed_batch_with_fallback(batch)
            all_embeddings.extend(batch_vectors)

        arr = np.array(all_embeddings, dtype=np.float32)
        # Normalize each row for cosine similarity
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = arr / norms
        return normalized.astype(np.float32)

    def _embed_batch_with_fallback(self, batch: List[str]) -> List[List[float]]:
        """Attempt embedding with active model with rate-limit recovery and 404 candidate fallback."""
        candidate_models = [self.model_name] + [m for m in FALLBACK_EMBEDDING_MODELS if m != self.model_name]
        last_error = None

        for candidate in candidate_models:
            try:
                vectors = execute_with_rate_limit_retry(
                    self._call_embed_api,
                    candidate,
                    batch,
                    context_desc=f"Embedding batch ({len(batch)} chunks) with '{candidate}'"
                )
                if candidate != self.model_name:
                    logger.warning(f"Embedding model '{self.model_name}' was unavailable. Switched to '{candidate}'.")
                    self.model_name = candidate
                return vectors
            except Exception as e:
                err_str = str(e)
                if '404' in err_str or 'not found' in err_str.lower():
                    last_error = e
                    continue
                raise e

        raise last_error or RuntimeError("All candidate embedding models failed.")

    def _call_embed_api(self, model_name: str, content: Union[str, List[str]]) -> List[List[float]]:
        """Call Google GenAI or GenerativeAI embedding API."""
        if self.client_type == 'genai':
            # Clean model name (strip models/ if present for genai client)
            clean_name = model_name.replace('models/', '')
            response = self.client.models.embed_content(
                model=clean_name,
                contents=content,
            )
            if hasattr(response, 'embeddings') and response.embeddings:
                return [emb.values for emb in response.embeddings]
            elif hasattr(response, 'embedding') and response.embedding:
                return [response.embedding.values]
            else:
                raise RuntimeError("Unexpected embedding response structure from Gemini API.")

        elif self.client_type == 'legacy':
            model_id = model_name if model_name.startswith('models/') else f"models/{model_name}"
            result = self.legacy_genai.embed_content(
                model=model_id,
                content=content,
                task_type="retrieval_document" if isinstance(content, list) else "retrieval_query"
            )
            if 'embedding' in result:
                emb = result['embedding']
                # If single vector returned for list, wrap it
                if emb and isinstance(emb[0], (int, float)):
                    return [emb]
                return emb
            raise RuntimeError("Failed to retrieve embeddings from google-generativeai.")

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single user query string.
        Returns a 1D float32 numpy array normalized with L2 norm.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        query = query.strip()
        candidate_models = [self.model_name] + [m for m in FALLBACK_EMBEDDING_MODELS if m != self.model_name]
        last_error = None

        for candidate in candidate_models:
            try:
                vectors = execute_with_rate_limit_retry(
                    self._call_embed_api,
                    candidate,
                    query,
                    context_desc=f"Embedding query with '{candidate}'"
                )
                if candidate != self.model_name:
                    self.model_name = candidate
                vec = np.array(vectors[0], dtype=np.float32)
                return self._normalize_vector(vec)
            except Exception as e:
                err_str = str(e)
                if '404' in err_str or 'not found' in err_str.lower():
                    last_error = e
                    continue
                raise e

        raise last_error or RuntimeError("Failed to embed query with any candidate model.")


def get_embedding_generator() -> GeminiEmbeddingGenerator:
    """Helper factory for GeminiEmbeddingGenerator."""
    return GeminiEmbeddingGenerator()

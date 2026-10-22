import os
import re
import logging
from typing import List, Dict, Any, Tuple
from django.conf import settings
from .embeddings import get_embedding_generator
from .vector_store import FaissVectorStore

logger = logging.getLogger(__name__)

# Patterns that indicate the user wants a document-wide overview or summary
DOCUMENT_LEVEL_PATTERNS = [
    r'\bsummar(y|ize|ise|izing)\b',
    r'\boverview\b',
    r'\bmain (points|topics|ideas|concepts|themes)\b',
    r'\bkey (takeaways|points|concepts|terms)\b',
    r'\bwhat is this (document|pdf|file|lesson|text) about\b',
    r'\btell me about this (document|pdf|file|lesson|text)\b',
    r'\bexplain this (document|pdf|file|lesson|text)\b',
    r'\boutline\b',
    r'\btable of contents\b',
    r'\bexecutive summary\b',
    r'\bcore (concepts|architecture|theme)\b',
    r'\bintroduction\b',
]


class DocumentRetriever:
    """
    Coordinates semantic vector retrieval and document-level context assembly.
    Supports:
    - High-level document synthesis (summaries, overviews, core points)
    - Targeted semantic search with configurable top-k and threshold
    - Chronological passage ordering for coherent context flow
    - Self-healing index recovery if index file is temporarily absent
    """

    def __init__(self, top_k: int = None, threshold: float = None):
        self.top_k = top_k or getattr(settings, 'TOP_K_CHUNKS', 6)
        self.threshold = threshold or getattr(settings, 'SIMILARITY_THRESHOLD', 0.35)
        self.embedding_generator = get_embedding_generator()
        self.vector_store = FaissVectorStore()

    def is_document_level_query(self, query: str) -> bool:
        """Determines if the question requires a document-wide synthesis rather than a localized fact lookup."""
        q_lower = query.lower().strip()
        for pattern in DOCUMENT_LEVEL_PATTERNS:
            if re.search(pattern, q_lower):
                return True
        return False

    def retrieve(self, document, query: str) -> Tuple[List[Dict[str, Any]], bool, float]:
        """
        Executes semantic search against the document's vector index.
        For document-level queries (summaries, overviews), retrieves a representative
        cross-section of introductory, core, and concluding passages.
        
        Returns:
            (retrieved_sources, is_confident, top_score)
        """
        index_path = document.get_index_path()
        total_chunks = document.chunks.count()

        if total_chunks == 0:
            return [], False, 0.0

        # Self-healing: if index file does not exist, rebuild it on the fly
        if not os.path.exists(index_path):
            logger.warning(f"Index file for document '{document.original_filename}' missing. Rebuilding...")
            self._rebuild_index(document)

        # Case 1: High-level document overview / summary request
        if self.is_document_level_query(query):
            return self._retrieve_document_cross_section(document, query)

        # Case 2: Targeted semantic vector search
        return self._retrieve_semantic_neighbors(document, query, index_path)

    def _retrieve_document_cross_section(self, document, query: str) -> Tuple[List[Dict[str, Any]], bool, float]:
        """
        Gathers a balanced selection of chunks spanning introduction, body, and conclusion,
        along with any semantically matching chunks.
        """
        chunks_qs = document.chunks.order_by('chunk_index')
        total_chunks = chunks_qs.count()

        if total_chunks <= 8:
            selected_chunks = list(chunks_qs)
        else:
            # Pick first 2 chunks (intro/abstract)
            intro_chunks = list(chunks_qs[:2])
            # Pick final chunk (conclusion)
            conclusion_chunk = list(chunks_qs.reverse()[:1])
            # Pick 3-4 evenly spaced body chunks
            step = max(1, total_chunks // 5)
            body_indices = [i * step for i in range(1, 5) if i * step < total_chunks - 1]
            body_chunks = list(document.chunks.filter(chunk_index__in=body_indices))

            # Combine and deduplicate
            seen_ids = set()
            selected_chunks = []
            for c in intro_chunks + body_chunks + conclusion_chunk:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    selected_chunks.append(c)

        # Sort chronologically by chunk index
        selected_chunks.sort(key=lambda c: c.chunk_index)

        sources = [
            {
                'chunk_index': c.chunk_index,
                'page_number': c.page_number,
                'score': 0.95 if c.chunk_index in [0, 1] else 0.85,
                'content': c.content,
            }
            for c in selected_chunks
        ]
        return sources, True, 0.95

    def _retrieve_semantic_neighbors(self, document, query: str, index_path: str) -> Tuple[List[Dict[str, Any]], bool, float]:
        """Performs vector search in FAISS and maps to database chunks."""
        # 1. Embed query
        query_vector = self.embedding_generator.embed_query(query)

        # 2. Search FAISS index for top-k nearest neighbors
        scores, chunk_indices = self.vector_store.search(
            index_path=index_path,
            query_vector=query_vector,
            top_k=max(self.top_k, 6)
        )

        if not chunk_indices:
            return [], False, 0.0

        top_score = float(scores[0]) if scores else 0.0

        # Check threshold confidence
        if top_score < self.threshold:
            # Low confidence: passages are semantically irrelevant
            return [], False, top_score

        # 3. Fetch chunks from Django database
        chunks_queryset = document.chunks.filter(chunk_index__in=chunk_indices)
        chunk_map = {chunk.chunk_index: chunk for chunk in chunks_queryset}

        retrieved_sources = []
        for score, idx in zip(scores, chunk_indices):
            chunk = chunk_map.get(idx)
            if chunk:
                # Include chunks meeting floor score
                if score >= (self.threshold * 0.75):
                    retrieved_sources.append({
                        'chunk_index': chunk.chunk_index,
                        'page_number': chunk.page_number,
                        'score': float(score),
                        'content': chunk.content,
                    })

        # Sort retrieved chunks in natural reading order (by chunk_index)
        retrieved_sources.sort(key=lambda s: s['chunk_index'])

        is_confident = len(retrieved_sources) > 0 and (top_score >= self.threshold)
        return retrieved_sources, is_confident, top_score

    def _rebuild_index(self, document):
        """Rebuilds the FAISS index from stored chunks if missing on disk."""
        chunks = document.chunks.order_by('chunk_index')
        texts = [c.content for c in chunks]
        if not texts:
            return
        embeddings = self.embedding_generator.embed_texts(texts)
        self.vector_store = FaissVectorStore(dimension=embeddings.shape[1])
        self.vector_store.create_and_save_index(embeddings, document.get_index_path())

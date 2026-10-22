import os
import logging
from typing import Tuple, List
import numpy as np

logger = logging.getLogger(__name__)

try:
    import faiss
    HAS_FAISS = True
except (ImportError, AttributeError, OSError) as e:
    faiss = None
    HAS_FAISS = False
    logger.warning(f"FAISS binary unavailable ({e}). Using optimized NumPy fallback for vector similarity.")


class FaissVectorStore:
    """
    Manages dense vector similarity search scoped per document.
    Uses FAISS IndexFlatIP with L2-normalized embeddings for exact Cosine Similarity,
    with an automatic NumPy linear algebra fallback for serverless/minimal environments.
    """

    def __init__(self, dimension: int = 3072):
        self.dimension = dimension

    def create_and_save_index(self, embeddings: np.ndarray, index_path: str) -> None:
        """
        Builds a new vector index from normalized chunk embeddings
        and serializes it to the specified index_path.
        """
        if embeddings.ndim != 2:
            raise ValueError(f"Embeddings array must be 2D, received ndim={embeddings.ndim}")

        num_vectors, dim = embeddings.shape
        if dim != self.dimension:
            self.dimension = dim

        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        dir_name = os.path.dirname(index_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        if HAS_FAISS:
            try:
                index = faiss.IndexFlatIP(self.dimension)
                index.add(embeddings)
                faiss.write_index(index, index_path)
                return
            except Exception as e:
                logger.warning(f"faiss.write_index failed ({e}). Saving NumPy backup.")

        # Save NumPy vector backup
        np.save(index_path, embeddings)

    def search(
        self,
        index_path: str,
        query_vector: np.ndarray,
        top_k: int = 4
    ) -> Tuple[List[float], List[int]]:
        """
        Loads the document's scoped vector index and retrieves the top-k most similar chunks.
        
        Returns:
            (scores, indices):
            - scores: list of cosine similarity floats (e.g. 0.85).
            - indices: list of 0-based integer chunk indices matching DocumentChunk.chunk_index.
        """
        npy_path = index_path if index_path.endswith('.npy') else index_path + '.npy'

        if not os.path.exists(index_path) and not os.path.exists(npy_path):
            raise FileNotFoundError(f"Vector index file not found at: {index_path}")

        raw_distances = []
        raw_indices = []

        if HAS_FAISS and os.path.exists(index_path):
            try:
                index = faiss.read_index(index_path)
                actual_k = min(top_k, index.ntotal)
                if actual_k <= 0:
                    return [], []

                query_2d = np.ascontiguousarray(query_vector.reshape(1, -1), dtype=np.float32)
                distances, indices = index.search(query_2d, actual_k)
                raw_distances = distances[0]
                raw_indices = indices[0]
            except Exception as e:
                logger.warning(f"FAISS read_index encountered an error ({e}). Falling back to NumPy search.")
                raw_distances, raw_indices = self._numpy_search(index_path, query_vector, top_k)
        else:
            raw_distances, raw_indices = self._numpy_search(index_path, query_vector, top_k)

        valid_scores = []
        valid_indices = []

        for dist, idx in zip(raw_distances, raw_indices):
            if idx != -1:
                score = max(0.0, min(1.0, float(dist)))
                valid_scores.append(round(score, 4))
                valid_indices.append(int(idx))

        return valid_scores, valid_indices

    def _numpy_search(
        self,
        index_path: str,
        query_vector: np.ndarray,
        top_k: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """NumPy matrix dot-product fallback (mathematically identical to IndexFlatIP)."""
        target_path = index_path
        if not os.path.exists(target_path):
            target_path = index_path + '.npy'

        if not os.path.exists(target_path):
            return np.array([]), np.array([])

        try:
            embeddings = np.load(target_path)
            q = query_vector.flatten().astype(np.float32)
            # Cosine similarity for normalized vectors is dot product
            sims = np.dot(embeddings, q)
            k = min(top_k, len(sims))
            top_k_indices = np.argsort(sims)[::-1][:k]
            top_k_scores = sims[top_k_indices]
            return top_k_scores, top_k_indices
        except Exception as e:
            logger.error(f"NumPy fallback search failed: {e}")
            return np.array([]), np.array([])

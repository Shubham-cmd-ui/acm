import os
from typing import Tuple, List
import faiss
import numpy as np

class FaissVectorStore:
    """
    Manages FAISS dense vector indices scoped per document.
    Uses IndexFlatIP with L2-normalized embeddings for exact Cosine Similarity.
    """

    def __init__(self, dimension: int = 3072):
        self.dimension = dimension

    def create_and_save_index(self, embeddings: np.ndarray, index_path: str) -> None:
        """
        Builds a new FAISS IndexFlatIP from normalized chunk embeddings
        and serializes it to the specified index_path.
        
        Parameters:
            embeddings: 2D float32 numpy array of shape (num_chunks, dimension).
            index_path: File system path where .faiss binary is saved.
        """
        if embeddings.ndim != 2:
            raise ValueError(f"Embeddings array must be 2D, received ndim={embeddings.ndim}")

        num_vectors, dim = embeddings.shape
        if dim != self.dimension:
            # Dynamically adapt to actual embedding dimension if it differs
            self.dimension = dim

        # Ensure float32 format for FAISS
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        # IndexFlatIP calculates inner product: for normalized vectors, IP == Cosine Similarity
        index = faiss.IndexFlatIP(self.dimension)
        index.add(embeddings)

        dir_name = os.path.dirname(index_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # Write index to disk
        faiss.write_index(index, index_path)

    def search(
        self,
        index_path: str,
        query_vector: np.ndarray,
        top_k: int = 4
    ) -> Tuple[List[float], List[int]]:
        """
        Loads the document's scoped FAISS index and retrieves the top-k most similar chunks.
        
        Returns:
            (scores, indices):
            - scores: list of cosine similarity floats (e.g. 0.85).
            - indices: list of 0-based integer chunk indices matching DocumentChunk.chunk_index.
        """
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index file not found at: {index_path}")

        # Load persisted index
        index = faiss.read_index(index_path)

        # Bound top_k by total indexed elements
        actual_k = min(top_k, index.ntotal)
        if actual_k <= 0:
            return [], []

        # Prepare 2D query vector
        query_vector = np.ascontiguousarray(query_vector.reshape(1, -1), dtype=np.float32)

        # Perform similarity search
        distances, indices = index.search(query_vector, actual_k)

        # Filter out invalid (-1) indices if any
        valid_scores = []
        valid_indices = []

        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1:
                # Clamp similarity score between 0.0 and 1.0 for UI friendliness
                score = max(0.0, min(1.0, float(dist)))
                valid_scores.append(round(score, 4))
                valid_indices.append(int(idx))

        return valid_scores, valid_indices

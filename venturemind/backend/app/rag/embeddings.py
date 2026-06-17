"""Embedding function selection for the RAG layer.

We default to ChromaDB's bundled embedding model (all-MiniLM-L6-v2 via ONNX),
which runs locally with no API key — ideal for development and self-hosting.

To move to a hosted embedder in production (better recall, no local CPU cost),
swap the return value here for one of chromadb's other embedding functions, e.g.:

    embedding_functions.OpenAIEmbeddingFunction(api_key=..., model_name=...)
    # Anthropic does not offer embeddings; their recommended partner is Voyage AI:
    embedding_functions.VoyageAIEmbeddingFunction(api_key=..., model_name="voyage-3")

Keeping this isolated means the collection, ingestion, and retrieval code never
change when the embedder does — only this one function does.
"""
from __future__ import annotations

from chromadb.utils import embedding_functions


def get_embedding_function():
    """Return the embedding function used for both ingestion and queries.

    The SAME function must be used on write and read, or vectors live in
    different spaces and similarity becomes meaningless.
    """
    return embedding_functions.DefaultEmbeddingFunction()

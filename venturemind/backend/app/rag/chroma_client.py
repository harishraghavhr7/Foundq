"""ChromaDB client and the `startups` collection accessor.

A single persistent client is reused across the process. `get_collection()`
returns the `startups` collection, creating it on first use with:
  - the shared embedding function (see embeddings.py), and
  - cosine distance ("hnsw:space": "cosine"), so distances map cleanly to a
    [0, 1] similarity via `similarity = 1 - distance`.
"""
from __future__ import annotations

import chromadb

from app.config import settings
from app.rag.embeddings import get_embedding_function

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    """Lazily create and cache a persistent Chroma client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def get_collection():
    """Get (or create) the `startups` collection with cosine similarity."""
    return get_client().get_or_create_collection(
        name=settings.chroma_collection,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

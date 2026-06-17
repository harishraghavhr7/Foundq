"""Retrieval service: semantic competitor search over the `startups` collection.

Given a startup's title + description, embed the query with the same function used
at ingestion, run a nearest-neighbour search in Chroma, and return the top-K most
similar startups as "competitors".
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rag.chroma_client import get_collection


@dataclass(frozen=True)
class Competitor:
    startup_name: str
    industry: str
    description: str
    similarity: float  # cosine similarity in [0, 1]; higher = more similar


def find_competitors(
    title: str,
    description: str,
    industry: str | None = None,
    top_k: int = 5,
    exclude_id: str | None = None,
) -> list[Competitor]:
    """Return the top-K most semantically similar startups.

    industry   : optional metadata filter to keep matches within one sector.
    exclude_id : skip this id in results (use when the query is itself stored,
                 so a startup isn't returned as its own competitor).
    """
    collection = get_collection()
    query_text = f"{title}\n{description}".strip()

    # Over-fetch by one so a self-match can be dropped without shrinking results.
    n_results = top_k + 1 if exclude_id else top_k

    result = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where={"industry": industry} if industry else None,
        include=["metadatas", "distances"],
    )

    # Chroma returns one inner list per query; we only sent one query.
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]

    competitors: list[Competitor] = []
    for meta, distance, _id in zip(metadatas, distances, ids):
        if exclude_id and _id == exclude_id:
            continue
        # Cosine distance in [0, 2] -> similarity in [0, 1]; clamp for safety.
        similarity = round(max(0.0, 1.0 - float(distance)), 4)
        competitors.append(
            Competitor(
                startup_name=meta.get("startup_name", ""),
                industry=meta.get("industry", ""),
                description=meta.get("description", ""),
                similarity=similarity,
            )
        )

    return competitors[:top_k]

"""Integration tests for the ChromaDB competitor-search flow.

Skipped automatically if `chromadb` isn't installed. Uses an EphemeralClient
(in-memory) so tests never touch the on-disk persistent store.
"""
import pytest

chromadb = pytest.importorskip("chromadb")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.rag import chroma_client  # noqa: E402
from app.rag.ingestion import ingest_startups, load_csv, load_seed  # noqa: E402
from app.rag.retrieval import find_competitors  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def ephemeral_chroma(monkeypatch):
    monkeypatch.setattr(chroma_client, "_client", chromadb.EphemeralClient())
    yield
    monkeypatch.setattr(chroma_client, "_client", None)


def test_ingest_and_search_returns_top_5():
    assert ingest_startups(load_seed()) >= 5

    results = find_competitors(
        title="LearnGenie",
        description="AI tutoring app that personalizes courses for students preparing for exams.",
        top_k=5,
    )
    assert len(results) == 5
    # EdTech seed entries should surface first for an EdTech query.
    assert results[0].industry == "EdTech"
    # Results are ordered by descending similarity.
    sims = [c.similarity for c in results]
    assert sims == sorted(sims, reverse=True)


def test_industry_filter_restricts_results():
    ingest_startups(load_seed())
    results = find_competitors(
        title="PayX",
        description="Instant mobile payments and wallet for peer-to-peer transfers.",
        industry="FinTech",
        top_k=5,
    )
    assert results, "expected at least one FinTech match"
    assert all(c.industry == "FinTech" for c in results)


def test_load_csv_has_expected_shape():
    records = load_csv()
    assert len(records) >= 5
    # Every record maps the CSV columns to the internal record shape.
    assert {"startup_name", "industry", "description"} <= set(records[0])
    assert any(r["startup_name"] == "Interviewing.io" for r in records)


def test_csv_ingest_surfaces_interviewing_io():
    # Requirement #1 (load startups.csv) feeding the end-to-end search.
    assert ingest_startups(load_csv()) >= 5
    results = find_competitors(
        title="MockLoop",
        description="A platform to practice coding interviews with real engineers before applying for software jobs.",
        top_k=5,
    )
    names = [c.startup_name for c in results]
    assert "Interviewing.io" in names
    # Every result carries a cosine similarity in [0, 1].
    assert all(0.0 <= c.similarity <= 1.0 for c in results)


def test_endpoint_returns_competitor_contract():
    ingest_startups(load_csv())
    res = client.post(
        "/competitors",
        json={
            "title": "MockLoop",
            "description": "Practice coding interviews with real engineers before applying for jobs.",
            "top_k": 3,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["query_title"] == "MockLoop"
    assert 1 <= len(body["competitors"]) <= 3
    first = body["competitors"][0]
    assert set(first.keys()) == {"startup_name", "industry", "description", "similarity"}
    assert 0.0 <= first["similarity"] <= 1.0

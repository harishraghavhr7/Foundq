"""Tests for the Gemini market-analysis service and its endpoint.

`_call_gemini` is the only impure seam (the SDK + network call); every test stubs
it. As a result the whole suite runs with no API key, no network, and without
`google-genai` or `chromadb` installed — the same hermetic style as the other
feature tests in this project.
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import market_analyzer
from app.services.market_analyzer import (
    AnalyzerConfigError,
    _CompetitorInsightLLM,
    _MarketAnalysisLLM,
    analyze_market,
)

client = TestClient(app)


@dataclass(frozen=True)
class FakeCompetitor:
    """Structurally matches app.rag.retrieval.Competitor (what the service needs)."""

    startup_name: str
    industry: str
    description: str
    similarity: float


COMPS = [
    FakeCompetitor("LearnSphere", "EdTech", "Adaptive AI K-12 curriculum.", 0.91),
    FakeCompetitor("EduNest", "EdTech", "Tutoring marketplace with live video.", 0.86),
]


def _llm_result(extra_names: tuple[str, ...] = ()) -> _MarketAnalysisLLM:
    """A fake Gemini result: insights for every real competitor, plus any
    `extra_names` to simulate the model hallucinating an out-of-context company."""
    insights = [
        _CompetitorInsightLLM(competitor_name=c.startup_name, relation=f"about {c.startup_name}")
        for c in COMPS
    ]
    insights += [
        _CompetitorInsightLLM(competitor_name=n, relation="fabricated") for n in extra_names
    ]
    return _MarketAnalysisLLM(
        market_summary="Crowded EdTech tutoring space.",
        competitor_analysis=insights,
        strengths=["Personalization"],
        weaknesses=["Crowded market"],
        sufficient_context=True,
    )


# --- service unit tests ---------------------------------------------------

def test_empty_competitors_short_circuits(monkeypatch):
    """No retrieved context => return an explicit gap, never call the model."""

    def boom(_prompt):
        raise AssertionError("the model must not be called without retrieved context")

    monkeypatch.setattr(market_analyzer, "_call_gemini", boom)

    result = analyze_market(
        idea_title="X", idea_description="Y", industry=None, competitors=[]
    )
    assert result.grounded is False
    assert result.competitor_analysis == []
    assert result.used_competitors == []
    assert result.model == ""


def test_maps_and_filters_hallucinated_competitor(monkeypatch):
    """A competitor the model invents (not in the retrieved set) is dropped."""
    monkeypatch.setattr(
        market_analyzer, "_call_gemini", lambda _p: _llm_result(extra_names=("GhostCorp",))
    )

    result = analyze_market(
        idea_title="LearnGenie",
        idea_description="AI tutor for exam prep",
        industry="EdTech",
        competitors=COMPS,
    )

    names = {ci.competitor_name for ci in result.competitor_analysis}
    assert names == {"LearnSphere", "EduNest"}  # GhostCorp filtered out
    assert result.used_competitors == ["LearnSphere", "EduNest"]
    assert result.grounded is True
    assert result.strengths == ["Personalization"]
    assert result.weaknesses == ["Crowded market"]


def test_name_match_is_case_and_space_insensitive(monkeypatch):
    """Model returns ' learnsphere ' — still matched to the retrieved 'LearnSphere'."""
    llm = _MarketAnalysisLLM(
        market_summary="s",
        competitor_analysis=[_CompetitorInsightLLM(competitor_name="  learnsphere ", relation="r")],
        strengths=[],
        weaknesses=[],
        sufficient_context=True,
    )
    monkeypatch.setattr(market_analyzer, "_call_gemini", lambda _p: llm)

    result = analyze_market(
        idea_title="X", idea_description="Y", industry=None, competitors=COMPS
    )
    # Canonicalised back to the retrieved spelling.
    assert [ci.competitor_name for ci in result.competitor_analysis] == ["LearnSphere"]


def test_grounded_false_when_all_competitors_hallucinated(monkeypatch):
    """If nothing the model named is real, the result is not considered grounded."""
    bad = _MarketAnalysisLLM(
        market_summary="...",
        competitor_analysis=[_CompetitorInsightLLM(competitor_name="GhostCorp", relation="x")],
        strengths=[],
        weaknesses=[],
        sufficient_context=True,
    )
    monkeypatch.setattr(market_analyzer, "_call_gemini", lambda _p: bad)

    result = analyze_market(
        idea_title="X", idea_description="Y", industry=None, competitors=COMPS
    )
    assert result.competitor_analysis == []
    assert result.grounded is False


def test_missing_api_key_raises_config_error(monkeypatch):
    """No GEMINI_API_KEY => a clear config error, surfaced as 503 by the route."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    market_analyzer._get_client.cache_clear()
    with pytest.raises(AnalyzerConfigError):
        market_analyzer._get_client()


# --- endpoint test --------------------------------------------------------

def test_endpoint_grounded_analysis(monkeypatch):
    """Full route → retrieval → service → mapping, with only the SDK call stubbed.

    `app.rag.retrieval` can't be imported here (no chromadb), so we inject a fake
    module providing `find_competitors`; the route imports it lazily and picks up
    the fake from sys.modules.
    """
    fake_retrieval = types.ModuleType("app.rag.retrieval")
    fake_retrieval.find_competitors = lambda **kwargs: list(COMPS)
    monkeypatch.setitem(sys.modules, "app.rag.retrieval", fake_retrieval)
    monkeypatch.setattr(
        market_analyzer, "_call_gemini", lambda _p: _llm_result(extra_names=("GhostCorp",))
    )

    res = client.post(
        "/analyze-market",
        json={
            "title": "LearnGenie",
            "description": "AI tutor that personalizes courses for exam prep.",
            "industry": "EdTech",
            "top_k": 5,
        },
    )
    assert res.status_code == 200
    body = res.json()

    assert body["grounded"] is True
    assert body["idea_title"] == "LearnGenie"
    # The exact retrieved context is echoed back for client-side auditing.
    assert {c["startup_name"] for c in body["retrieved_competitors"]} == {"LearnSphere", "EduNest"}
    # Hallucinated competitor never reaches the client.
    insight_names = {ci["competitor_name"] for ci in body["competitor_analysis"]}
    assert insight_names == {"LearnSphere", "EduNest"}
    assert set(body.keys()) == {
        "idea_title",
        "industry",
        "market_summary",
        "competitor_analysis",
        "strengths",
        "weaknesses",
        "grounded",
        "model",
        "retrieved_competitors",
    }


def test_endpoint_validation_error():
    """Empty idea fields are rejected by the schema before any work happens."""
    res = client.post("/analyze-market", json={"title": "", "description": ""})
    assert res.status_code == 422

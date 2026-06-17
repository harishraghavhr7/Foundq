"""Tests for the SWOT Analysis Engine (Gemini) — service, prompt, and endpoint.

`_call_gemini` is the only impure seam (the SDK + network call); every test that
exercises the model stubs it. The prompt builder is pure and tested directly. As
a result the whole suite runs with no API key, no network, and without
`google-genai` installed — the same hermetic style as the other feature tests.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.prompts.swot_analysis import SYSTEM_INSTRUCTION, build_user_prompt
from app.services import swot_analyzer
from app.services.swot_analyzer import (
    SwotConfigError,
    _SwotAnalysisLLM,
    _SwotItemLLM,
    generate_swot,
)

client = TestClient(app)


@dataclass(frozen=True)
class FakeCompetitor:
    """Structurally matches schemas.SwotCompetitorIn (what the service needs)."""

    name: str
    description: str | None


COMPS = [
    FakeCompetitor("LearnSphere", "Adaptive AI K-12 curriculum."),
    FakeCompetitor("EduNest", "Tutoring marketplace with live video."),
]


def _item(point: str) -> _SwotItemLLM:
    return _SwotItemLLM(point=point, rationale=f"because {point.lower()}")


def _llm_result(sufficient: bool = True) -> _SwotAnalysisLLM:
    """A fake Gemini SWOT result — one item per quadrant is enough for mapping tests."""
    return _SwotAnalysisLLM(
        strengths=[_item("Adaptive personalization")],
        weaknesses=[_item("Crowded market")],
        opportunities=[_item("Rising exam-prep demand")],
        threats=[_item("Well-funded incumbents")],
        sufficient_context=sufficient,
    )


# --- prompt builder unit tests (pure, no SDK) -----------------------------

def test_system_instruction_encodes_quadrant_discipline():
    # The internal/external split is the load-bearing rule of a SWOT.
    assert "INTERNAL" in SYSTEM_INSTRUCTION
    assert "EXTERNAL" in SYSTEM_INSTRUCTION


def test_prompt_includes_all_supplied_context():
    prompt = build_user_prompt(
        idea_title="LearnGenie",
        idea_description="AI tutor for exam prep.",
        industry="EdTech",
        competitors=COMPS,
        market_context="EdTech market growing 18% CAGR.",
    )
    assert "LearnGenie" in prompt
    assert "EdTech" in prompt
    assert "LearnSphere" in prompt and "EduNest" in prompt
    assert "18% CAGR" in prompt


def test_prompt_marks_absent_context_explicitly():
    # Empty blocks must read as a real absence of evidence, not be omitted.
    prompt = build_user_prompt(
        idea_title="Zorp",
        idea_description="A thing.",
        industry=None,
        competitors=[],
        market_context=None,
    )
    assert "(No competitors were provided.)" in prompt
    assert "(No market context was provided.)" in prompt
    assert "stated_industry" not in prompt  # omitted when industry is None


# --- service unit tests ---------------------------------------------------

def test_generate_swot_maps_all_quadrants(monkeypatch):
    monkeypatch.setattr(swot_analyzer, "_call_gemini", lambda _p: _llm_result())

    result = generate_swot(
        idea_title="LearnGenie",
        idea_description="AI tutor for exam prep.",
        industry="EdTech",
        competitors=COMPS,
        market_context="Growing fast.",
    )
    assert [i.point for i in result.strengths] == ["Adaptive personalization"]
    assert [i.point for i in result.weaknesses] == ["Crowded market"]
    assert [i.point for i in result.opportunities] == ["Rising exam-prep demand"]
    assert [i.point for i in result.threats] == ["Well-funded incumbents"]
    assert result.sufficient_context is True
    assert result.model == settings.gemini_model


def test_generate_swot_calls_model_even_without_context(monkeypatch):
    """A SWOT of the bare idea is valid — the model is still called (unlike
    /analyze-market, which short-circuits on an empty competitor set)."""
    called = {"n": 0}

    def fake(_prompt):
        called["n"] += 1
        return _llm_result(sufficient=False)

    monkeypatch.setattr(swot_analyzer, "_call_gemini", fake)

    result = generate_swot(
        idea_title="Zorp",
        idea_description="A thing that does stuff.",
        industry=None,
        competitors=[],
        market_context=None,
    )
    assert called["n"] == 1
    assert result.sufficient_context is False


def test_missing_api_key_raises_config_error(monkeypatch):
    """No GEMINI_API_KEY => a clear config error, surfaced as 503 by the route."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    swot_analyzer._get_client.cache_clear()
    with pytest.raises(SwotConfigError):
        swot_analyzer._get_client()


# --- endpoint tests -------------------------------------------------------

def test_endpoint_returns_contract(monkeypatch):
    monkeypatch.setattr(swot_analyzer, "_call_gemini", lambda _p: _llm_result())

    res = client.post(
        "/swot-analysis",
        json={
            "title": "LearnGenie",
            "description": "AI tutor that personalizes courses for exam prep.",
            "industry": "EdTech",
            "competitors": [{"name": "LearnSphere", "description": "Adaptive curriculum."}],
            "market_context": "EdTech tutoring growing ~18% CAGR.",
        },
    )
    assert res.status_code == 200
    body = res.json()

    assert body["idea_title"] == "LearnGenie"
    assert body["sufficient_context"] is True
    for quadrant in ("strengths", "weaknesses", "opportunities", "threats"):
        assert len(body[quadrant]) >= 1
        assert set(body[quadrant][0].keys()) == {"point", "rationale"}
    assert set(body.keys()) == {
        "idea_title",
        "industry",
        "strengths",
        "weaknesses",
        "opportunities",
        "threats",
        "sufficient_context",
        "model",
    }


def test_endpoint_works_with_idea_only(monkeypatch):
    """competitors and market_context are optional — the idea alone is enough."""
    monkeypatch.setattr(swot_analyzer, "_call_gemini", lambda _p: _llm_result(sufficient=False))

    res = client.post(
        "/swot-analysis",
        json={"title": "Zorp", "description": "A thing that does stuff."},
    )
    assert res.status_code == 200
    assert res.json()["sufficient_context"] is False


def test_endpoint_validation_error():
    """Empty idea fields are rejected by the schema before any work happens."""
    res = client.post("/swot-analysis", json={"title": "", "description": ""})
    assert res.status_code == 422

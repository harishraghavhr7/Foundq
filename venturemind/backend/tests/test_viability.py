"""Tests for the Startup Viability Scoring Engine (Feature 3) and its endpoint.

Like the industry suite, the endpoint tests mount the feature's own router on a
minimal FastAPI app instead of importing ``app.main``. This keeps the suite
hermetic: it exercises the real route, schemas and scorer with no PostgreSQL or
RAG/vector-store dependency, so Feature 3 verifies independently of the rest.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.score import router
from app.services.viability_scorer import (
    DEFAULT_WEIGHTS,
    ScoringConfig,
    rating_for,
    score_startup,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


# --- The model -------------------------------------------------------------

def test_perfect_inputs_score_100():
    # All upside maxed (competition = 0 => favorability 100), zero risk.
    r = score_startup(demand=100, competition=0, scalability=100, innovation=100, risk=0)
    assert r.upside_score == 100.0
    assert r.risk_multiplier == 1.0
    assert r.final_score == 100.0
    assert r.rating == "Highly Viable"


def test_max_risk_halves_a_perfect_upside():
    # λ = 0.5 means risk = 100 removes exactly half of the upside.
    r = score_startup(demand=100, competition=0, scalability=100, innovation=100, risk=100)
    assert r.upside_score == 100.0
    assert r.risk_multiplier == 0.5
    assert r.final_score == 50.0
    assert r.rating == "Moderate"


def test_competition_is_inverse():
    # A more crowded market (higher competition) must lower the score, all else equal.
    crowded = score_startup(demand=70, competition=90, scalability=70, innovation=70, risk=30)
    open_market = score_startup(demand=70, competition=10, scalability=70, innovation=70, risk=30)
    assert open_market.final_score > crowded.final_score
    comp_factor = next(f for f in open_market.breakdown if f.factor == "Competition")
    assert comp_factor.direction == "inverse"
    assert comp_factor.adjusted == 90.0  # 100 - 10


def test_risk_is_monotonic_discount():
    base = dict(demand=80, competition=40, scalability=70, innovation=60)
    low = score_startup(**base, risk=10)
    mid = score_startup(**base, risk=50)
    high = score_startup(**base, risk=90)
    # Same upside, strictly decreasing final score as risk rises.
    assert low.upside_score == mid.upside_score == high.upside_score
    assert low.final_score > mid.final_score > high.final_score


def test_breakdown_reconciles_to_score():
    r = score_startup(demand=82, competition=55, scalability=66, innovation=71, risk=44)
    # Upside factor contributions sum to the pre-risk upside (within rounding).
    assert sum(f.contribution for f in r.breakdown) == pytest.approx(r.upside_score, abs=0.1)
    # Final equals upside * multiplier (within rounding).
    assert r.final_score == pytest.approx(r.upside_score * r.risk_multiplier, abs=0.1)
    # Risk discount accounting is consistent.
    assert r.risk_discount_points == pytest.approx(r.upside_score - r.final_score, abs=0.1)
    # All four upside factors are itemized; max_contribution = weight * 100.
    assert len(r.breakdown) == 4
    for f in r.breakdown:
        assert f.max_contribution == pytest.approx(f.weight * 100, abs=0.01)
        assert f.points_lost == pytest.approx(f.max_contribution - f.contribution, abs=0.05)


@pytest.mark.parametrize(
    "scores",
    [
        dict(demand=0, competition=0, scalability=0, innovation=0, risk=0),
        dict(demand=100, competition=100, scalability=100, innovation=100, risk=100),
        dict(demand=37, competition=88, scalability=12, innovation=63, risk=51),
    ],
)
def test_score_always_in_range(scores):
    r = score_startup(**scores)
    assert 0.0 <= r.final_score <= 100.0
    assert 0.0 <= r.upside_score <= 100.0


def test_rating_bands():
    assert rating_for(85) == "Highly Viable"
    assert rating_for(70) == "Viable"
    assert rating_for(55) == "Moderate"
    assert rating_for(40) == "Weak"
    assert rating_for(20) == "Not Viable"


# --- Config validation -----------------------------------------------------

def test_default_weights_sum_to_one():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        ScoringConfig(weights={"demand": 0.5, "scalability": 0.5, "innovation": 0.5, "competition": 0.5})


def test_risk_severity_bounds():
    with pytest.raises(ValueError):
        ScoringConfig(risk_severity=1.5)


def test_inputs_must_be_in_range():
    with pytest.raises(ValueError):
        score_startup(demand=150, competition=0, scalability=0, innovation=0, risk=0)


# --- The endpoint ----------------------------------------------------------

def test_endpoint_returns_contract():
    res = client.post(
        "/score-viability",
        json={"demand": 92, "competition": 20, "scalability": 88, "innovation": 85, "risk": 12},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["final_score"] == 82.0
    assert body["rating"] == "Highly Viable"
    assert 0.0 <= body["final_score"] <= 100.0
    assert len(body["breakdown"]) == 4
    assert {"final_score", "rating", "upside_score", "risk", "risk_severity",
            "risk_multiplier", "risk_discount_points", "breakdown", "summary"} == set(body)


def test_endpoint_validation_error():
    res = client.post(
        "/score-viability",
        json={"demand": 120, "competition": 20, "scalability": 88, "innovation": 85, "risk": 12},
    )
    assert res.status_code == 422

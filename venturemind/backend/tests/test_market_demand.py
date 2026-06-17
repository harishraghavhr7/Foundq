"""Tests for the Market Demand Score engine and its endpoint."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.market_demand import (
    SATURATION_SCORE,
    UNPROVEN_FLOOR,
    score_market_demand,
)

client = TestClient(app)


def test_hot_market_scores_high():
    # Strong, growing, healthy-but-not-crowded HealthTech market.
    result = score_market_demand(
        industry="HealthTech",
        competitor_count=6,      # exactly HealthTech's sweet spot -> competition C = 100
        search_trend=60,         # +60% search momentum
        market_growth=30,        # 30% CAGR
    )
    assert result.demand_score >= 80
    assert result.band in ("High", "Very High")
    assert 0 <= result.demand_score <= 100


def test_weak_market_scores_low():
    # Declining, shrinking, saturated E-commerce market.
    result = score_market_demand(
        industry="E-commerce",
        competitor_count=50,     # E-commerce saturation count -> competition C = SATURATION_SCORE
        search_trend=-40,        # search interest falling
        market_growth=-5,        # market contracting
    )
    assert result.demand_score <= 30
    assert result.band in ("Very Low", "Low")


def test_search_trend_is_monotonic():
    base = dict(industry="SaaS", competitor_count=12, market_growth=10)
    low = score_market_demand(search_trend=0, **base).demand_score
    high = score_market_demand(search_trend=80, **base).demand_score
    assert high > low


def test_market_growth_is_monotonic():
    base = dict(industry="SaaS", competitor_count=12, search_trend=10)
    low = score_market_demand(market_growth=-10, **base).demand_score
    high = score_market_demand(market_growth=40, **base).demand_score
    assert high > low


def test_competition_is_inverted_u():
    # The sweet spot (c*=12 for SaaS) must beat both an empty and a saturated market.
    base = dict(industry="SaaS", search_trend=20, market_growth=20)
    empty = score_market_demand(competitor_count=0, **base)
    sweet = score_market_demand(competitor_count=12, **base)
    saturated = score_market_demand(competitor_count=60, **base)

    assert sweet.competition_score == 100.0
    assert empty.competition_score == UNPROVEN_FLOOR
    assert round(saturated.competition_score, 1) == SATURATION_SCORE
    # ... and that ordering propagates to the final score.
    assert sweet.demand_score > empty.demand_score
    assert sweet.demand_score > saturated.demand_score


def test_unknown_industry_falls_back_to_default():
    result = score_market_demand(
        industry="Quantum Teleportation Widgets",
        competitor_count=5,
        search_trend=10,
        market_growth=10,
    )
    assert result.industry_matched == "default"
    assert 0 <= result.demand_score <= 100


def test_industry_alias_resolves():
    assert score_market_demand("ecommerce", 5, 10, 10).industry_matched == "e-commerce"
    assert score_market_demand("HEALTH TECH", 5, 10, 10).industry_matched == "healthtech"


def test_weights_sum_to_one():
    result = score_market_demand("FinTech", 5, 10, 10)
    assert abs(sum(result.weights.values()) - 1.0) < 1e-6


def test_extreme_inputs_stay_in_range():
    # Absurd inputs must clamp, never overflow the 0-100 contract.
    hot = score_market_demand("HealthTech", 0, 100000, 100000)
    cold = score_market_demand("E-commerce", 100000, -100000, -100000)
    assert 0 <= hot.demand_score <= 100
    assert 0 <= cold.demand_score <= 100


def test_endpoint_returns_contract():
    res = client.post(
        "/market-demand-score",
        json={
            "industry": "FinTech",
            "competitor_count": 6,
            "search_trend": 35,
            "market_growth": 22,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == {"demand_score", "band", "breakdown"}
    assert 0.0 <= body["demand_score"] <= 100.0
    breakdown = body["breakdown"]
    assert set(breakdown.keys()) == {
        "industry_matched",
        "trend_score",
        "growth_score",
        "competition_score",
        "weighted_base",
        "multiplier",
        "weights",
    }
    assert breakdown["industry_matched"] == "fintech"


def test_endpoint_rejects_negative_competitor_count():
    res = client.post(
        "/market-demand-score",
        json={
            "industry": "SaaS",
            "competitor_count": -1,
            "search_trend": 10,
            "market_growth": 10,
        },
    )
    assert res.status_code == 422


def test_endpoint_rejects_missing_field():
    res = client.post(
        "/market-demand-score",
        json={"industry": "SaaS", "competitor_count": 3, "search_trend": 10},
    )
    assert res.status_code == 422

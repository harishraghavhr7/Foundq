"""Router for the Market Demand Score engine (Feature 4).

Self-contained like the industry and viability routers: it imports only the
Pydantic schemas and the pure-logic scorer — never the database or RAG layers.
That keeps the /market-demand-score endpoint importable, deployable and testable
in isolation, with no PostgreSQL or vector-store dependency.

The 0-100 demand_score this returns is a natural upstream input to the `demand`
field of POST /score-viability.
"""
from fastapi import APIRouter

from app import schemas
from app.services.market_demand import score_market_demand

router = APIRouter(tags=["market-demand"])


@router.post("/market-demand-score", response_model=schemas.MarketDemandResponse)
def market_demand_endpoint(payload: schemas.MarketDemandRequest) -> schemas.MarketDemandResponse:
    """Compute the 0-100 Market Demand Score with a full, explainable breakdown."""
    result = score_market_demand(
        industry=payload.industry,
        competitor_count=payload.competitor_count,
        search_trend=payload.search_trend,
        market_growth=payload.market_growth,
    )
    return schemas.MarketDemandResponse(
        demand_score=result.demand_score,
        band=result.band,
        breakdown=schemas.MarketDemandBreakdown(
            industry_matched=result.industry_matched,
            trend_score=result.trend_score,
            growth_score=result.growth_score,
            competition_score=result.competition_score,
            weighted_base=result.weighted_base,
            multiplier=result.multiplier,
            weights=result.weights,
        ),
    )

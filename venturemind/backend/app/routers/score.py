"""Router for the Startup Viability Scoring Engine (Feature 3).

Self-contained like the industry router: it imports only the Pydantic schemas
and the pure-logic scorer — never the database or RAG layers. That keeps the
/score-viability endpoint importable, deployable and testable in isolation, with
no PostgreSQL or vector-store dependency.
"""
from fastapi import APIRouter

from app import schemas
from app.services.viability_scorer import score_startup

router = APIRouter(tags=["viability"])


@router.post("/score-viability", response_model=schemas.ViabilityResponse)
def score_viability_endpoint(payload: schemas.ViabilityRequest) -> schemas.ViabilityResponse:
    """Compute the 0-100 Startup Viability Score with a full breakdown."""
    result = score_startup(
        demand=payload.demand,
        competition=payload.competition,
        scalability=payload.scalability,
        innovation=payload.innovation,
        risk=payload.risk,
    )
    return schemas.ViabilityResponse(
        final_score=result.final_score,
        rating=result.rating,
        upside_score=result.upside_score,
        risk=result.risk,
        risk_severity=result.risk_severity,
        risk_multiplier=result.risk_multiplier,
        risk_discount_points=result.risk_discount_points,
        breakdown=[
            schemas.FactorBreakdown(
                factor=f.factor,
                raw=f.raw,
                direction=f.direction,
                adjusted=f.adjusted,
                weight=f.weight,
                contribution=f.contribution,
                max_contribution=f.max_contribution,
                points_lost=f.points_lost,
            )
            for f in result.breakdown
        ],
        summary=result.summary,
    )

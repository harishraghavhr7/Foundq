"""Router for SWOT analysis (Gemini generation).

A self-contained generative feature: it takes the startup idea plus the
caller-supplied competitors and market context and asks Gemini to produce a
four-quadrant SWOT (``app.services.swot_analyzer``). Unlike /analyze-market it
does NOT retrieve competitors, so it depends on neither the database nor the RAG
layer and stays importable and testable in isolation.

Flow
----
    POST /swot-analysis
        │  idea (title, description, optional industry)
        │  + competitors (optional)  + market_context (optional)
        ▼
    generate_swot  ──►  Gemini, grounded in the supplied inputs
        ▼
    SwotAnalysisResponse  (the four quadrants + honesty signal + model id)

Failure mapping mirrors /analyze-market: a missing API key is a configuration
problem (503, the service is simply not enabled here); an upstream model/parse
failure is a bad gateway (502). Neither leaks a stack trace to the client.
"""
from fastapi import APIRouter, HTTPException, status

from app import schemas

router = APIRouter(tags=["swot"])


@router.post("/swot-analysis", response_model=schemas.SwotAnalysisResponse)
def swot_analysis_endpoint(
    payload: schemas.SwotAnalysisRequest,
) -> schemas.SwotAnalysisResponse:
    """Generate a grounded SWOT analysis from the idea and supplied context."""
    try:
        from app.services.swot_analyzer import (
            SwotConfigError,
            SwotError,
            generate_swot,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SWOT analysis unavailable: google-genai not installed.",
        )

    try:
        analysis = generate_swot(
            idea_title=payload.title,
            idea_description=payload.description,
            industry=payload.industry,
            competitors=payload.competitors,
            market_context=payload.market_context,
        )
    except SwotConfigError as exc:
        # The feature isn't configured (no GEMINI_API_KEY) — not the caller's fault.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except SwotError as exc:
        # The model call or its parsing failed upstream.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    def _out(items) -> list[schemas.SwotItemOut]:
        return [schemas.SwotItemOut(point=i.point, rationale=i.rationale) for i in items]

    return schemas.SwotAnalysisResponse(
        idea_title=payload.title,
        industry=payload.industry,
        strengths=_out(analysis.strengths),
        weaknesses=_out(analysis.weaknesses),
        opportunities=_out(analysis.opportunities),
        threats=_out(analysis.threats),
        sufficient_context=analysis.sufficient_context,
        model=analysis.model,
    )

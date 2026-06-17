"""Router for grounded market analysis (Gemini RAG generation).

This is the "generate" half of Retrieval-Augmented Generation and the one router
that intentionally depends on the RAG layer: it first *retrieves* competitors for
the idea (``app.rag.retrieval.find_competitors``), then asks Gemini to *generate*
a four-part analysis grounded only in those competitors
(``app.services.market_analyzer``).

Flow
----
    POST /analyze-market
        │  idea (title, description, optional industry)
        ▼
    find_competitors  ──►  top-K competitors from the Chroma knowledge base
        │
        ▼
    analyze_market    ──►  Gemini, constrained to the retrieved context
        │
        ▼
    MarketAnalysisResponse  (analysis + the competitors it was grounded in)

Failure mapping: a missing API key is a configuration problem (503, the service
is simply not enabled here); an upstream model/parse failure is a bad gateway
(502). Neither leaks a stack trace to the client.
"""
from fastapi import APIRouter, HTTPException, status

from app import schemas

router = APIRouter(tags=["market-analysis"])


@router.post("/analyze-market", response_model=schemas.MarketAnalysisResponse)
def analyze_market_endpoint(
    payload: schemas.AnalyzeMarketRequest,
) -> schemas.MarketAnalysisResponse:
    """Retrieve competitors for the idea, then generate a grounded analysis."""
    try:
        from app.rag.retrieval import find_competitors
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market analysis unavailable: chromadb / sentence-transformers not installed.",
        )

    try:
        from app.services.market_analyzer import (
            AnalyzerConfigError,
            AnalyzerError,
            analyze_market,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market analysis unavailable: google-genai not installed.",
        )

    competitors = find_competitors(
        title=payload.title,
        description=payload.description,
        industry=payload.industry,
        top_k=payload.top_k,
    )

    try:
        analysis = analyze_market(
            idea_title=payload.title,
            idea_description=payload.description,
            industry=payload.industry,
            competitors=competitors,
        )
    except AnalyzerConfigError as exc:
        # The feature isn't configured (no GEMINI_API_KEY) — not the caller's fault.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except AnalyzerError as exc:
        # The model call or its parsing failed upstream.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return schemas.MarketAnalysisResponse(
        idea_title=payload.title,
        industry=payload.industry,
        market_summary=analysis.market_summary,
        competitor_analysis=[
            schemas.CompetitorInsightOut(
                competitor_name=ci.competitor_name, relation=ci.relation
            )
            for ci in analysis.competitor_analysis
        ],
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        grounded=analysis.grounded,
        model=analysis.model,
        # Echo the exact retrieved context so the client can audit every claim.
        retrieved_competitors=[
            schemas.CompetitorOut(
                startup_name=c.startup_name,
                industry=c.industry,
                description=c.description,
                similarity=c.similarity,
            )
            for c in competitors
        ],
    )


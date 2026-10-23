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
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(tags=["market-analysis"])



@router.post("/analyze-market", response_model=schemas.MarketAnalysisResponse)
def analyze_market_endpoint(
    payload: schemas.AnalyzeMarketRequest,
) -> schemas.MarketAnalysisResponse:
    """Retrieve competitors for the idea, then generate a grounded analysis."""
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

    try:
        from app.services.web_competitor_search import find_web_competitors_sync
        competitors = find_web_competitors_sync(
            title=payload.title,
            description=payload.description,
            industry=payload.industry,
            top_k=payload.top_k,
        )
    except Exception:
        try:
            from app.rag.retrieval import find_competitors
            competitors = find_competitors(
                title=payload.title,
                description=payload.description,
                industry=payload.industry,
                top_k=payload.top_k,
            )
        except Exception:
            competitors = []

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


# ---------------------------------------------------------------------------
# Multi-Agent Investment Committee Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/startups/{startup_id}/analyze",
    response_model=schemas.InvestmentMemo,
    summary="Run or retrieve Multi-Agent Investment Committee analysis for a startup",
)
@router.post(
    "/ideas/{startup_id}/analyze",
    response_model=schemas.InvestmentMemo,
    include_in_schema=False,
)
async def analyze_startup_endpoint(
    startup_id: int,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
) -> schemas.InvestmentMemo:
    """Run the 3-agent investment committee (Bull, Bear, Moat), conduct a debate round,
    and generate a synthesized Lead Partner Investment Memo. Results are cached in the database.
    """
    startup = crud.get_idea(db=db, idea_id=startup_id)
    if not startup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Startup idea with id={startup_id} not found.",
        )

    # Check for cached memo unless force_refresh is requested
    if not force_refresh:
        cached_memo = crud.get_memo_by_startup_id(db=db, startup_id=startup_id)
        if cached_memo:
            return schemas.InvestmentMemo.model_validate_json(cached_memo.full_memo_json)

    from app.services.agents import LeadPartnerOrchestrator

    startup_context = {
        "id": startup.id,
        "title": startup.title,
        "description": startup.description,
        "industry": startup.industry,
    }

    orchestrator = LeadPartnerOrchestrator()
    memo = await orchestrator.run(startup_context)
    crud.save_memo(db=db, startup_id=startup_id, memo=memo)
    return memo


@router.get(
    "/startups/{startup_id}/memo",
    response_model=schemas.InvestmentMemo,
    summary="Fetch existing Investment Memo for a startup",
)
def get_startup_memo_endpoint(
    startup_id: int,
    db: Session = Depends(get_db),
) -> schemas.InvestmentMemo:
    """Fetch previously generated investment memo from the database."""
    cached_memo = crud.get_memo_by_startup_id(db=db, startup_id=startup_id)
    if not cached_memo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investment memo found for startup id={startup_id}.",
        )
    return schemas.InvestmentMemo.model_validate_json(cached_memo.full_memo_json)


@router.post(
    "/tools/web-search",
    response_model=schemas.WebSearchResponse,
    summary="Execute live web search intel using Tavily",
)
async def live_web_search_endpoint(
    payload: schemas.WebSearchRequest,
) -> schemas.WebSearchResponse:
    """Execute live web search intel (Tavily/Serper/Fallback) and return structured results with tool tracking."""
    from app.services.agents.tools import execute_and_track_tool, web_search_intel

    result_text, tool_record = await execute_and_track_tool(
        tool_callable=web_search_intel,
        input_parameters={"query": payload.query, "search_type": payload.search_type},
        agent_name="LiveWebSearch",
    )
    return schemas.WebSearchResponse(
        query=payload.query,
        search_type=payload.search_type,
        results=result_text,
        tool_record=tool_record,
    )




"""Market-analysis generation service — the Gemini integration.

Given a startup idea and the competitors retrieved for it (by
``app.rag.retrieval.find_competitors``), ask Google Gemini to produce a grounded,
four-part analysis: market summary, competitor analysis, strengths, weaknesses.

Position in the pipeline
------------------------
    idea ──> [retrieval: Chroma vector search] ──> competitors
                                                      │
    idea + competitors ──> [this service: Gemini] ──> MarketAnalysis

Retrieval is the "R" of RAG; this module is the "G". It deliberately does NOT do
its own retrieval — it only generates from context it is handed, which keeps the
grounding guarantee easy to reason about and the unit tests free of a vector DB.

Three independent anti-hallucination guardrails
-----------------------------------------------
1. Prompt grounding (``prompts/market_analysis.py``): the model is told the
   retrieved competitors are the only admissible evidence and to abstain on gaps.
2. Structured decoding: we pass a JSON ``response_schema`` and temperature 0, so
   the output shape is fixed and decoding is (near-)deterministic.
3. Code-level enforcement (this file): if retrieval returned nothing we never
   call the model at all, and after generation we drop any competitor the model
   named that was not actually in the retrieved set.

Laziness
--------
The Gemini SDK is imported and the client constructed on first use, not at import
time, mirroring the RAG layer. Importing this module therefore has no side
effects and needs no API key — unit tests stub ``_call_gemini`` and never touch
the network.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel

from app.config import settings
from app.prompts.market_analysis import SYSTEM_INSTRUCTION, build_user_prompt


# --- Input contract -------------------------------------------------------

class CompetitorContext(Protocol):
    """What this service needs from a retrieved competitor.

    Structurally satisfied by ``app.rag.retrieval.Competitor`` — we depend on the
    shape, not the concrete class, so retrieval and generation stay decoupled.
    """

    startup_name: str
    industry: str
    description: str
    similarity: float


# --- Gemini structured-output schema --------------------------------------
# These Pydantic models are handed to Gemini as the response schema. The API is
# constrained to emit JSON matching this shape, which removes a whole class of
# free-form hallucination (extra sections, prose, invented fields).

class _CompetitorInsightLLM(BaseModel):
    competitor_name: str
    relation: str  # how this competitor relates to / differs from the idea


class _MarketAnalysisLLM(BaseModel):
    market_summary: str
    competitor_analysis: list[_CompetitorInsightLLM]
    strengths: list[str]
    weaknesses: list[str]
    # The model's own honesty signal: did the retrieved context actually support
    # the analysis, or was it too thin? Surfaced to the caller, not hidden.
    sufficient_context: bool


# --- Public result types --------------------------------------------------

@dataclass(frozen=True)
class CompetitorInsight:
    competitor_name: str
    relation: str


@dataclass(frozen=True)
class MarketAnalysis:
    market_summary: str
    competitor_analysis: list[CompetitorInsight]
    strengths: list[str]
    weaknesses: list[str]
    grounded: bool          # True when generated from a non-empty, validated set
    model: str              # Gemini model id that produced this (or "" if none)
    used_competitors: list[str]  # retrieved names the analysis is anchored on


# --- Errors ---------------------------------------------------------------

class AnalyzerError(RuntimeError):
    """Base class for market-analyzer failures."""


class AnalyzerConfigError(AnalyzerError):
    """Raised when the service is not configured (e.g. missing API key)."""


from app.services.llm_client import BaseLLMClient, get_llm_client


def _call_gemini(user_prompt: str) -> _MarketAnalysisLLM:
    """Send one grounded request to the configured LLM (Ollama or Gemini) and return the parsed analysis."""
    import asyncio
    client = get_llm_client()
    if client is None:
        raise AnalyzerConfigError(
            "No LLM provider available. Set LLM_PROVIDER=ollama (and ensure Ollama is running) or set GEMINI_API_KEY."
        )

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    client.generate_structured(
                        system_instruction=SYSTEM_INSTRUCTION,
                        user_prompt=user_prompt,
                        response_schema=_MarketAnalysisLLM,
                        temperature=0.0,
                    ),
                ).result()
        else:
            return asyncio.run(
                client.generate_structured(
                    system_instruction=SYSTEM_INSTRUCTION,
                    user_prompt=user_prompt,
                    response_schema=_MarketAnalysisLLM,
                    temperature=0.0,
                )
            )
    except Exception as exc:
        raise AnalyzerError(f"LLM generation failed: {exc}") from exc



# --- Orchestration --------------------------------------------------------

def analyze_market(
    *,
    idea_title: str,
    idea_description: str,
    industry: str | None,
    competitors: Sequence[CompetitorContext],
) -> MarketAnalysis:
    """Generate a grounded market analysis for an idea from its retrieved competitors.

    Guardrail 3a: with no retrieved competitors there is no admissible evidence,
    so we return an explicit "insufficient context" result and never invoke the
    model — the cheapest possible way to not hallucinate a market.
    """
    if not competitors:
        return MarketAnalysis(
            market_summary=(
                "No competitors were retrieved for this idea, so no market "
                "analysis can be grounded. Add more startups to the knowledge "
                "base or broaden the idea description, then retry."
            ),
            competitor_analysis=[],
            strengths=[],
            weaknesses=[],
            grounded=False,
            model="",
            used_competitors=[],
        )

    user_prompt = build_user_prompt(
        idea_title=idea_title,
        idea_description=idea_description,
        industry=industry,
        competitors=competitors,
    )
    llm = _call_gemini(user_prompt)

    # Guardrail 3b: keep only insights about competitors that were actually
    # retrieved. If the model fabricates a name, it is dropped here rather than
    # surfaced to the user. Matching is case/space-insensitive on the name.
    retrieved = {c.startup_name.strip().casefold(): c.startup_name for c in competitors}
    insights: list[CompetitorInsight] = []
    used: list[str] = []
    for item in llm.competitor_analysis:
        canonical = retrieved.get(item.competitor_name.strip().casefold())
        if canonical is None:
            continue  # hallucinated / out-of-context competitor — discard
        insights.append(CompetitorInsight(competitor_name=canonical, relation=item.relation))
        if canonical not in used:
            used.append(canonical)

    return MarketAnalysis(
        market_summary=llm.market_summary,
        competitor_analysis=insights,
        strengths=list(llm.strengths),
        weaknesses=list(llm.weaknesses),
        grounded=bool(llm.sufficient_context and insights),
        model=settings.gemini_model,
        used_competitors=used,
    )

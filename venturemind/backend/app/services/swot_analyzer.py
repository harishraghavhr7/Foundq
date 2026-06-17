"""SWOT-analysis generation service — the Gemini integration.

Given a startup idea plus caller-supplied competitors and market context, ask
Google Gemini to produce a grounded four-quadrant SWOT (strengths, weaknesses,
opportunities, threats).

Relation to the market-analysis feature
---------------------------------------
``services/market_analyzer.py`` *retrieves* competitors from the vector store and
generates a market summary grounded in them. This service is the sibling that
takes competitors and market context as **explicit inputs** — the caller controls
the evidence set — and produces a SWOT instead. It therefore depends on neither
the database nor the RAG layer, which keeps the /swot-analysis router
self-contained and independently testable (the same property the classify/score/
market-demand routers have).

Two anti-hallucination guardrails
---------------------------------
1. Prompt grounding (``prompts/swot_analysis.py``): the model is told the
   supplied inputs are the only admissible evidence and to abstain on gaps.
2. Structured decoding: we pass a JSON ``response_schema`` and temperature 0, so
   the output shape is fixed and decoding is (near-)deterministic.

Unlike market analysis, there is no "drop hallucinated competitor" pass: a SWOT
legitimately reasons beyond the competitor list (about market forces, internal
fit, timing), so a code-level whitelist would be wrong here. Grounding is carried
by the prompt and the schema, and the model's own ``sufficient_context`` flag is
surfaced to the caller rather than hidden.

Laziness
--------
The Gemini SDK is imported and the client constructed on first use, not at import
time, mirroring the RAG layer and the market analyzer. Importing this module has
no side effects and needs no API key — unit tests stub ``_call_gemini`` and never
touch the network.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel

from app.config import settings
from app.prompts.swot_analysis import SYSTEM_INSTRUCTION, build_user_prompt


# --- Input contract -------------------------------------------------------

class CompetitorContext(Protocol):
    """What this service needs from a supplied competitor.

    Structurally satisfied by ``schemas.SwotCompetitorIn`` — we depend on the
    shape (name + optional description), not the concrete class.
    """

    name: str
    description: str | None


# --- Gemini structured-output schema --------------------------------------
# These Pydantic models are handed to Gemini as the response schema. The API is
# constrained to emit JSON matching this shape, which removes a whole class of
# free-form hallucination (extra sections, prose, invented fields).

class _SwotItemLLM(BaseModel):
    point: str
    rationale: str


class _SwotAnalysisLLM(BaseModel):
    strengths: list[_SwotItemLLM]
    weaknesses: list[_SwotItemLLM]
    opportunities: list[_SwotItemLLM]
    threats: list[_SwotItemLLM]
    # The model's own honesty signal: were the inputs rich enough to analyse
    # well, or too thin? Surfaced to the caller, not hidden.
    sufficient_context: bool


# --- Public result types --------------------------------------------------

@dataclass(frozen=True)
class SwotItem:
    point: str
    rationale: str


@dataclass(frozen=True)
class SwotAnalysis:
    strengths: list[SwotItem]
    weaknesses: list[SwotItem]
    opportunities: list[SwotItem]
    threats: list[SwotItem]
    sufficient_context: bool
    model: str  # Gemini model id that produced this (or "" if none)


# --- Errors ---------------------------------------------------------------

class SwotError(RuntimeError):
    """Base class for SWOT-analyzer failures."""


class SwotConfigError(SwotError):
    """Raised when the service is not configured (e.g. missing API key)."""


# --- The Gemini call (the one impure seam; stubbed in tests) --------------

@lru_cache(maxsize=1)
def _get_client():
    """Construct the Gemini client once. Imported lazily so the SDK is only a
    hard dependency when the feature is actually exercised.

    Kept local (rather than shared with the market analyzer) so this feature
    stays self-contained and raises its own configuration error type.
    """
    if not settings.gemini_api_key:
        raise SwotConfigError(
            "GEMINI_API_KEY is not set — POST /swot-analysis is unavailable. "
            "Add it to your .env (see .env.example)."
        )
    from google import genai  # lazy: keeps import-time deps light

    return genai.Client(api_key=settings.gemini_api_key)


def _call_gemini(user_prompt: str) -> _SwotAnalysisLLM:
    """Send one grounded request to Gemini and return the parsed SWOT.

    Isolated behind this function so tests can monkeypatch it without the SDK,
    an API key, or a network. Everything around it is pure and deterministic.
    """
    client = _get_client()  # validates the API key first (clear config error)
    from google.genai import types
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.0,                    # deterministic, no creative drift
            response_mime_type="application/json",
            response_schema=_SwotAnalysisLLM,   # constrain output shape
        ),
    )

    # The SDK parses JSON into our Pydantic model on `.parsed`; fall back to
    # manual JSON validation if a model/SDK version leaves it unset.
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, _SwotAnalysisLLM):
        return parsed
    text = getattr(response, "text", None)
    if not text:
        raise SwotError("Gemini returned an empty response.")
    try:
        return _SwotAnalysisLLM.model_validate_json(text)
    except Exception as exc:  # malformed JSON despite the schema constraint
        raise SwotError(f"Could not parse Gemini response: {exc}") from exc


# --- Orchestration --------------------------------------------------------

def _to_items(items: Sequence[_SwotItemLLM]) -> list[SwotItem]:
    return [SwotItem(point=i.point, rationale=i.rationale) for i in items]


def generate_swot(
    *,
    idea_title: str,
    idea_description: str,
    industry: str | None,
    competitors: Sequence[CompetitorContext],
    market_context: str | None,
) -> SwotAnalysis:
    """Generate a SWOT analysis for an idea from the supplied context.

    Unlike market analysis, this always calls the model: a SWOT of the bare idea
    is meaningful even with no competitors or market context (the model simply
    reports thinner external quadrants and sets ``sufficient_context`` to false).
    """
    user_prompt = build_user_prompt(
        idea_title=idea_title,
        idea_description=idea_description,
        industry=industry,
        competitors=competitors,
        market_context=market_context,
    )
    llm = _call_gemini(user_prompt)

    return SwotAnalysis(
        strengths=_to_items(llm.strengths),
        weaknesses=_to_items(llm.weaknesses),
        opportunities=_to_items(llm.opportunities),
        threats=_to_items(llm.threats),
        sufficient_context=bool(llm.sufficient_context),
        model=settings.gemini_model,
    )

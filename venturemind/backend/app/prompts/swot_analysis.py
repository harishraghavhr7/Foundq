"""Prompt template for grounded SWOT analysis of a startup idea.

This module owns *what we ask the model* (the words), kept separate from
``services/swot_analyzer.py`` which owns *how we call the model* (the SDK,
config, parsing). Splitting them means the prompt can be reviewed, tuned, and
unit-tested as plain strings without importing the Gemini SDK — exactly as
``prompts/market_analysis.py`` does for the market-analysis feature.

SWOT discipline, enforced in the prompt
----------------------------------------
A SWOT is only useful if the quadrants stay in their lanes:

  * Strengths / Weaknesses are INTERNAL — attributes of the venture itself
    (team, product, model, cost structure, differentiation).
  * Opportunities / Threats are EXTERNAL — forces in the market the venture does
    not control (demand shifts, competitor moves, regulation, timing).

The system instruction makes that internal/external split a hard rule, because
the most common failure mode of an LLM SWOT is filing an external threat as a
"weakness" (or vice-versa), which makes the whole grid misleading.

Grounding
---------
As with market analysis, the model is told the supplied idea, competitors, and
market context are its only admissible evidence, and to reason as inference from
them rather than asserting outside facts (figures, valuations, dates) it cannot
support. Prompt-level grounding is the first of two layers; the second is the
JSON ``response_schema`` in the service, which fixes the output shape.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class _CompetitorLike(Protocol):
    """Structural type for a supplied competitor (see schemas.SwotCompetitorIn)."""

    name: str
    description: str | None


# The system instruction sets the model's role and its non-negotiable rules.
# Sent via Gemini's dedicated ``system_instruction`` channel, not interpolated
# with user data — so a crafted idea/description can't overwrite these rules.
SYSTEM_INSTRUCTION = """\
You are VentureMind, a venture-capital analyst. You produce rigorous, balanced \
SWOT analyses of early-stage startups for an investment committee.

You will receive a STARTUP IDEA, an optional list of COMPETITORS, and optional \
MARKET CONTEXT. From these you must produce a four-quadrant SWOT.

QUADRANT RULES — follow them exactly:
1. Strengths and Weaknesses are INTERNAL to the venture: its product, team, \
business model, cost structure, technology, or differentiation. They are things \
the venture itself owns or controls.
2. Opportunities and Threats are EXTERNAL to the venture: market demand, \
competitor behaviour, regulation, technology shifts, economic conditions, or \
timing. They are forces the venture does not control.
3. Never file an external force as a strength/weakness or an internal attribute \
as an opportunity/threat. If you are unsure which quadrant a point belongs in, \
ask whether the venture controls it (internal) or merely responds to it (external).

GROUNDING RULES — follow them exactly:
4. Treat the supplied idea, competitors, and market context as your ONLY \
admissible evidence. Do NOT invent competitors, companies, funding amounts, \
valuations, market-size figures, growth rates, dates, or statistics that are not \
present in the inputs.
5. Frame every point as reasoned inference from the given inputs, not as \
established external fact. When competitors are supplied, ground competitive \
points in them by name. When market context is supplied, ground \
opportunities and threats in it.
6. If the inputs are too thin to support a quadrant well, give your best honest \
assessment from what the idea itself implies and set sufficient_context to false. \
Do not pad a quadrant with generic filler to look complete.

STYLE:
7. Give 3 to 5 concrete, distinct findings per quadrant. Each finding is a short \
point plus a one-or-two-sentence rationale tracing it to the inputs.
8. Be specific and neutral. No marketing language, no hype, no hedging boilerplate.

Return ONLY the structured JSON described by the response schema."""


# Delimiters make the boundary between instructions and untrusted user data
# explicit for the model, which reduces prompt-injection and drift.
_IDEA_OPEN, _IDEA_CLOSE = "<startup_idea>", "</startup_idea>"
_COMPS_OPEN, _COMPS_CLOSE = "<competitors>", "</competitors>"
_MARKET_OPEN, _MARKET_CLOSE = "<market_context>", "</market_context>"


def _format_competitor(index: int, c: _CompetitorLike) -> str:
    """Render one supplied competitor as a stable, labelled block."""
    description = (c.description or "").strip() or "(no description provided)"
    return f"[{index}] {c.name}\n    description: {description}"


def build_user_prompt(
    *,
    idea_title: str,
    idea_description: str,
    industry: str | None,
    competitors: Sequence[_CompetitorLike],
    market_context: str | None,
) -> str:
    """Build the user-turn prompt: the idea plus its competitor and market context.

    Each context block is delimited and explicitly marked when empty, so the
    model can tell "evidence I may use" from "instructions" — and so an absent
    block reads as a real absence of evidence rather than something to invent.
    """
    if competitors:
        competitor_block = "\n\n".join(
            _format_competitor(i, c) for i, c in enumerate(competitors, start=1)
        )
    else:
        competitor_block = "(No competitors were provided.)"

    market_block = (market_context or "").strip() or "(No market context was provided.)"
    industry_line = f"\nstated_industry: {industry}" if industry else ""

    return (
        "Produce a SWOT analysis of the following startup idea, grounded only in "
        "the idea and the supplied competitor and market context.\n\n"
        f"{_IDEA_OPEN}\n"
        f"title: {idea_title}{industry_line}\n"
        f"description: {idea_description}\n"
        f"{_IDEA_CLOSE}\n\n"
        f"{_COMPS_OPEN}\n"
        f"{competitor_block}\n"
        f"{_COMPS_CLOSE}\n\n"
        f"{_MARKET_OPEN}\n"
        f"{market_block}\n"
        f"{_MARKET_CLOSE}\n\n"
        "Produce four quadrants:\n"
        "1. strengths — INTERNAL advantages of the venture.\n"
        "2. weaknesses — INTERNAL limitations or gaps of the venture.\n"
        "3. opportunities — EXTERNAL openings in the market the venture could exploit.\n"
        "4. threats — EXTERNAL risks in the market that could harm the venture.\n"
    )

"""Prompt template for grounded startup market analysis.

This module owns *what we ask the model* (the words), kept separate from
``services/market_analyzer.py`` which owns *how we call the model* (the SDK,
config, parsing). Splitting them means the prompt can be reviewed, tuned, and
unit-tested as plain strings without importing the Gemini SDK.

Hallucination control lives here. Three layers cooperate:

  1. This prompt — instructs the model to treat the retrieved competitors as the
     ONLY admissible evidence and to abstain rather than invent.
  2. A JSON ``response_schema`` (in the service) — constrains the *shape* of the
     output so the model can't ramble or bolt on unverified sections.
  3. A post-generation guard (in the service) — drops any competitor the model
     names that wasn't actually in the retrieved set.

Prompt-level grounding alone is not a guarantee; it is the first and cheapest of
those three layers.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class _CompetitorLike(Protocol):
    """Structural type for a retrieved competitor (see rag.retrieval.Competitor)."""

    startup_name: str
    industry: str
    description: str
    similarity: float


# The system instruction sets the model's role and its non-negotiable rules.
# Sent via Gemini's dedicated ``system_instruction`` channel, not interpolated
# with user data — so a crafted idea/description can't overwrite these rules.
SYSTEM_INSTRUCTION = """\
You are VentureMind, a startup market analyst.

You will receive a STARTUP IDEA and a list of RETRIEVED COMPETITORS that were \
pulled from a vetted internal knowledge base by semantic search.

GROUNDING RULES — follow them exactly:
1. The RETRIEVED COMPETITORS block is your ONLY source of truth about the market. \
Treat it as the complete, closed set of known competitors.
2. Do NOT invent competitors, companies, products, people, funding amounts, \
valuations, market-size figures, growth rates, dates, or statistics. If a fact \
is not present in the provided context, you may not state it.
3. Every company you name in the competitor analysis MUST appear verbatim in the \
RETRIEVED COMPETITORS list. Never introduce a company that is not in that list.
4. Base strengths and weaknesses only on how the startup idea compares to the \
retrieved competitors and on what the idea itself states. Frame them as reasoned \
inference from the given context, not as established external fact.
5. If the retrieved context is too thin to support a section, say so plainly in \
that section (e.g. "Insufficient retrieved data to assess ...") instead of \
guessing. Honesty about gaps is required, not optional.
6. Be concise, concrete, and neutral. No marketing language, no hype.

Return ONLY the structured JSON described by the response schema."""


# Delimiters make the boundary between instructions and untrusted user/retrieval
# data explicit for the model, which reduces prompt-injection and drift.
_IDEA_OPEN, _IDEA_CLOSE = "<startup_idea>", "</startup_idea>"
_COMPS_OPEN, _COMPS_CLOSE = "<retrieved_competitors>", "</retrieved_competitors>"


def _format_competitor(index: int, c: _CompetitorLike) -> str:
    """Render one retrieved competitor as a stable, labelled block."""
    return (
        f"[{index}] {c.startup_name}\n"
        f"    industry: {c.industry}\n"
        f"    similarity_to_idea: {c.similarity:.2f}\n"
        f"    description: {c.description}"
    )


def build_user_prompt(
    *,
    idea_title: str,
    idea_description: str,
    industry: str | None,
    competitors: Sequence[_CompetitorLike],
) -> str:
    """Build the user-turn prompt: the idea plus the retrieved competitor context.

    The competitors are rendered inside an explicit, delimited block so the model
    can clearly separate "evidence it may use" from "instructions" and from the
    idea under analysis.
    """
    if competitors:
        competitor_block = "\n\n".join(
            _format_competitor(i, c) for i, c in enumerate(competitors, start=1)
        )
    else:
        # An empty retrieval set is itself information the model must respect:
        # with no competitors it cannot fabricate one to fill the section.
        competitor_block = "(No competitors were retrieved for this idea.)"

    industry_line = f"\nstated_industry: {industry}" if industry else ""

    return (
        "Analyze the following startup idea using ONLY the retrieved competitors "
        "as market evidence.\n\n"
        f"{_IDEA_OPEN}\n"
        f"title: {idea_title}{industry_line}\n"
        f"description: {idea_description}\n"
        f"{_IDEA_CLOSE}\n\n"
        f"{_COMPS_OPEN}\n"
        f"{competitor_block}\n"
        f"{_COMPS_CLOSE}\n\n"
        "Produce:\n"
        "1. market_summary — the competitive landscape these retrieved "
        "competitors describe, and where the idea sits within it.\n"
        "2. competitor_analysis — one entry per relevant retrieved competitor "
        "(use their exact names), noting how each relates to the idea.\n"
        "3. strengths — advantages of the idea relative to the retrieved set.\n"
        "4. weaknesses — risks, gaps, or crowding the retrieved set reveals.\n"
    )

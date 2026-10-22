from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.schemas import AgentVerdict, DebateRound, InvestmentMemo
from app.services.llm_client import BaseLLMClient, get_llm_client


class FinalMemoLLMResponse(BaseModel):
    overall_score: float = Field(ge=1.0, le=10.0)
    verdict: str
    executive_summary: str
    key_strengths: list[str]
    key_risks: list[str]
    recommendations: list[str]


async def write_memo(
    startup_context: dict[str, Any],
    verdicts: list[AgentVerdict],
    debate_transcript: list[DebateRound],
    llm_client: Any = None,
) -> InvestmentMemo:
    """Synthesize committee verdicts and debate into a final Investment Memo."""
    client = None if llm_client is False else (llm_client if llm_client is not None else get_llm_client())
    startup_id = startup_context.get("id", 0)

    startup_title = startup_context.get("title", "Untitled Startup")
    industry = startup_context.get("industry", "Unspecified")

    # Load final memo prompt
    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    prompt_path = prompt_dir / "final_memo.txt"
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()
    else:
        system_instruction = "You are the Lead Partner synthesizing an investment memo."

    # Format debate context
    verdicts_summary = "\n\n".join(
        f"--- {v.agent_name} (Score: {v.score}/10) ---\n"
        f"Summary: {v.summary}\n"
        f"Points: {', '.join(v.key_points)}\n"
        f"Recommendation: {v.recommendation}"
        for v in verdicts
    )

    debate_summary = "\n\n".join(
        f"Round {d.round_number}:\n" + "\n".join(f"- {c.agent_name}: {c.critique_text}" for c in d.critiques)
        for d in debate_transcript
    )

    user_prompt = (
        f"Startup: {startup_title}\n"
        f"Industry: {industry}\n"
        f"Description: {startup_context.get('description', '')}\n\n"
        f"Committee Verdicts:\n{verdicts_summary}\n\n"
        f"Debate Transcript:\n{debate_summary}\n\n"
        f"Synthesize the final Investment Committee Memo with overall score, verdict, executive summary, strengths, risks, and recommendations."
    )

    # Aggregate tool calls from all agent verdicts
    all_tool_calls = [tc for v in verdicts for tc in getattr(v, "tool_calls", [])]

    if isinstance(client, BaseLLMClient):
        try:
            parsed_memo = await client.generate_structured(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                response_schema=FinalMemoLLMResponse,
                temperature=0.2,
            )
            return InvestmentMemo(
                startup_id=startup_id,
                startup_title=startup_title,
                industry=industry,
                overall_score=max(1.0, min(10.0, float(parsed_memo.overall_score))),
                verdict=parsed_memo.verdict,
                executive_summary=parsed_memo.executive_summary,
                key_strengths=parsed_memo.key_strengths,
                key_risks=parsed_memo.key_risks,
                recommendations=parsed_memo.recommendations,
                agent_verdicts=verdicts,
                debate_transcript=debate_transcript,
                tool_calls=all_tool_calls,
                created_at=datetime.now(timezone.utc),
            )
        except Exception:
            # Fall through to algorithmic synthesis
            pass

    # Algorithmic calculation fallback when LLM is unavailable or offline
    bull_score = next((v.score for v in verdicts if "Bull" in v.agent_name), 7.0)
    bear_score = next((v.score for v in verdicts if "Bear" in v.agent_name), 5.0)
    moat_score = next((v.score for v in verdicts if "Moat" in v.agent_name), 6.0)

    # Invert bear score risk: higher bear score = lower score contribution
    risk_penalty = bear_score * 0.3
    calc_score = round(max(1.0, min(10.0, (bull_score * 0.45 + moat_score * 0.35) - risk_penalty + 2.0)), 1)

    if calc_score >= 8.0:
        verdict = "STRONG INVEST"
    elif calc_score >= 6.5:
        verdict = "INVEST WITH CONDITIONS"
    elif calc_score >= 5.0:
        verdict = "CAUTION / PASS"
    else:
        verdict = "PASS"

    return InvestmentMemo(
        startup_id=startup_id,
        startup_title=startup_title,
        industry=industry,
        overall_score=calc_score,
        verdict=verdict,
        executive_summary=f"The Investment Committee evaluated {startup_title} across growth upside, execution downside, and defensive barriers. The opportunity presents meaningful catalysts alongside specific unit economic and moat conditions.",
        key_strengths=[
            f"Compelling product positioning in the {industry} sector.",
            "Identified secular demand and market expansion vectors.",
            "Viable path toward customer acquisition and revenue scaling.",
        ],
        key_risks=[
            "Execution risk in acquiring initial customers against existing competitors.",
            "Requirement to establish durable switching costs early.",
        ],
        recommendations=[
            "Validate early customer retention and payback period metrics.",
            "Deepen proprietary product workflows to raise switching costs.",
            "Proceed with diligence focusing on gross margins.",
        ],
        agent_verdicts=verdicts,
        debate_transcript=debate_transcript,
        tool_calls=all_tool_calls,
        created_at=datetime.now(timezone.utc),
    )


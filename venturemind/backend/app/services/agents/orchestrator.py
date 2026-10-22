from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from app.schemas import AgentVerdict, DebateRound, InvestmentMemo
from app.services.llm_client import get_llm_client
from app.services.agents.bull_agent import BullAgent
from app.services.agents.bear_agent import BearAgent
from app.services.agents.moat_agent import MoatAgent
from app.services.debate import run_debate
from app.services.memo_writer import write_memo


class CommitteeGraphState(TypedDict):
    """LangGraph state representation for the end-to-end investment committee workflow."""

    startup_context: dict[str, Any]
    verdicts: list[AgentVerdict]
    debate_transcript: list[DebateRound]
    memo: InvestmentMemo | None
    rounds: int


class LeadPartnerOrchestrator:
    """Lead Partner Orchestrator coordinating committee evaluation, LangGraph debate, and memo synthesis."""

    def __init__(self, llm_client: Any = None):
        if llm_client is False:
            self.llm = None
        elif llm_client is not None:
            self.llm = llm_client
        else:
            self.llm = get_llm_client()

        self.committee = [
            BullAgent(self.llm if self.llm is not None else False),
            BearAgent(self.llm if self.llm is not None else False),
            MoatAgent(self.llm if self.llm is not None else False),
        ]

        self.graph = self._build_graph()

    def _build_graph(self):
        """Construct the compiled LangGraph StateGraph governing the full committee workflow."""
        builder = StateGraph(CommitteeGraphState)

        async def analyze_node(state: CommitteeGraphState) -> dict[str, Any]:
            # Multi-Agent Committee: run independent analyses in parallel
            verdicts = await asyncio.gather(
                *[agent.analyze(state["startup_context"]) for agent in self.committee]
            )
            return {"verdicts": list(verdicts)}

        async def debate_node(state: CommitteeGraphState) -> dict[str, Any]:
            # Multi-Agent Debate: execute cyclic LangGraph debate cross-critique rounds
            transcript = await run_debate(
                committee=self.committee,
                verdicts=state["verdicts"],
                rounds=state.get("rounds", 1),
            )
            return {"debate_transcript": transcript}

        async def memo_node(state: CommitteeGraphState) -> dict[str, Any]:
            # Lead Partner Synthesis: compile consensus Investment Memo
            memo = await write_memo(
                startup_context=state["startup_context"],
                verdicts=state["verdicts"],
                debate_transcript=state["debate_transcript"],
                llm_client=self.llm,
            )
            return {"memo": memo}

        builder.add_node("committee_analysis", analyze_node)
        builder.add_node("committee_debate", debate_node)
        builder.add_node("memo_synthesis", memo_node)

        builder.add_edge(START, "committee_analysis")
        builder.add_edge("committee_analysis", "committee_debate")
        builder.add_edge("committee_debate", "memo_synthesis")
        builder.add_edge("memo_synthesis", END)

        return builder.compile()

    async def run(
        self, startup_context: dict[str, Any], rounds: int = 1
    ) -> InvestmentMemo:
        """Execute the committee LangGraph pipeline and return the generated InvestmentMemo."""
        initial_state: CommitteeGraphState = {
            "startup_context": startup_context,
            "verdicts": [],
            "debate_transcript": [],
            "memo": None,
            "rounds": rounds,
        }

        final_state = await self.graph.ainvoke(initial_state)
        return final_state["memo"]

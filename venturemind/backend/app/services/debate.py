from __future__ import annotations

import asyncio
import re
from typing import Annotated, Any, Sequence, TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.schemas import DebateCritique, DebateRound, AgentVerdict
from app.services.agents.base import Agent
from app.services.llm_client import LangChainLLMAdapter, BaseLLMClient


def merge_critiques(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    """Reducer function for merging critique contributions from parallel agent nodes in LangGraph."""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class DebateState(TypedDict):
    """LangGraph State representation for the multi-agent committee debate."""

    verdicts: dict[str, AgentVerdict]
    transcript: list[DebateRound]
    current_round: int
    max_rounds: int
    current_critiques: Annotated[dict[str, str], merge_critiques]


# LangChain prompt template for debate cross-critique rounds
DEBATE_CRITIQUE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_instruction}"),
    (
        "human",
        (
            "You are {agent_name} participating in an Investment Committee Debate.\n\n"
            "YOUR INITIAL POSITION (Score: {score}/10):\n"
            "Summary: {own_summary}\n"
            "Key Points: {own_key_points}\n"
            "Recommendation: {own_recommendation}\n\n"
            "OTHER COMMITTEE MEMBERS' ARGUMENTS:\n"
            "{other_positions}\n\n"
            "{debate_history}"
            "DEBATE INSTRUCTIONS:\n"
            "Cross-examine peer arguments directly. Defend your stance, challenge other members' "
            "assumptions or risk evaluations, and state any critical conditions or concessions. "
            "Keep your critique sharp, concise, and focused (2-3 sentences)."
        ),
    ),
])


def build_debate_graph(committee: Sequence[Agent]):
    """Construct and compile a LangGraph StateGraph governing the cyclic multi-agent debate interaction."""
    builder = StateGraph(DebateState)

    def init_round_node(state: DebateState) -> dict[str, Any]:
        """Initialize or reset per-round critique buffer."""
        return {"current_critiques": {}}

    builder.add_node("init_round", init_round_node)

    # Fan out to parallel agent debate nodes
    for i, agent in enumerate(committee):
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", agent.name.lower())
        node_name = f"critique_{clean_name}_{i}"

        async def _agent_critique_node(state: DebateState, current_agent: Agent = agent) -> dict[str, Any]:
            own_verdict = state["verdicts"].get(current_agent.name)
            if own_verdict is None:
                # Fallback to first available verdict if naming differs
                own_verdict = next(iter(state["verdicts"].values()), None)

            other_verdicts = [v for k, v in state["verdicts"].items() if k != current_agent.name]
            transcript = state.get("transcript", [])

            # Generate cross-critique via agent's LangChain integration
            if hasattr(current_agent, "critique"):
                import inspect

                sig = inspect.signature(current_agent.critique)
                if "prior_rounds" in sig.parameters:
                    text = await current_agent.critique(
                        own_verdict=own_verdict,
                        other_verdicts=other_verdicts,
                        prior_rounds=transcript,
                    )
                else:
                    text = await current_agent.critique(own_verdict, other_verdicts)
            else:
                text = f"{current_agent.name} cross-examined peer positions."

            return {"current_critiques": {current_agent.name: text}}

        builder.add_node(node_name, _agent_critique_node)
        builder.add_edge("init_round", node_name)
        builder.add_edge(node_name, "aggregate_round")

    def aggregate_round_node(state: DebateState) -> dict[str, Any]:
        """Fan in from all committee members, synthesize round transcript, and advance round counter."""
        round_critiques = [
            DebateCritique(
                agent_name=agent.name,
                critique_text=state["current_critiques"].get(
                    agent.name,
                    f"{agent.name} defended stance against peer arguments.",
                ),
            )
            for agent in committee
        ]

        new_round = DebateRound(
            round_number=state["current_round"],
            critiques=round_critiques,
        )

        return {
            "transcript": state["transcript"] + [new_round],
            "current_critiques": {},
            "current_round": state["current_round"] + 1,
        }

    builder.add_node("aggregate_round", aggregate_round_node)

    def should_continue_debate(state: DebateState) -> str:
        """Evaluate cyclic condition: loop for next debate round or terminate."""
        if state["current_round"] <= state["max_rounds"]:
            return "init_round"
        return END

    builder.add_edge(START, "init_round")
    builder.add_conditional_edges("aggregate_round", should_continue_debate)

    return builder.compile()


async def run_debate(
    committee: Sequence[Agent],
    verdicts: Sequence[AgentVerdict],
    rounds: int = 1,
) -> list[DebateRound]:
    """Execute cross-critique rounds where committee members challenge each other's verdicts

    orchestrated through a compiled LangGraph cyclic StateGraph with LangChain agent prompt chains.
    """
    if rounds <= 0 or not committee:
        return []

    # Map verdicts by agent_name, falling back to index alignment
    verdict_map: dict[str, AgentVerdict] = {}
    for idx, agent in enumerate(committee):
        matching = next((v for v in verdicts if v.agent_name == agent.name), None)
        if matching is None and idx < len(verdicts):
            matching = verdicts[idx]
        if matching is not None:
            verdict_map[agent.name] = matching

    graph = build_debate_graph(committee)
    initial_state: DebateState = {
        "verdicts": verdict_map,
        "transcript": [],
        "current_round": 1,
        "max_rounds": rounds,
        "current_critiques": {},
    }

    final_state = await graph.ainvoke(initial_state)
    return final_state["transcript"]

from __future__ import annotations

from typing import Any, Sequence
from app.schemas import AgentVerdict
from app.services.agents.base import Agent


class MoatAgent(Agent):
    name = "Moat Agent"
    prompt_filename = "moat_agent.txt"

    async def analyze(self, startup_context: dict[str, Any]) -> AgentVerdict:
        market_data = await self.retrieve_context(startup_context, focus="moats,switching_costs,defensibility,competitors")
        user_prompt = (
            f"Analyze the defensibility, barriers to entry, switching costs, and competitive moats for this startup:\n\n"
            f"Startup Context & Retrieved Market Data:\n{market_data}\n\n"
            f"Provide your structured evaluation (score 1-10 for moat strength, summary, key moat points, recommendation)."
        )
        return await self._call_llm_structured(user_prompt)


def create_moat_agent(
    llm_client: Any = None,
    tools: Sequence[Any] | None = None,
    middleware: Sequence[Any] | None = None,
) -> MoatAgent:
    """Factory creating a MoatAgent in LangChain style with ModelFallbackMiddleware."""
    return MoatAgent(llm_client=llm_client, tools=tools, middleware=middleware)

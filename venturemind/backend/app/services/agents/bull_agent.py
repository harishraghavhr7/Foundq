from __future__ import annotations

from typing import Any, Sequence
from app.schemas import AgentVerdict
from app.services.agents.base import Agent


class BullAgent(Agent):
    name = "Bull Agent"
    prompt_filename = "bull_agent.txt"

    async def analyze(self, startup_context: dict[str, Any]) -> AgentVerdict:
        market_data = await self.retrieve_context(startup_context, focus="market_size,tam,growth,funding")
        user_prompt = (
            f"Build the strongest upside investment case for this startup:\n\n"
            f"Startup Context & Retrieved Market Data:\n{market_data}\n\n"
            f"Provide your structured evaluation (score 1-10, summary, key upside points, recommendation)."
        )
        return await self._call_llm_structured(user_prompt)


def create_bull_agent(
    llm_client: Any = None,
    tools: Sequence[Any] | None = None,
    middleware: Sequence[Any] | None = None,
) -> BullAgent:
    """Factory creating a BullAgent in LangChain style with ModelFallbackMiddleware."""
    return BullAgent(llm_client=llm_client, tools=tools, middleware=middleware)

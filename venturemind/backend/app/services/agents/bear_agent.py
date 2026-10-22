from __future__ import annotations

from typing import Any, Sequence
from app.schemas import AgentVerdict
from app.services.agents.base import Agent


class BearAgent(Agent):
    name = "Bear Agent"
    prompt_filename = "bear_agent.txt"

    async def analyze(self, startup_context: dict[str, Any]) -> AgentVerdict:
        market_data = await self.retrieve_context(startup_context, focus="risks,cac,unit_economics,competition,news")
        user_prompt = (
            f"Stress-test and identify critical downside risks, execution bottlenecks, and failure modes for this startup:\n\n"
            f"Startup Context & Retrieved Market Data:\n{market_data}\n\n"
            f"Provide your structured evaluation (score 1-10 where 1 is low risk and 10 is extreme risk / high skepticism, "
            f"summary, key downside points, recommendation)."
        )
        return await self._call_llm_structured(user_prompt)


def create_bear_agent(
    llm_client: Any = None,
    tools: Sequence[Any] | None = None,
    middleware: Sequence[Any] | None = None,
) -> BearAgent:
    """Factory creating a BearAgent in LangChain style with ModelFallbackMiddleware."""
    return BearAgent(llm_client=llm_client, tools=tools, middleware=middleware)

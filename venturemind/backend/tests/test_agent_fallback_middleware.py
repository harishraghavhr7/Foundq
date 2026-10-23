from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
import unittest
from typing import Sequence, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from app.schemas import AgentVerdict
from app.services.agents import (
    create_investment_committee_agent,
    create_bull_agent,
    create_bear_agent,
    create_moat_agent,
    BullAgent,
)
from app.services.llm_client import (
    GroqClient,
    OllamaClient,
    GeminiClient,
    OpenRouterClient,
    FallbackLLMClient,
    get_fallback_models,
    LangChainLLMAdapter,
)


class MockFailoverModel(BaseChatModel):
    name: str = "mock-model"
    should_fail: bool = False
    fail_exception_msg: str = "Provider outage"
    succeed_with_text: str = "Fallback success"

    @property
    def _llm_type(self) -> str:
        return self.name

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self

    def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
        if self.should_fail:
            raise RuntimeError(f"{self.name}: {self.fail_exception_msg}")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.succeed_with_text))])

    async def _agenerate(self, messages, stop=None, **kwargs) -> ChatResult:
        if self.should_fail:
            raise RuntimeError(f"{self.name}: {self.fail_exception_msg}")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.succeed_with_text))])


class TestAgentFallbackMiddleware(unittest.TestCase):
    """Test suite validating LangChain style create_agent and ModelFallbackMiddleware across providers (Gemini -> Groq -> OpenRouter -> Ollama)."""

    def test_direct_modelfallbackmiddleware_gemini_to_groq(self):
        async def _run():
            gemini = MockFailoverModel(name="gemini", should_fail=True)
            groq = MockFailoverModel(name="groq", should_fail=False, succeed_with_text="Groq answered.")
            openrouter = MockFailoverModel(name="openrouter", should_fail=False, succeed_with_text="OpenRouter answered.")
            ollama = MockFailoverModel(name="ollama", should_fail=False, succeed_with_text="Ollama answered.")

            agent = create_agent(
                model=gemini,
                tools=[],
                system_prompt="You are Bull Agent.",
                middleware=[
                    ModelFallbackMiddleware(
                        groq,
                        openrouter,
                        ollama,
                    )
                ],
            )

            res = await agent.ainvoke({"messages": [HumanMessage(content="Evaluate startup.")]})
            content = res["messages"][-1].content
            self.assertEqual(content, "Groq answered.")

        asyncio.run(_run())

    def test_direct_modelfallbackmiddleware_gemini_and_groq_fail_to_openrouter(self):
        async def _run():
            gemini = MockFailoverModel(name="gemini", should_fail=True)
            groq = MockFailoverModel(name="groq", should_fail=True)
            openrouter = MockFailoverModel(name="openrouter", should_fail=False, succeed_with_text="OpenRouter answered.")
            ollama = MockFailoverModel(name="ollama", should_fail=False, succeed_with_text="Ollama answered.")

            agent = create_agent(
                model=gemini,
                tools=[],
                system_prompt="You are Bull Agent.",
                middleware=[
                    ModelFallbackMiddleware(
                        groq,
                        openrouter,
                        ollama,
                    )
                ],
            )

            res = await agent.ainvoke({"messages": [HumanMessage(content="Evaluate startup.")]})
            content = res["messages"][-1].content
            self.assertEqual(content, "OpenRouter answered.")

        asyncio.run(_run())

    def test_direct_modelfallbackmiddleware_gemini_groq_openrouter_fail_to_ollama(self):
        async def _run():
            gemini = MockFailoverModel(name="gemini", should_fail=True)
            groq = MockFailoverModel(name="groq", should_fail=True)
            openrouter = MockFailoverModel(name="openrouter", should_fail=True)
            ollama = MockFailoverModel(name="ollama", should_fail=False, succeed_with_text="Ollama rescued the request.")

            agent = create_agent(
                model=gemini,
                tools=[],
                system_prompt="You are Bear Agent.",
                middleware=[
                    ModelFallbackMiddleware(
                        groq,
                        openrouter,
                        ollama,
                    )
                ],
            )

            res = await agent.ainvoke({"messages": [HumanMessage(content="Stress test startup.")]})
            content = res["messages"][-1].content
            self.assertEqual(content, "Ollama rescued the request.")

        asyncio.run(_run())

    def test_create_committee_agent_factory(self):
        primary, fallbacks = get_fallback_models()
        self.assertEqual(primary._llm_type, "openrouter")
        self.assertEqual([f._llm_type for f in fallbacks], ["gemini", "groq", "ollama"])

        agent = create_investment_committee_agent(
            system_prompt="You are an investment analyst.",
            tools=[],
        )
        self.assertIsNotNone(agent)
        self.assertTrue(hasattr(agent, "ainvoke"))

    def test_agent_factory_functions(self):
        bull = create_bull_agent(llm_client=False)
        bear = create_bear_agent(llm_client=False)
        moat = create_moat_agent(llm_client=False)

        self.assertEqual(bull.name, "Bull Agent")
        self.assertEqual(bear.name, "Bear Agent")
        self.assertEqual(moat.name, "Moat Agent")

    def test_bull_agent_with_fallback_middleware_execution(self):
        async def _run():
            gemini = MockFailoverModel(name="gemini", should_fail=True)
            groq = MockFailoverModel(
                name="groq",
                should_fail=False,
                succeed_with_text=json.dumps({
                    "score": 9.0,
                    "summary": "Massive market expansion verified by Groq.",
                    "key_points": ["Strong growth trajectory"],
                    "recommendation": "Invest",
                }),
            )
            openrouter = MockFailoverModel(name="openrouter", should_fail=False)
            ollama = MockFailoverModel(name="ollama", should_fail=False)

            # Custom middleware injecting the mock models
            custom_middleware = [ModelFallbackMiddleware(groq, openrouter, ollama)]

            agent = BullAgent(
                llm_client=True,
                middleware=custom_middleware,
                fallback_models=[groq, openrouter, ollama],
            )
            agent.langchain_agent = create_agent(
                model=gemini,
                tools=[],
                system_prompt=agent.system_prompt,
                middleware=custom_middleware,
            )

            # Fast stub for retrieve_context to avoid external network requests during unit tests
            async def _stub_retrieve(ctx, focus=""):
                return "Mocked retrieved context for Quantum Compute Platform."

            agent.retrieve_context = _stub_retrieve

            context = {
                "id": 10,
                "title": "Quantum Compute Platform",
                "description": "Next-gen fault-tolerant quantum algorithms.",
                "industry": "DeepTech",
            }
            verdict = await agent.analyze(context)
            self.assertEqual(verdict.agent_name, "Bull Agent")
            self.assertEqual(verdict.score, 9.0)
            self.assertIn("Groq", verdict.summary)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

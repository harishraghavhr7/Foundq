from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import AgentVerdict, DebateRound, DebateCritique
from app.services.agents import BullAgent, BearAgent, MoatAgent, LeadPartnerOrchestrator
from app.services.debate import build_debate_graph, run_debate, DEBATE_CRITIQUE_PROMPT, DebateState
from app.services.llm_client import LangChainLLMAdapter, BaseLLMClient
from langchain_core.messages import SystemMessage, HumanMessage


class MockLLM(BaseLLMClient):
    """Hermetic mock LLM client for testing LangChain and LangGraph interactions."""

    def __init__(self, reply_prefix: str = "Mock critique"):
        self.reply_prefix = reply_prefix

    async def generate_text(self, system_instruction: str, user_prompt: str, temperature: float = 0.3) -> str:
        return f"{self.reply_prefix}: defending stance against peer challenges."

    async def generate_structured(self, system_instruction: str, user_prompt: str, response_schema: Any, temperature: float = 0.2):
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class TestLangGraphDebate(unittest.TestCase):
    """Test suite verifying LangChain and LangGraph implementation for multi-agent debates."""

    def setUp(self):
        self.bull_verdict = AgentVerdict(
            agent_name="Bull Agent",
            score=8.5,
            summary="High market growth and expansion opportunities.",
            key_points=["Large TAM", "Product differentiation"],
            recommendation="Invest aggressively.",
        )
        self.bear_verdict = AgentVerdict(
            agent_name="Bear Agent",
            score=5.5,
            summary="Substantial customer acquisition friction and margin risk.",
            key_points=["High CAC", "Competitive headwinds"],
            recommendation="Exercise caution.",
        )
        self.moat_verdict = AgentVerdict(
            agent_name="Moat Agent",
            score=7.0,
            summary="Moderate network effects with expanding data advantage.",
            key_points=["Data moat", "Moderate switching barriers"],
            recommendation="Fund with governance milestones.",
        )
        self.verdicts = [self.bull_verdict, self.bear_verdict, self.moat_verdict]

    def test_build_debate_graph_compilation(self):
        committee = [BullAgent(False), BearAgent(False), MoatAgent(False)]
        graph = build_debate_graph(committee)
        self.assertIsNotNone(graph)
        self.assertTrue(hasattr(graph, "ainvoke"))

    def test_single_round_debate(self):
        async def _run():
            committee = [BullAgent(False), BearAgent(False), MoatAgent(False)]
            transcript = await run_debate(committee, self.verdicts, rounds=1)

            self.assertEqual(len(transcript), 1)
            first_round = transcript[0]
            self.assertEqual(first_round.round_number, 1)
            self.assertEqual(len(first_round.critiques), 3)

            critique_agents = [c.agent_name for c in first_round.critiques]
            self.assertEqual(critique_agents, ["Bull Agent", "Bear Agent", "Moat Agent"])

            for c in first_round.critiques:
                self.assertTrue(len(c.critique_text) > 0)
                self.assertIn("critique", c.critique_text.lower())

        asyncio.run(_run())

    def test_multi_round_cyclic_debate(self):
        async def _run():
            committee = [BullAgent(False), BearAgent(False), MoatAgent(False)]
            # Execute 3 cyclic rounds in LangGraph
            transcript = await run_debate(committee, self.verdicts, rounds=3)

            self.assertEqual(len(transcript), 3)
            for idx, debate_round in enumerate(transcript, start=1):
                self.assertEqual(debate_round.round_number, idx)
                self.assertEqual(len(debate_round.critiques), 3)

        asyncio.run(_run())

    def test_debate_with_mock_llm_adapter(self):
        async def _run():
            mock_llm = MockLLM(reply_prefix="Live Model Critique")
            committee = [
                BullAgent(mock_llm),
                BearAgent(mock_llm),
                MoatAgent(mock_llm),
            ]

            transcript = await run_debate(committee, self.verdicts, rounds=1)
            self.assertEqual(len(transcript), 1)
            critique = transcript[0].critiques[0]
            self.assertIn("Live Model Critique", critique.critique_text)

        asyncio.run(_run())

    def test_langchain_adapter_generate_methods(self):
        async def _run():
            mock_llm = MockLLM(reply_prefix="Adapter Test")
            adapter = LangChainLLMAdapter(llm_client=mock_llm, temperature=0.2)

            res = await adapter.ainvoke([
                SystemMessage(content="You are a debate analyst."),
                HumanMessage(content="Present counter-argument."),
            ])
            self.assertIn("Adapter Test", res.content)

            # Test synchronous invoke
            sync_res = adapter.invoke([
                SystemMessage(content="You are a debate analyst."),
                HumanMessage(content="Present counter-argument."),
            ])
            self.assertIn("Adapter Test", sync_res.content)

        asyncio.run(_run())

    def test_edge_cases_zero_rounds_and_empty_committee(self):
        async def _run():
            committee = [BullAgent(False)]
            res_zero = await run_debate(committee, self.verdicts, rounds=0)
            self.assertEqual(res_zero, [])

            res_empty = await run_debate([], self.verdicts, rounds=2)
            self.assertEqual(res_empty, [])

        asyncio.run(_run())

    def test_orchestrator_langgraph_pipeline(self):
        async def _run():
            orchestrator = LeadPartnerOrchestrator(llm_client=False)
            context = {
                "id": 42,
                "title": "Quantum Fleet",
                "description": "Autonomous logistics network powered by quantum edge computing.",
                "industry": "Supply Chain",
            }
            memo = await orchestrator.run(context, rounds=2)
            self.assertEqual(memo.startup_id, 42)
            self.assertEqual(len(memo.agent_verdicts), 3)
            self.assertEqual(len(memo.debate_transcript), 2)
            self.assertTrue(memo.overall_score >= 1.0)
            self.assertIn(memo.verdict, ["STRONG INVEST", "INVEST WITH CONDITIONS", "CAUTION / PASS", "PASS"])

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()

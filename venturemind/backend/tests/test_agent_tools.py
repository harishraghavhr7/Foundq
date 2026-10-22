from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.agents import (
    INVESTMENT_COMMITTEE_TOOLS,
    web_search_intel,
    lookup_competitor_traction,
    lookup_sec_edgar_tam,
    BullAgent,
    BearAgent,
    create_investment_committee_agent,
)


class TestAgentTools(unittest.TestCase):
    """Test suite validating live web search, competitor traction, and SEC EDGAR TAM tools."""

    def setUp(self):
        try:
            import app.rag.retrieval as rag_retrieval
            from unittest.mock import patch, MagicMock
            self._rag_patch = patch.object(
                rag_retrieval,
                "find_competitors",
                return_value=[MagicMock(startup_name="TutorAI", industry="EdTech", description="AI tutoring bot", similarity=0.88)],
            )
            self._rag_patch.start()
        except Exception:
            self._rag_patch = None

    def tearDown(self):
        if getattr(self, "_rag_patch", None):
            self._rag_patch.stop()

    def test_tools_catalog(self):
        self.assertEqual(len(INVESTMENT_COMMITTEE_TOOLS), 3)
        tool_names = [t.name for t in INVESTMENT_COMMITTEE_TOOLS]
        self.assertIn("web_search_intel", tool_names)
        self.assertIn("lookup_competitor_traction", tool_names)
        self.assertIn("lookup_sec_edgar_tam", tool_names)

    def test_web_search_intel_tool(self):
        async def _run():
            res_edtech = await web_search_intel.ainvoke({"query": "AI tutoring startup funding"})
            self.assertTrue("Live Web Search" in res_edtech or "Verified" in res_edtech)
            self.assertTrue("funding" in res_edtech.lower())

            res_fintech = await web_search_intel.ainvoke({"query": "FinTech payment rails Series A"})
            self.assertTrue("FinTech" in res_fintech or "Live Web Search" in res_fintech)
            self.assertTrue(len(res_fintech) > 50)

        asyncio.run(_run())

    def test_lookup_competitor_traction_tool(self):
        async def _run():
            res = await lookup_competitor_traction.ainvoke({
                "company_or_category": "TutorAI",
                "industry": "EdTech",
            })
            self.assertIn("Competitor Traction", res)
            self.assertIn("Product Hunt", res)
            self.assertIn("Pricing Models", res)
            self.assertIn("Freemium", res)
            self.assertIn("Enterprise", res)

        asyncio.run(_run())

    def test_lookup_sec_edgar_tam_tool(self):
        async def _run():
            # Test public comp ticker
            res_ticker = await lookup_sec_edgar_tam.ainvoke({"sector_or_ticker": "DUOL"})
            self.assertIn("SEC EDGAR 10-K", res_ticker)
            self.assertIn("Duolingo", res_ticker)
            self.assertIn("Gross Margin", res_ticker)
            self.assertIn("Rule of 40", res_ticker)

            # Test industry sector TAM report
            res_sector = await lookup_sec_edgar_tam.ainvoke({"sector_or_ticker": "EdTech"})
            self.assertIn("Total Addressable Market (TAM)", res_sector)
            self.assertIn("Gross Margin", res_sector)
            self.assertIn("CAC Payback", res_sector)

        asyncio.run(_run())

    def test_agent_context_enrichment_with_tools(self):
        async def _run():
            bull = BullAgent(llm_client=False)
            context = {
                "title": "Quantum Physics Tutor",
                "description": "Interactive AI tutor teaching quantum mechanics.",
                "industry": "EdTech",
            }
            enriched_context = await bull.retrieve_context(context, focus="tam,growth,risks")
            self.assertIn("Quantum Physics Tutor", enriched_context)
            self.assertIn("Total Addressable Market (TAM)", enriched_context)
            self.assertIn("Product Hunt", enriched_context)

        asyncio.run(_run())

    def test_create_agent_with_tools_and_middleware(self):
        agent = create_investment_committee_agent(
            tools=INVESTMENT_COMMITTEE_TOOLS,
            system_prompt="You are an analyst equipped with live web, financial, and traction tools.",
        )
        self.assertIsNotNone(agent)
        self.assertTrue(hasattr(agent, "ainvoke"))

    def test_execute_and_track_tool_initialization_and_retrieval(self):
        from app.services.agents.tools import execute_and_track_tool

        async def _run():
            # Test direct tracking of tool execution
            result, record = await execute_and_track_tool(
                tool_callable=lookup_sec_edgar_tam,
                input_parameters={"sector_or_ticker": "DUOL"},
                agent_name="Bull Agent",
            )
            # Verify tool call initialization details
            self.assertEqual(record.tool_name, "lookup_sec_edgar_tam")
            self.assertEqual(record.input_parameters, {"sector_or_ticker": "DUOL"})
            self.assertEqual(record.agent_name, "Bull Agent")
            self.assertIsNotNone(record.timestamp)

            # Verify retrieved information
            self.assertEqual(record.status, "completed")
            self.assertIn("Duolingo", record.retrieved_information)
            self.assertIn("Gross Margin", record.retrieved_information)
            self.assertIsNotNone(record.latency_ms)
            self.assertGreaterEqual(record.latency_ms, 0.0)

        asyncio.run(_run())

    def test_agent_tool_calls_tracking_in_verdict(self):
        async def _run():
            bull = BullAgent(llm_client=False)
            context = {
                "title": "Quantum Physics Tutor",
                "description": "Interactive AI tutor teaching quantum mechanics.",
                "industry": "EdTech",
            }
            verdict = await bull.analyze(context)

            # Verify that the agent tracked tool calls during analysis
            self.assertTrue(len(verdict.tool_calls) >= 2)
            tool_names = [tc.tool_name for tc in verdict.tool_calls]
            self.assertIn("lookup_sec_edgar_tam", tool_names)
            self.assertIn("lookup_competitor_traction", tool_names)

            for tc in verdict.tool_calls:
                # Initialization details
                self.assertEqual(tc.agent_name, "Bull Agent")
                self.assertIsInstance(tc.input_parameters, dict)
                self.assertTrue(len(tc.input_parameters) > 0)
                self.assertEqual(tc.status, "completed")
                # Information retrieved details
                self.assertIsNotNone(tc.retrieved_information)
                self.assertTrue(len(tc.retrieved_information) > 0)
                self.assertIsNotNone(tc.latency_ms)

        asyncio.run(_run())

    def test_tracking_callback_handler(self):
        from app.services.agents.tools import ToolCallTrackingCallbackHandler

        handler = ToolCallTrackingCallbackHandler(agent_name="Moat Agent")
        # Simulate LangChain tool call lifecycle
        handler.on_tool_start(
            serialized={"name": "lookup_sec_edgar_tam"},
            input_str='{"sector_or_ticker": "CRM"}',
            run_id="test-run-123",
        )
        handler.on_tool_end(
            output="### SEC EDGAR 10-K Financial Benchmarks for Salesforce, Inc. (CRM)",
            run_id="test-run-123",
        )

        self.assertEqual(len(handler.tool_calls), 1)
        record = handler.tool_calls[0]
        self.assertEqual(record.tool_name, "lookup_sec_edgar_tam")
        self.assertEqual(record.agent_name, "Moat Agent")
        self.assertEqual(record.input_parameters, {"sector_or_ticker": "CRM"})
        self.assertEqual(record.status, "completed")
        self.assertIn("Salesforce", record.retrieved_information)


if __name__ == "__main__":
    unittest.main()


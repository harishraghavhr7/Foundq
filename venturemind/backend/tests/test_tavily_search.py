from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.agents.tools import (
    execute_and_track_tool,
    web_search_intel,
    lookup_competitor_traction,
    lookup_sec_edgar_tam,
)


class TestTavilyWebSearch(unittest.TestCase):
    """Exhaustive test suite for the Tavily live web search tool, formatting, and fallbacks."""

    def setUp(self):
        self.client = TestClient(app)

    def test_live_tavily_search_when_configured(self):
        """Test real Tavily search if TAVILY_API_KEY is configured in the environment."""
        if not settings.tavily_api_key:
            self.skipTest("TAVILY_API_KEY not configured, skipping live API test.")

        async def _run():
            res = await web_search_intel.ainvoke({
                "query": "OpenAI Series F valuation 2025 2026",
                "search_type": "funding_and_news",
            })
            self.assertIn("Live Web Search Results (Tavily)", res)
            self.assertIn("URL:", res)
            self.assertGreater(len(res), 100)

        asyncio.run(_run())

    def test_mocked_tavily_success_with_answer_and_scores(self):
        """Test Tavily response parsing with synthesized answer, results, and relevance scores."""
        mock_response = {
            "query": "EdTech AI seed funding",
            "answer": "In late 2025, AI tutoring startups secured over $140M in early-stage rounds with high investor interest.",
            "results": [
                {
                    "title": "EdTech AI Closes $10M Seed",
                    "url": "https://techcrunch.com/2025/10/edtech-ai-seed",
                    "content": "AI personalized tutoring platform announces seed round led by Owl Ventures.",
                    "score": 0.94,
                },
                {
                    "title": "Venture Trends in AI Education",
                    "url": "https://venturebeat.com/2025/ai-education-trends",
                    "content": "Seed valuations median at $25M post-money across North America and Europe.",
                    "score": 0.88,
                },
            ],
        }

        async def _run():
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = MagicMock(
                    status_code=200,
                    json=MagicMock(return_value=mock_response),
                )
                res = await web_search_intel.ainvoke({
                    "query": "EdTech AI seed funding",
                    "search_type": "funding_and_news",
                })

                self.assertIn("Live Web Search Results (Tavily)", res)
                self.assertIn("Executive Synthesis", res)
                self.assertIn("In late 2025, AI tutoring startups secured over $140M", res)
                self.assertIn("EdTech AI Closes $10M Seed", res)
                self.assertIn("[Score: 0.94]", res)
                self.assertIn("https://techcrunch.com/2025/10/edtech-ai-seed", res)

        asyncio.run(_run())

    def test_tavily_empty_results_falls_back(self):
        """Test that if Tavily returns empty results and no answer, it gracefully falls back."""
        mock_empty = {"query": "obscure query", "results": [], "answer": None}

        async def _run():
            with patch.object(settings, "tavily_api_key", "mock-tavily-key"):
                with patch.object(settings, "serper_api_key", ""):
                    with patch("httpx.AsyncClient.post") as mock_post:
                        mock_post.return_value = MagicMock(
                            status_code=200,
                            json=MagicMock(return_value=mock_empty),
                        )
                        res = await web_search_intel.ainvoke({
                            "query": "EdTech learning platform market size",
                        })
                        # Should fall back to hermetic market intelligence
                        self.assertIn("Verified Market & Funding Intelligence (EdTech", res)

        asyncio.run(_run())

    def test_tavily_http_error_falls_back_to_serper_or_hermetic(self):
        """Test HTTP error status code (e.g. 401 Unauthorized or 429 Rate Limit) handled gracefully."""
        async def _run():
            with patch.object(settings, "tavily_api_key", "invalid-key"):
                with patch.object(settings, "serper_api_key", ""):
                    with patch("httpx.AsyncClient.post") as mock_post:
                        mock_post.return_value = MagicMock(
                            status_code=401,
                            text="Unauthorized: Invalid API key",
                        )
                        res = await web_search_intel.ainvoke({
                            "query": "FinTech payment rails Series A",
                        })
                        self.assertIn("Verified Market & Funding Intelligence (FinTech", res)

        asyncio.run(_run())

    def test_tavily_timeout_exception_graceful_handling(self):
        """Test timeout exception in Tavily HTTP request falls back gracefully without raising."""
        async def _run():
            with patch.object(settings, "tavily_api_key", "valid-key"):
                with patch.object(settings, "serper_api_key", ""):
                    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
                        res = await web_search_intel.ainvoke({
                            "query": "HealthTech clinical diagnostic market",
                        })
                        self.assertIn("Verified Market & Funding Intelligence (Digital Health", res)

        asyncio.run(_run())

    def test_empty_query_handling(self):
        """Test empty or whitespace query returns clean message."""
        async def _run():
            res = await web_search_intel.ainvoke({"query": "   "})
            self.assertEqual(res, "No search query provided for market intelligence.")

        asyncio.run(_run())

    def test_execute_and_track_tool_with_web_search(self):
        """Test execute_and_track_tool correctly logs and returns ToolCallRecord for web search."""
        async def _run():
            mock_response = {
                "query": "Robotics automation TAM",
                "answer": "Global robotics market reached $45B in 2025.",
                "results": [
                    {
                        "title": "Robotics Report 2025",
                        "url": "https://robotics-report.com/tam",
                        "content": "Autonomous industrial robotics grows at 24% CAGR.",
                        "score": 0.91,
                    }
                ],
            }
            with patch.object(settings, "tavily_api_key", "mock-tavily-key"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_post.return_value = MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=mock_response),
                    )
                    res_str, record = await execute_and_track_tool(
                        tool_callable=web_search_intel,
                        input_parameters={"query": "Robotics automation TAM", "search_type": "market_trends"},
                        agent_name="Bull Agent",
                    )
                    self.assertEqual(record.tool_name, "web_search_intel")
                    self.assertEqual(record.status, "completed")
                    self.assertEqual(record.agent_name, "Bull Agent")
                    self.assertIn("Executive Synthesis", record.retrieved_information)
                    self.assertIn("Robotics Report 2025", record.retrieved_information)
                    self.assertIsNotNone(record.latency_ms)

        asyncio.run(_run())

    def test_live_web_search_api_endpoint(self):
        """Test POST /tools/web-search endpoint via FastAPI TestClient."""
        mock_response = {
            "query": "CleanTech battery storage Series B",
            "answer": "Battery storage infrastructure attracted $3.2B across 45 deals.",
            "results": [
                {
                    "title": "CleanTech Funding News",
                    "url": "https://cleantech.com/battery-storage",
                    "content": "Series B median size expanded to $35M in late 2025.",
                    "score": 0.95,
                }
            ],
        }
        with patch.object(settings, "tavily_api_key", "mock-tavily-key"):
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = MagicMock(
                    status_code=200,
                    json=MagicMock(return_value=mock_response),
                )
                response = self.client.post(
                    "/tools/web-search",
                    json={"query": "CleanTech battery storage Series B", "search_type": "funding_and_news"},
                )
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["query"], "CleanTech battery storage Series B")
                self.assertIn("CleanTech Funding News", data["results"])
                self.assertEqual(data["tool_record"]["tool_name"], "web_search_intel")
                self.assertEqual(data["tool_record"]["status"], "completed")

    def test_competitor_traction_with_tavily_search(self):
        """Test lookup_competitor_traction successfully integrates Tavily live Product Hunt search."""
        mock_response = {
            "query": "Linear app Product Hunt launch upvotes reviews pricing models alternatives traction",
            "answer": "Linear launched on Product Hunt winning #1 Product of the Day with over 1,400 upvotes.",
            "results": [
                {
                    "title": "Linear on Product Hunt",
                    "url": "https://producthunt.com/posts/linear",
                    "content": "The issue tracker built for high-performance software teams. 1,420 upvotes, 4.9/5 rating.",
                    "score": 0.96,
                },
                {
                    "title": "Linear Pricing: Standard vs Plus",
                    "url": "https://linear.app/pricing",
                    "content": "Free for up to 250 active issues. Standard plan is $8/user/mo, Plus plan is $14/user/mo.",
                    "score": 0.92,
                },
            ],
        }
        async def _run():
            with patch.object(settings, "tavily_api_key", "mock-tavily-key"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_post.return_value = MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=mock_response),
                    )
                    res = await lookup_competitor_traction.ainvoke({
                        "company_or_category": "Linear app",
                        "industry": "Developer Tools",
                    })
                    self.assertIn("Competitor Traction", res)
                    self.assertIn("Product Hunt", res)
                    self.assertIn("Tavily Live Intel", res)
                    self.assertIn("1,400 upvotes", res)
                    self.assertIn("Pricing Models", res)
                    self.assertIn("Freemium", res)
                    self.assertIn("Enterprise", res)

        asyncio.run(_run())

    def test_sec_edgar_tam_with_tavily_search(self):
        """Test lookup_sec_edgar_tam successfully integrates Tavily live SEC EDGAR 10-K search."""
        mock_response = {
            "query": "NVDA SEC Form 10-K S-1 filing gross margin Rule of 40 TAM market size CAC payback",
            "answer": "According to the latest SEC Form 10-K, gross margin reached 75.0% driven by $89B in Data Center revenue.",
            "results": [
                {
                    "title": "NVIDIA FY2025 SEC Form 10-K Annual Report",
                    "url": "https://sec.gov/edgar/data/1045810/nvda-10k.htm",
                    "content": "Gross margin increased to 75.0% in fiscal year 2025. Data Center revenue grew 117% YoY.",
                    "score": 0.97,
                }
            ],
        }
        async def _run():
            with patch.object(settings, "tavily_api_key", "mock-tavily-key"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_post.return_value = MagicMock(
                        status_code=200,
                        json=MagicMock(return_value=mock_response),
                    )
                    res = await lookup_sec_edgar_tam.ainvoke({
                        "sector_or_ticker": "NVDA",
                        "metric_focus": "tam_and_margins",
                    })
                    self.assertIn("SEC EDGAR 10-K", res)
                    self.assertIn("Gross Margin", res)
                    self.assertIn("Rule of 40", res)
                    self.assertIn("Total Addressable Market (TAM)", res)
                    self.assertIn("75.0%", res)
                    self.assertIn("Data Center", res)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()


import asyncio
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services.llm_client import (
    OllamaClient,
    GeminiClient,
    get_llm_client,
    extract_json_payload,
)
from app.services.agents import BullAgent, BearAgent, MoatAgent, LeadPartnerOrchestrator


class SampleSchema(BaseModel):
    name: str
    score: float


class TestOllamaIntegration(unittest.TestCase):
    def setUp(self):
        self.rag_patch = patch("app.rag.retrieval.find_competitors", return_value=[])
        self.rag_patch.start()

    def tearDown(self):
        self.rag_patch.stop()

    def test_extract_json_payload(self):

        # Plain json
        self.assertEqual(extract_json_payload('{"key": "val"}'), '{"key": "val"}')
        # Markdown fence
        raw_markdown = "`json\n{\"name\": \"AI Platform\", \"score\": 8.5}\n`"
        self.assertEqual(extract_json_payload(raw_markdown), '{"name": "AI Platform", "score": 8.5}')
        # Markdown fence without json tag
        raw_markdown2 = "`\n{\"name\": \"test\", \"score\": 5.0}\n`"
        self.assertEqual(extract_json_payload(raw_markdown2), '{"name": "test", "score": 5.0}')

    @patch("urllib.request.urlopen")
    def test_ollama_client_structured_generation(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {
                "role": "assistant",
                "content": '{"name": "HealthFlow", "score": 9.2}'
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = OllamaClient(base_url="http://localhost:11434", model="llama3.2")
        result = asyncio.run(
            client.generate_structured(
                system_instruction="Analyze startup",
                user_prompt="Idea: HealthFlow",
                response_schema=SampleSchema,
                temperature=0.1,
            )
        )
        self.assertIsInstance(result, SampleSchema)
        self.assertEqual(result.name, "HealthFlow")
        self.assertEqual(result.score, 9.2)

    @patch("urllib.request.urlopen")
    def test_ollama_client_text_generation(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {
                "role": "assistant",
                "content": "Bull Agent defends market TAM against Bear concerns."
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = OllamaClient()
        text = asyncio.run(client.generate_text("System", "User Prompt"))
        self.assertEqual(text, "Bull Agent defends market TAM against Bear concerns.")

    def test_get_llm_client_factory(self):
        with patch.object(settings, "llm_provider", "ollama"):
            client = get_llm_client()
            self.assertIsInstance(client, OllamaClient)

        with patch.object(settings, "llm_provider", "gemini"):
            with patch.object(settings, "gemini_api_key", "test-key"):
                client = get_llm_client()
                self.assertIsInstance(client, GeminiClient)

    @patch("urllib.request.urlopen")
    def test_committee_orchestrator_with_ollama(self, mock_urlopen):
        # Mock committee structured responses and text critiques
        def side_effect_urlopen(req, *args, **kwargs):
            mock_resp = MagicMock()
            body = json.loads(req.data.decode("utf-8")) if hasattr(req, "data") and req.data else {}
            # Check if structured or text
            if "format" in body:
                mock_resp.read.return_value = json.dumps({
                    "message": {
                        "content": json.dumps({
                            "score": 8.0,
                            "summary": "Strong Ollama evaluation.",
                            "key_points": ["Point 1", "Point 2"],
                            "recommendation": "Invest",
                            "overall_score": 8.5,
                            "verdict": "STRONG INVEST",
                            "executive_summary": "Synthesized memo from Ollama.",
                            "key_strengths": ["Fast scaling"],
                            "key_risks": ["Competition"],
                            "recommendations": ["Expand sales"]
                        })
                    }
                }).encode("utf-8")
            else:
                mock_resp.read.return_value = json.dumps({
                    "message": {
                        "content": "Ollama debate critique response."
                    }
                }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        mock_urlopen.side_effect = side_effect_urlopen

        client = OllamaClient()
        orchestrator = LeadPartnerOrchestrator(llm_client=client)

        context = {
            "id": 1,
            "title": "LocalAI Doc Parser",
            "description": "Parses documents offline using Ollama.",
            "industry": "SaaS",
        }

        memo = asyncio.run(orchestrator.run(context))
        self.assertEqual(memo.startup_id, 1)
        self.assertEqual(len(memo.agent_verdicts), 3)
        self.assertEqual(len(memo.debate_transcript), 1)
        self.assertEqual(memo.verdict, "STRONG INVEST")


if __name__ == "__main__":
    unittest.main()

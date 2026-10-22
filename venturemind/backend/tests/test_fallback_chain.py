from __future__ import annotations

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
    BaseLLMClient,
    GeminiClient,
    GroqClient,
    OpenRouterClient,
    OllamaClient,
    FallbackLLMClient,
    get_fallback_models,
    get_fallback_llm_client,
    get_llm_client,
    extract_json_payload,
)


class SampleVerdict(BaseModel):
    score: float
    summary: str


class MockProvider(BaseLLMClient):
    def __init__(self, name: str, should_fail: bool = False, text_resp: str = "", structured_resp: Any = None):
        self.name = name
        self.should_fail = should_fail
        self.text_resp = text_resp or f"{name} text response"
        self.structured_resp = structured_resp

    def is_available(self) -> bool:
        return True

    async def generate_structured(self, system_instruction, user_prompt, response_schema, temperature=0.2):
        if self.should_fail:
            raise RuntimeError(f"{self.name} generation failed")
        if self.structured_resp is not None:
            return self.structured_resp
        return response_schema(score=8.5, summary=f"{self.name} structured summary")

    async def generate_text(self, system_instruction, user_prompt, temperature=0.3):
        if self.should_fail:
            raise RuntimeError(f"{self.name} generation failed")
        return self.text_resp


class TestFallbackChain(unittest.TestCase):
    """Test suite verifying LLM fallback order: Gemini -> Groq -> OpenRouter -> Ollama."""

    def test_fallback_order_resolution(self):
        primary, fallbacks = get_fallback_models()
        self.assertEqual(primary._llm_type, "gemini")
        fallback_types = [f._llm_type for f in fallbacks]
        self.assertEqual(fallback_types, ["groq", "openrouter", "ollama"])

    def test_openrouter_client_text_and_structured(self):
        client = OpenRouterClient(api_key="sk-or-test-key", model="openai/gpt-4o-mini")
        self.assertTrue(client.is_available())

        # Test text generation with mock
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "OpenRouter evaluation response"}}]
            }).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            text = asyncio.run(client.generate_text("Sys", "User"))
            self.assertEqual(text, "OpenRouter evaluation response")

        # Test structured generation with mock
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": json.dumps({"score": 9.1, "summary": "OR summary"})}}]
            }).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = asyncio.run(
                client.generate_structured("Sys", "User", SampleVerdict)
            )
            self.assertIsInstance(result, SampleVerdict)
            self.assertEqual(result.score, 9.1)
            self.assertEqual(result.summary, "OR summary")

    def test_fallback_client_order_gemini_succeeds(self):
        gemini = MockProvider("gemini", should_fail=False, text_resp="Gemini answered")
        groq = MockProvider("groq", should_fail=False, text_resp="Groq answered")
        openrouter = MockProvider("openrouter", should_fail=False, text_resp="OpenRouter answered")
        ollama = MockProvider("ollama", should_fail=False, text_resp="Ollama answered")

        fallback_client = FallbackLLMClient(providers=[
            ("gemini", gemini),
            ("groq", groq),
            ("openrouter", openrouter),
            ("ollama", ollama),
        ])

        res = asyncio.run(fallback_client.generate_text("Sys", "User"))
        self.assertEqual(res, "Gemini answered")

    def test_fallback_client_gemini_fails_groq_succeeds(self):
        gemini = MockProvider("gemini", should_fail=True)
        groq = MockProvider("groq", should_fail=False, text_resp="Groq answered")
        openrouter = MockProvider("openrouter", should_fail=False, text_resp="OpenRouter answered")
        ollama = MockProvider("ollama", should_fail=False, text_resp="Ollama answered")

        fallback_client = FallbackLLMClient(providers=[
            ("gemini", gemini),
            ("groq", groq),
            ("openrouter", openrouter),
            ("ollama", ollama),
        ])

        res = asyncio.run(fallback_client.generate_text("Sys", "User"))
        self.assertEqual(res, "Groq answered")

    def test_fallback_client_gemini_and_groq_fail_openrouter_succeeds(self):
        gemini = MockProvider("gemini", should_fail=True)
        groq = MockProvider("groq", should_fail=True)
        openrouter = MockProvider("openrouter", should_fail=False, text_resp="OpenRouter rescued the call")
        ollama = MockProvider("ollama", should_fail=False, text_resp="Ollama answered")

        fallback_client = FallbackLLMClient(providers=[
            ("gemini", gemini),
            ("groq", groq),
            ("openrouter", openrouter),
            ("ollama", ollama),
        ])

        res = asyncio.run(fallback_client.generate_text("Sys", "User"))
        self.assertEqual(res, "OpenRouter rescued the call")

    def test_fallback_client_gemini_groq_openrouter_fail_ollama_succeeds(self):
        gemini = MockProvider("gemini", should_fail=True)
        groq = MockProvider("groq", should_fail=True)
        openrouter = MockProvider("openrouter", should_fail=True)
        ollama = MockProvider("ollama", should_fail=False, text_resp="Ollama local fallback")

        fallback_client = FallbackLLMClient(providers=[
            ("gemini", gemini),
            ("groq", groq),
            ("openrouter", openrouter),
            ("ollama", ollama),
        ])

        res = asyncio.run(fallback_client.generate_text("Sys", "User"))
        self.assertEqual(res, "Ollama local fallback")

    def test_fallback_client_structured_generation_cascading(self):
        gemini = MockProvider("gemini", should_fail=True)
        groq = MockProvider("groq", should_fail=True)
        openrouter = MockProvider(
            "openrouter",
            should_fail=False,
            structured_resp=SampleVerdict(score=8.8, summary="OpenRouter structured result"),
        )
        ollama = MockProvider("ollama", should_fail=False)

        fallback_client = FallbackLLMClient(providers=[
            ("gemini", gemini),
            ("groq", groq),
            ("openrouter", openrouter),
            ("ollama", ollama),
        ])

        verdict = asyncio.run(
            fallback_client.generate_structured("Sys", "User", SampleVerdict)
        )
        self.assertEqual(verdict.score, 8.8)
        self.assertEqual(verdict.summary, "OpenRouter structured result")

    def test_fallback_client_all_fail_raises_runtime_error(self):
        gemini = MockProvider("gemini", should_fail=True)
        groq = MockProvider("groq", should_fail=True)
        openrouter = MockProvider("openrouter", should_fail=True)
        ollama = MockProvider("ollama", should_fail=True)

        fallback_client = FallbackLLMClient(providers=[
            ("gemini", gemini),
            ("groq", groq),
            ("openrouter", openrouter),
            ("ollama", ollama),
        ])

        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(fallback_client.generate_text("Sys", "User"))
        self.assertIn("All fallback LLM providers failed", str(ctx.exception))

    def test_get_llm_client_auto_returns_fallback_client(self):
        with patch.object(settings, "llm_provider", "auto"):
            with patch.object(settings, "gemini_api_key", "test-gemini"):
                client = get_llm_client()
                self.assertIsInstance(client, FallbackLLMClient)
                self.assertEqual(
                    [name for name, _ in client.providers],
                    ["gemini", "groq", "openrouter", "ollama"],
                )


if __name__ == "__main__":
    unittest.main()

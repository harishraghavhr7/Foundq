from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel
from app.config import settings
from app.services.llm_client import (
    GeminiClient,
    GroqClient,
    OpenRouterClient,
    OllamaClient,
    FallbackLLMClient,
    get_fallback_llm_client,
)


class TestSchema(BaseModel):
    status: str
    provider: str
    message: str


async def test_live_clients():
    print("=" * 60)
    print("TESTING CONFIGURED LIVE LLM CLIENTS")
    print("=" * 60)

    # 1. Test Gemini
    print("\n--- 1. Testing Gemini ---")
    gemini = GeminiClient()
    if gemini.is_available():
        try:
            resp = await gemini.generate_text("You are a helpful assistant.", "Reply with 'Gemini OK' only.")
            print(f"[SUCCESS] Gemini text: {resp}")
        except Exception as e:
            print(f"[FAILED] Gemini text: {e}")
    else:
        print("[SKIPPED] Gemini API key not provided or unavailable.")

    # 2. Test Groq
    print("\n--- 2. Testing Groq ---")
    groq = GroqClient()
    if groq.is_available():
        try:
            resp = await groq.generate_text("You are a helpful assistant.", "Reply with 'Groq OK' only.")
            print(f"[SUCCESS] Groq text: {resp}")

            structured = await groq.generate_structured(
                "You are an evaluator.",
                "Give a status object with status='healthy', provider='groq', and message='Groq structured works'.",
                TestSchema,
            )
            print(f"[SUCCESS] Groq structured: {structured.model_dump()}")
        except Exception as e:
            print(f"[FAILED] Groq: {e}")
    else:
        print("[SKIPPED] Groq API key not provided.")

    # 3. Test OpenRouter
    print("\n--- 3. Testing OpenRouter ---")
    openrouter = OpenRouterClient()
    if openrouter.is_available():
        try:
            resp = await openrouter.generate_text("You are a helpful assistant.", "Reply with 'OpenRouter OK' only.")
            print(f"[SUCCESS] OpenRouter text: {resp}")

            structured = await openrouter.generate_structured(
                "You are an evaluator.",
                "Give a status object with status='healthy', provider='openrouter', and message='OpenRouter structured works'.",
                TestSchema,
            )
            print(f"[SUCCESS] OpenRouter structured: {structured.model_dump()}")
        except Exception as e:
            print(f"[FAILED] OpenRouter: {e}")
    else:
        print("[SKIPPED] OpenRouter API key not provided.")

    # 4. Test Ollama
    print("\n--- 4. Testing Ollama (Local) ---")
    ollama = OllamaClient()
    if ollama.is_available():
        try:
            resp = await ollama.generate_text("You are a helpful assistant.", "Reply with 'Ollama OK' only.")
            print(f"[SUCCESS] Ollama text: {resp}")
        except Exception as e:
            print(f"[FAILED] Ollama text: {e}")
    else:
        print("[OFFLINE] Ollama daemon is not currently running on localhost:11434.")

    # 5. Test Live Fallback Chain
    print("\n--- 5. Testing Live Fallback Chain (Gemini -> Groq -> OpenRouter -> Ollama) ---")
    fallback = get_fallback_llm_client()
    try:
        text_resp = await fallback.generate_text("You are a helpful assistant.", "Say 'Fallback chain healthy'.")
        print(f"[SUCCESS] Live Fallback text: {text_resp}")

        structured_resp = await fallback.generate_structured(
            "You are an evaluator.",
            "Generate JSON with status='active', provider='primary-available', message='Chain works'.",
            TestSchema,
        )
        print(f"[SUCCESS] Live Fallback structured: {structured_resp.model_dump()}")
    except Exception as e:
        print(f"[FAILED] Live Fallback: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_live_clients())

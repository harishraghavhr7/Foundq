from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def extract_json_payload(text: str) -> str:
    """Extract clean JSON substring if model enclosed it in markdown code fences."""
    text = text.strip()
    match = re.search(r"`(?:json)?\s*([\s\S]*?)\s*`", text)
    if match:
        return match.group(1).strip()
    return text


class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        """Generate structured output adhering to a Pydantic schema."""
        ...

    @abstractmethod
    async def generate_text(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        """Generate free-form text response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this provider is configured and reachable."""
        ...


class OllamaClient(BaseLLMClient):
    """Local LLM client communicating with Ollama's HTTP API."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout

    def is_available(self) -> bool:
        try:
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            host = parsed.hostname or "127.0.0.1"
            if host == "localhost":
                host = "127.0.0.1"
            port = parsed.port or 11434
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            return False



    def _sync_chat(
        self,
        system_instruction: str,
        user_prompt: str,
        format_spec: Any = None,
        temperature: float = 0.2,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if format_spec is not None:
            payload["format"] = format_spec

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("message", {}).get("content", "")
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama connection error at {self.base_url}: {exc}. "
                f"Ensure Ollama is running (ollama serve or ollama run {self.model})."
            ) from exc

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        # Pass JSON schema for structured grammar constraint
        schema_dict = response_schema.model_json_schema()
        raw_text = await asyncio.to_thread(
            self._sync_chat,
            system_instruction,
            user_prompt,
            schema_dict,
            temperature,
        )

        clean_json = extract_json_payload(raw_text)
        try:
            return response_schema.model_validate_json(clean_json)
        except Exception:
            # Fallback attempt with format="json" generic json constraint
            fallback_text = await asyncio.to_thread(
                self._sync_chat,
                f"{system_instruction}\nYou must respond strictly in JSON matching the schema.",
                f"{user_prompt}\nResponse schema: {json.dumps(schema_dict)}",
                "json",
                temperature,
            )
            return response_schema.model_validate_json(extract_json_payload(fallback_text))

    async def generate_text(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        raw_text = await asyncio.to_thread(
            self._sync_chat,
            system_instruction,
            user_prompt,
            None,
            temperature,
        )
        return raw_text.strip()


class GeminiClient(BaseLLMClient):
    """Google Gemini LLM client using google-genai SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY is not set.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        client = self._get_client()
        from google.genai import types

        def _sync_call():
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, response_schema):
                return parsed
            text = getattr(response, "text", "")
            return response_schema.model_validate_json(text)

        return await asyncio.to_thread(_sync_call)

    async def generate_text(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        client = self._get_client()
        from google.genai import types

        def _sync_call():
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
            )
            return getattr(response, "text", "").strip()

        return await asyncio.to_thread(_sync_call)


class GroqClient(BaseLLMClient):
    """Groq LLM client communicating with Groq API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GROQ_API_KEY is not set.")
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        client = self._get_client()
        schema_dict = response_schema.model_json_schema()

        def _sync_call():
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"{system_instruction}\nYou must respond strictly in JSON matching the schema: {json.dumps(schema_dict)}",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            raw = completion.choices[0].message.content or ""
            clean_json = extract_json_payload(raw)
            return response_schema.model_validate_json(clean_json)

        return await asyncio.to_thread(_sync_call)

    async def generate_text(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        client = self._get_client()

        def _sync_call():
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            return (completion.choices[0].message.content or "").strip()

        return await asyncio.to_thread(_sync_call)


class OpenRouterClient(BaseLLMClient):
    """OpenRouter LLM client communicating with OpenRouter's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.openrouter_model
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _sync_chat(
        self,
        system_instruction: str,
        user_prompt: str,
        format_spec: Any = None,
        temperature: float = 0.3,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set.")

        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": user_prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if format_spec is not None:
            payload["response_format"] = format_spec

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=req_data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://venturemind.ai",
                "X-Title": "VentureMind",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError(f"OpenRouter returned empty choices: {data}")
                return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenRouter HTTP error {exc.code}: {err_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter connection error: {exc}") from exc

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        schema_dict = response_schema.model_json_schema()
        raw_text = await asyncio.to_thread(
            self._sync_chat,
            f"{system_instruction}\nYou must respond strictly in JSON matching the schema: {json.dumps(schema_dict)}",
            user_prompt,
            {"type": "json_object"},
            temperature,
        )
        clean_json = extract_json_payload(raw_text)
        try:
            return response_schema.model_validate_json(clean_json)
        except Exception:
            # Fallback attempt if response_format was not honored
            fallback_text = await asyncio.to_thread(
                self._sync_chat,
                f"{system_instruction}\nRespond strictly with valid JSON conforming to: {json.dumps(schema_dict)}",
                user_prompt,
                None,
                temperature,
            )
            return response_schema.model_validate_json(extract_json_payload(fallback_text))

    async def generate_text(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        raw_text = await asyncio.to_thread(
            self._sync_chat,
            system_instruction,
            user_prompt,
            None,
            temperature,
        )
        return raw_text.strip()


class FallbackLLMClient(BaseLLMClient):
    """Resilient multi-provider client cascading across LLM providers.

    Default sequence: Gemini -> Groq -> OpenRouter -> Ollama.
    """

    def __init__(
        self,
        providers: list[tuple[str, BaseLLMClient]] | None = None,
        fallback_order: list[str] | None = None,
    ):
        if providers is not None:
            self.providers = providers
        else:
            order = fallback_order or [
                p.strip().lower()
                for p in settings.llm_fallback_order.split(",")
                if p.strip()
            ]
            if not order:
                order = ["openrouter", "gemini", "groq", "ollama"]

            self.providers = []
            for name in order:
                client = self._create_provider_client(name)
                if client is not None:
                    self.providers.append((name, client))

    @staticmethod
    def _create_provider_client(name: str) -> BaseLLMClient | None:
        p = name.lower().strip()
        if p == "gemini":
            return GeminiClient()
        elif p == "groq":
            return GroqClient()
        elif p == "openrouter":
            return OpenRouterClient()
        elif p == "ollama":
            return OllamaClient()
        return None

    @property
    def primary_name(self) -> str:
        return self.providers[0][0] if self.providers else "gemini"

    def is_available(self) -> bool:
        return any(client.is_available() for _, client in self.providers)

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        errors: list[str] = []
        for name, client in self.providers:
            if not client.is_available():
                errors.append(f"{name}: unconfigured or offline")
                continue
            try:
                logger.info("FallbackLLMClient: attempting generate_structured via %s", name)
                return await client.generate_structured(
                    system_instruction=system_instruction,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    temperature=temperature,
                )
            except Exception as exc:
                logger.warning("FallbackLLMClient: provider '%s' failed in generate_structured: %s", name, exc)
                errors.append(f"{name}: {exc}")

        raise RuntimeError(
            f"All fallback LLM providers failed: {'; '.join(errors)}"
        )

    async def generate_text(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        errors: list[str] = []
        for name, client in self.providers:
            if not client.is_available():
                errors.append(f"{name}: unconfigured or offline")
                continue
            try:
                logger.info("FallbackLLMClient: attempting generate_text via %s", name)
                return await client.generate_text(
                    system_instruction=system_instruction,
                    user_prompt=user_prompt,
                    temperature=temperature,
                )
            except Exception as exc:
                logger.warning("FallbackLLMClient: provider '%s' failed in generate_text: %s", name, exc)
                errors.append(f"{name}: {exc}")

        raise RuntimeError(
            f"All fallback LLM providers failed: {'; '.join(errors)}"
        )


def get_fallback_llm_client(fallback_order: list[str] | None = None) -> FallbackLLMClient:
    """Explicit factory to obtain a FallbackLLMClient cascading across providers (gemini -> groq -> openrouter -> ollama)."""
    return FallbackLLMClient(fallback_order=fallback_order)


def get_llm_client() -> BaseLLMClient | None:
    """Factory to obtain the configured LLM client (Gemini, Groq, OpenRouter, or Ollama)."""
    provider = settings.llm_provider.lower().strip()

    if provider == "gemini":
        if settings.gemini_api_key:
            return GeminiClient()
        if settings.groq_api_key:
            return GroqClient()
        if settings.openrouter_api_key:
            return OpenRouterClient()
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama
        return None
    elif provider == "groq":
        if settings.groq_api_key:
            return GroqClient()
        if settings.openrouter_api_key:
            return OpenRouterClient()
        if settings.gemini_api_key:
            return GeminiClient()
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama
        return None
    elif provider == "openrouter":
        if settings.openrouter_api_key:
            return OpenRouterClient()
        if settings.gemini_api_key:
            return GeminiClient()
        if settings.groq_api_key:
            return GroqClient()
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama
        return None
    elif provider == "ollama":
        ollama = OllamaClient()
        if ollama.is_available():
            return ollama
        if settings.gemini_api_key:
            return GeminiClient()
        if settings.groq_api_key:
            return GroqClient()
        if settings.openrouter_api_key:
            return OpenRouterClient()
        return OllamaClient()
    elif provider in ("auto", "fallback"):
        fb = FallbackLLMClient()
        if fb.is_available():
            return fb
        return None

    return OllamaClient()


class LangChainLLMAdapter(BaseChatModel):
    """LangChain BaseChatModel adapter wrapping venturemind's BaseLLMClient with bind_tools support."""

    llm_client: Any = None
    temperature: float = 0.3
    name: str = "venturemind-llm"

    @property
    def _llm_type(self) -> str:
        return self.name

    def bind_tools(self, tools: Any = None, **kwargs: Any) -> Any:
        return self.__class__(
            llm_client=self.llm_client,
            temperature=self.temperature,
            name=self.name,
        )

    def _extract_system_and_user(self, messages: list[BaseMessage]) -> tuple[str, str]:
        sys_parts: list[str] = []
        user_parts: list[str] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                sys_parts.append(str(msg.content))
            elif isinstance(msg, HumanMessage):
                user_parts.append(str(msg.content))
            elif isinstance(msg, AIMessage):
                user_parts.append(f"Assistant: {msg.content}")
            else:
                user_parts.append(str(msg.content))
        return "\n\n".join(sys_parts), "\n\n".join(user_parts)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.llm_client is None:
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="Mock evaluation response"))]
            )

        if hasattr(self.llm_client, "is_available") and not self.llm_client.is_available():
            raise RuntimeError(f"Provider '{self.name}' is not configured or offline.")

        sys_inst, user_prompt = self._extract_system_and_user(messages)
        if hasattr(self.llm_client, "generate_text"):
            text = await self.llm_client.generate_text(
                system_instruction=sys_inst,
                user_prompt=user_prompt,
                temperature=self.temperature,
            )
        else:
            text = f"Automated response from {self.name}."

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.llm_client is None:
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="Mock evaluation response"))]
            )

        if hasattr(self.llm_client, "is_available") and not self.llm_client.is_available():
            raise RuntimeError(f"Provider '{self.name}' is not configured or offline.")

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self._agenerate(messages, stop=stop, **kwargs)
                ).result()

        return loop.run_until_complete(self._agenerate(messages, stop=stop, **kwargs))


def get_langchain_chat_model_for_provider(
    provider_name: str,
    temperature: float = 0.3,
) -> BaseChatModel:
    """Instantiate a LangChain BaseChatModel for a specific provider name (gemini, groq, openrouter, ollama)."""
    p = provider_name.lower().strip()
    if p == "gemini":
        return LangChainLLMAdapter(
            llm_client=GeminiClient(),
            temperature=temperature,
            name="gemini",
        )
    elif p == "groq":
        return LangChainLLMAdapter(
            llm_client=GroqClient(),
            temperature=temperature,
            name="groq",
        )
    elif p == "openrouter":
        return LangChainLLMAdapter(
            llm_client=OpenRouterClient(),
            temperature=temperature,
            name="openrouter",
        )
    elif p == "ollama":
        return LangChainLLMAdapter(
            llm_client=OllamaClient(),
            temperature=temperature,
            name="ollama",
        )
    return LangChainLLMAdapter(llm_client=None, temperature=temperature, name=p)


def get_fallback_models(
    primary_client: Any = None,
    fallback_order: list[str] | None = None,
    temperature: float = 0.3,
) -> tuple[BaseChatModel, list[BaseChatModel]]:
    """Resolve the primary model and fallback model list for ModelFallbackMiddleware.
    Default fallback sequence: gemini -> groq -> openrouter -> ollama.
    """
    if primary_client is False:
        mock_model = LangChainLLMAdapter(llm_client=None, temperature=temperature, name="mock")
        return mock_model, []

    order = fallback_order or [
        p.strip().lower()
        for p in settings.llm_fallback_order.split(",")
        if p.strip()
    ]
    if not order:
        order = ["openrouter", "gemini", "groq", "ollama"]

    if isinstance(primary_client, BaseLLMClient):
        if isinstance(primary_client, GeminiClient):
            client_name = "gemini"
        elif isinstance(primary_client, GroqClient):
            client_name = "groq"
        elif isinstance(primary_client, OpenRouterClient):
            client_name = "openrouter"
        elif isinstance(primary_client, OllamaClient):
            client_name = "ollama"
        elif isinstance(primary_client, FallbackLLMClient):
            client_name = primary_client.primary_name
        else:
            client_name = order[0]

        primary_model = LangChainLLMAdapter(
            llm_client=primary_client, temperature=temperature, name=client_name
        )
        remaining = [p for p in order if p != client_name]
        fallback_models = [
            get_langchain_chat_model_for_provider(p, temperature=temperature)
            for p in remaining
        ]
        return primary_model, fallback_models

    models = [
        get_langchain_chat_model_for_provider(p, temperature=temperature)
        for p in order
    ]
    primary_model = models[0]
    fallback_models = models[1:]
    return primary_model, fallback_models


def get_langchain_chat_model(
    llm_client: Any = None, temperature: float = 0.3
) -> BaseChatModel:
    """Helper to get a LangChain ChatModel wrapping the configured LLM client."""
    client = llm_client if llm_client is not None else get_llm_client()
    return LangChainLLMAdapter(llm_client=client, temperature=temperature)


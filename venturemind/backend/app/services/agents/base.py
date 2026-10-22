from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.schemas import AgentVerdict, DebateRound, ToolCallRecord
from app.services.llm_client import (
    BaseLLMClient,
    get_llm_client,
    LangChainLLMAdapter,
    get_fallback_models,
    extract_json_payload,
)
from app.services.agents.tools import (
    INVESTMENT_COMMITTEE_TOOLS,
    web_search_intel,
    lookup_competitor_traction,
    lookup_sec_edgar_tam,
    execute_and_track_tool,
    ToolCallTrackingCallbackHandler,
)


class AgentLLMResponse(BaseModel):
    score: float
    summary: str
    key_points: list[str]
    recommendation: str


def create_investment_committee_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[Any] | None = None,
    system_prompt: str | None = None,
    middleware: Sequence[Any] | None = None,
    fallback_models: Sequence[BaseChatModel] | None = None,
    llm_client: Any = None,
):
    """Factory creating an investment committee agent in idiomatic LangChain style

    configured with ModelFallbackMiddleware to gracefully fallback across Gemini, Groq, OpenRouter, and Ollama.

    Example:
        ```python
        from langchain.agents import create_agent
        from langchain.agents.middleware import ModelFallbackMiddleware

        agent = create_agent(
            model=primary_model,
            tools=[],
            middleware=[
                ModelFallbackMiddleware(
                    fallback_model_1,
                    fallback_model_2,
                ),
            ],
        )
        ```
    """
    if model is None:
        primary_model, default_fallbacks = get_fallback_models(primary_client=llm_client)
        active_fallbacks = fallback_models if fallback_models is not None else default_fallbacks
    else:
        primary_model = model
        active_fallbacks = fallback_models or []

    # Configure middleware: use custom middleware if provided, otherwise configure ModelFallbackMiddleware
    if middleware is not None:
        active_middleware = list(middleware)
    elif active_fallbacks:
        active_middleware = [
            ModelFallbackMiddleware(
                active_fallbacks[0],
                *active_fallbacks[1:],
            )
        ]
    else:
        active_middleware = []

    active_tools = list(tools) if tools is not None else list(INVESTMENT_COMMITTEE_TOOLS)

    return create_agent(
        model=primary_model,
        tools=active_tools,
        system_prompt=system_prompt,
        middleware=active_middleware,
    )


class Agent(ABC):
    name: str
    prompt_filename: str

    def __init__(
        self,
        llm_client: Any = None,
        tools: Sequence[Any] | None = None,
        middleware: Sequence[Any] | None = None,
        fallback_models: Sequence[BaseChatModel] | None = None,
    ):
        if llm_client is False:
            self.llm = None
        elif llm_client is not None:
            self.llm = llm_client
        else:
            self.llm = get_llm_client()

        prompt_dir = Path(__file__).resolve().parents[2] / "prompts"
        prompt_path = prompt_dir / self.prompt_filename
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        else:
            self.system_prompt = f"You are {self.name} on the investment committee."

        self.tools = list(tools) if tools is not None else list(INVESTMENT_COMMITTEE_TOOLS)
        self.tool_calls: list[ToolCallRecord] = []

        # Instantiate LangChain agent with ModelFallbackMiddleware
        self.langchain_agent = create_investment_committee_agent(
            tools=self.tools,
            system_prompt=self.system_prompt,
            middleware=middleware,
            fallback_models=fallback_models,
            llm_client=self.llm if self.llm is not None else False,
        )

    async def retrieve_context(self, startup_context: dict[str, Any], focus: str = "") -> str:
        """Retrieve competitor, TAM benchmarks, and market context from RAG layer and research tools."""
        self.tool_calls = []
        title = startup_context.get("title", "")
        description = startup_context.get("description", "")
        industry = startup_context.get("industry")
        industry_str = industry or "Technology"

        context_lines = [
            f"Title: {title}",
            f"Description: {description}",
            f"Industry: {industry_str}",
        ]

        # 1. RAG Knowledge Base Retrieval
        def _rag_find(title: str, description: str, industry: str | None) -> str:
            import app.rag.retrieval as rag_retrieval
            competitors = rag_retrieval.find_competitors(title=title, description=description, industry=industry, top_k=4)
            if competitors:
                lines = ["Known / Retrieved Competitors:"]
                for c in competitors:
                    lines.append(f"- {c.startup_name} ({c.industry}): {c.description} (Similarity: {c.similarity:.2f})")
                return "\n".join(lines)
            return "No direct competitors retrieved from knowledge base."

        try:
            rag_data, rag_rec = await execute_and_track_tool(
                tool_callable=_rag_find,
                input_parameters={"title": title, "description": description, "industry": industry},
                agent_name=self.name,
            )
            rag_rec.tool_name = "rag_knowledge_base"
            self.tool_calls.append(rag_rec)
            if rag_data and not rag_data.startswith("No direct"):
                context_lines.append(f"\n{rag_data}")
        except Exception:
            pass

        # 2. Tool Query: SEC EDGAR 10-K & Verified TAM Benchmarks
        try:
            sec_tam_data, sec_rec = await execute_and_track_tool(
                tool_callable=lookup_sec_edgar_tam,
                input_parameters={"sector_or_ticker": industry_str},
                agent_name=self.name,
            )
            self.tool_calls.append(sec_rec)
            if sec_tam_data:
                context_lines.append(f"\n{sec_tam_data}")
        except Exception:
            pass

        # 3. Tool Query: Competitor Traction & Product Hunt Metrics
        try:
            traction_data, trac_rec = await execute_and_track_tool(
                tool_callable=lookup_competitor_traction,
                input_parameters={
                    "company_or_category": title or industry_str,
                    "industry": industry,
                },
                agent_name=self.name,
            )
            self.tool_calls.append(trac_rec)
            if traction_data:
                context_lines.append(f"\n{traction_data}")
        except Exception:
            pass

        # 4. Tool Query: Live Web Search (if focus or title requires live funding or market intel)
        search_triggers = ["web", "news", "funding", "round", "venture", "growth", "market", "competition", "competitor"]
        if any(k in focus.lower() for k in search_triggers):
            try:
                # Tailor the search query and category based on agent perspective and focus
                if any(k in focus.lower() for k in ["risk", "downside", "competition", "cac", "threat"]) or "bear" in self.name.lower():
                    web_q = f"{title} {industry_str} competitor risks challenges market" if title else f"{industry_str} startup market risks"
                    search_type = "competitor_moves"
                elif "moat" in self.name.lower() or "defensibility" in focus.lower():
                    web_q = f"{title} {industry_str} competitors market defensibility" if title else f"{industry_str} market competitive moat"
                    search_type = "market_trends"
                else:
                    web_q = f"{title} {industry_str} funding round valuation" if title else f"{industry_str} venture funding rounds"
                    search_type = "funding_and_news"

                web_data, web_rec = await execute_and_track_tool(
                    tool_callable=web_search_intel,
                    input_parameters={"query": web_q, "search_type": search_type},
                    agent_name=self.name,
                )
                self.tool_calls.append(web_rec)
                if web_data:
                    context_lines.append(f"\n{web_data}")
            except Exception:
                pass

        return "\n".join(context_lines)

    async def _call_llm_structured(self, user_prompt: str) -> AgentVerdict:
        """Call configured LLM with LangChain agent and ModelFallbackMiddleware."""
        if self.llm is None:
            # Fallback mock for testing or when LLM is unconfigured
            return AgentVerdict(
                agent_name=self.name,
                score=7.5 if "Bull" in self.name else (5.0 if "Moat" in self.name else 6.0),
                summary=f"Automated evaluation from {self.name} (mock mode: start Ollama or configure GEMINI_API_KEY for live reasoning).",
                key_points=[
                    f"{self.name} primary observation based on provided idea parameters",
                    "Market positioning and opportunity analysis",
                    "Execution feasibility and risk parameters",
                ],
                recommendation=f"{self.name} standard recommendation for diligence.",
                tool_calls=list(self.tool_calls),
            )

        schema_json = json.dumps(AgentLLMResponse.model_json_schema())
        structured_prompt = (
            f"{user_prompt}\n\n"
            f"Respond strictly in JSON matching this schema:\n{schema_json}"
        )

        tracking_handler = ToolCallTrackingCallbackHandler(agent_name=self.name)

        try:
            # Invoke LangChain agent with ModelFallbackMiddleware
            result = await self.langchain_agent.ainvoke(
                {"messages": [HumanMessage(content=structured_prompt)]},
                config={"callbacks": [tracking_handler]},
            )
            last_message_content = result["messages"][-1].content
            clean_json = extract_json_payload(last_message_content)
            parsed_data = AgentLLMResponse.model_validate_json(clean_json)

            combined_tool_calls = list(self.tool_calls) + tracking_handler.tool_calls
            return AgentVerdict(
                agent_name=self.name,
                score=max(1.0, min(10.0, float(parsed_data.score))),
                summary=parsed_data.summary,
                key_points=parsed_data.key_points,
                recommendation=parsed_data.recommendation,
                tool_calls=combined_tool_calls,
            )
        except Exception:
            combined_tool_calls = list(self.tool_calls) + tracking_handler.tool_calls
            # Fallback to direct client call if agent parsing failed
            if isinstance(self.llm, BaseLLMClient):
                try:
                    parsed_data = await self.llm.generate_structured(
                        system_instruction=self.system_prompt,
                        user_prompt=user_prompt,
                        response_schema=AgentLLMResponse,
                        temperature=0.2,
                    )
                    return AgentVerdict(
                        agent_name=self.name,
                        score=max(1.0, min(10.0, float(parsed_data.score))),
                        summary=parsed_data.summary,
                        key_points=parsed_data.key_points,
                        recommendation=parsed_data.recommendation,
                        tool_calls=combined_tool_calls,
                    )
                except Exception as exc:
                    return AgentVerdict(
                        agent_name=self.name,
                        score=7.0 if "Bull" in self.name else 5.5,
                        summary=f"{self.name} evaluated the startup (LLM fallback: {exc}).",
                        key_points=["Identified primary market vectors", "Assessed initial risk-reward trade-offs"],
                        recommendation="Proceed with diligence.",
                        tool_calls=combined_tool_calls,
                    )

        return AgentVerdict(
            agent_name=self.name,
            score=7.0,
            summary=f"Automated evaluation from {self.name}.",
            key_points=["Core market observation"],
            recommendation="Proceed with diligence.",
            tool_calls=list(self.tool_calls) + tracking_handler.tool_calls,
        )

    @abstractmethod
    async def analyze(self, startup_context: dict[str, Any]) -> AgentVerdict:
        """Execute independent analysis of the startup."""
        ...

    async def critique(
        self,
        own_verdict: AgentVerdict,
        other_verdicts: list[AgentVerdict],
        prior_rounds: list[DebateRound] | None = None,
    ) -> str:
        """Used in the Debate & Cross-Critique step with LangChain agent and ModelFallbackMiddleware."""
        if self.llm is None:
            return (
                f"{self.name} critique: Acknowledged points from "
                f"{[v.agent_name for v in other_verdicts]}, maintaining thesis on core risk-reward trade-offs."
            )

        other_positions = "\n".join(
            f"- {v.agent_name} (Score: {v.score}/10): {v.summary}\n  Key points: {', '.join(v.key_points)}"
            for v in other_verdicts
        )

        history_section = ""
        if prior_rounds:
            history_lines = []
            for r in prior_rounds:
                history_lines.append(f"Round {r.round_number}:")
                for c in r.critiques:
                    history_lines.append(f"  * {c.agent_name}: {c.critique_text}")
            history_section = "Previous Debate Rounds:\n" + "\n".join(history_lines) + "\n\n"

        prompt = (
            f"Your initial position as {self.name} (Score: {own_verdict.score}/10):\n{own_verdict.summary}\n\n"
            f"Other committee members argued:\n{other_positions}\n\n"
            f"{history_section}"
            f"Provide a sharp, 2-3 sentence cross-critique defending your stance, challenging the other members' assumptions, "
            f"or noting any concessions."
        )

        try:
            # Run critique through LangChain agent with ModelFallbackMiddleware
            res = await self.langchain_agent.ainvoke({
                "messages": [HumanMessage(content=prompt)]
            })
            return res["messages"][-1].content.strip()
        except Exception:
            # Fallback to direct text call or graceful message
            if isinstance(self.llm, BaseLLMClient):
                try:
                    return await self.llm.generate_text(
                        system_instruction=self.system_prompt,
                        user_prompt=prompt,
                        temperature=0.3,
                    )
                except Exception as exc:
                    return f"{self.name} critique: Acknowledged peer arguments (LLM note: {exc})."

        return f"{self.name} critique: Defending core position while considering peer inputs."

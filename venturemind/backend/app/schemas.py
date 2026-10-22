"""Pydantic request/response schemas — the API contract."""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IdeaCreate(BaseModel):
    """Shape of the POST /ideas request body."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    industry: str = Field(min_length=1, max_length=100)


class IdeaResponse(BaseModel):
    """Shape of an idea returned to the client."""

    id: int
    title: str
    description: str
    industry: str
    created_at: datetime

    # Allow building this model directly from a SQLAlchemy ORM object.
    model_config = ConfigDict(from_attributes=True)


class ClassifyRequest(BaseModel):
    """Shape of the POST /classify-industry request body."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)


class ClassifyResponse(BaseModel):
    """Predicted industry with a confidence score in [0, 1]."""

    industry: str
    confidence: float = Field(ge=0.0, le=1.0)


class CompetitorQuery(BaseModel):
    """Shape of the POST /competitors request body."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    industry: str | None = Field(default=None, description="Optional sector filter")
    top_k: int = Field(default=5, ge=1, le=20)


class CompetitorOut(BaseModel):
    startup_name: str
    industry: str
    description: str
    similarity: float = Field(ge=0.0, le=1.0)


class CompetitorSearchResponse(BaseModel):
    query_title: str
    competitors: list[CompetitorOut]


class AnalyzeMarketRequest(BaseModel):
    """Shape of the POST /analyze-market request body.

    Only the idea is supplied by the client; the competitors are retrieved
    server-side, so the analysis is always grounded in the knowledge base rather
    than in anything the caller asserts.
    """

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    industry: str | None = Field(default=None, description="Optional sector filter for retrieval")
    top_k: int = Field(default=8, ge=1, le=20, description="Competitors to retrieve as context")


class CompetitorInsightOut(BaseModel):
    """One competitor-specific finding. ``competitor_name`` is always one of the
    retrieved competitors (enforced server-side)."""

    competitor_name: str
    relation: str


class MarketAnalysisResponse(BaseModel):
    """The four-part analysis plus the evidence it was grounded in.

    ``retrieved_competitors`` echoes the exact context fed to the model so the
    client can audit every claim against its source — a transparency guard that
    complements the server-side anti-hallucination checks.
    """

    idea_title: str
    industry: str | None
    market_summary: str
    competitor_analysis: list[CompetitorInsightOut]
    strengths: list[str]
    weaknesses: list[str]
    grounded: bool = Field(description="True when generated from a validated, non-empty retrieval set")
    model: str = Field(description="Gemini model id that produced the analysis (empty if not called)")
    retrieved_competitors: list[CompetitorOut]


class ViabilityRequest(BaseModel):
    """Shape of the POST /score-viability request body.

    All five sub-scores are analyst inputs in [0, 100]. Note the directionality:
    Demand, Scalability and Innovation are higher-is-better; Competition is
    market intensity (higher = more crowded = worse); Risk is overall risk
    (higher = riskier = worse).
    """

    demand: float = Field(ge=0, le=100, description="Market demand / pull (higher is better)")
    competition: float = Field(ge=0, le=100, description="Competitive intensity (higher = more crowded)")
    scalability: float = Field(ge=0, le=100, description="Ability to scale efficiently (higher is better)")
    innovation: float = Field(ge=0, le=100, description="Differentiation / moat (higher is better)")
    risk: float = Field(ge=0, le=100, description="Overall venture risk (higher = riskier)")


class FactorBreakdown(BaseModel):
    """One upside factor's contribution to the score."""

    factor: str
    raw: float
    direction: str = Field(description="'positive' (as-is) or 'inverse' (100 - raw)")
    adjusted: float = Field(description="Higher-is-better value after direction handling")
    weight: float
    contribution: float = Field(description="weight * adjusted — points of upside earned")
    max_contribution: float = Field(description="weight * 100 — most this factor could add")
    points_lost: float = Field(description="max_contribution - contribution — headroom left")


class ViabilityResponse(BaseModel):
    """The 0-100 Startup Viability Score with a full, explainable breakdown."""

    final_score: float = Field(ge=0, le=100)
    rating: str
    upside_score: float = Field(ge=0, le=100, description="Weighted upside before the risk discount")
    risk: float = Field(ge=0, le=100)
    risk_severity: float = Field(description="λ: fraction of upside removed at risk = 100")
    risk_multiplier: float = Field(description="1 - λ * risk/100, applied to the upside")
    risk_discount_points: float = Field(description="Points removed by the risk discount")
    breakdown: list[FactorBreakdown]
    summary: str


class MarketDemandRequest(BaseModel):
    """Shape of the POST /market-demand-score request body."""

    industry: str = Field(min_length=1, max_length=100)
    competitor_count: int = Field(
        ge=0, description="Number of known competitors in the market."
    )
    search_trend: float = Field(
        description="% change in search interest over the trailing window (e.g. 40 = +40%).",
    )
    market_growth: float = Field(
        description="Projected market CAGR in % (e.g. 18 = 18% per year).",
    )


class MarketDemandBreakdown(BaseModel):
    """The drivers behind the score — returned so it is never a black box."""

    industry_matched: str
    trend_score: float = Field(ge=0.0, le=100.0)
    growth_score: float = Field(ge=0.0, le=100.0)
    competition_score: float = Field(ge=0.0, le=100.0)
    weighted_base: float = Field(ge=0.0, le=100.0)
    multiplier: float
    weights: dict[str, float]


class MarketDemandResponse(BaseModel):
    """Market Demand Score in [0, 100] with a qualitative band and breakdown.

    The demand_score here is a natural upstream input to the `demand` field of
    POST /score-viability (both are 0-100, higher-is-better).
    """

    demand_score: float = Field(ge=0.0, le=100.0)
    band: str
    breakdown: MarketDemandBreakdown


# ---------------------------------------------------------------------------
# SWOT analysis (POST /swot-analysis)
# ---------------------------------------------------------------------------
class SwotCompetitorIn(BaseModel):
    """A competitor supplied by the caller as context for the analysis.

    Shaped to accept the output of /competitors with minimal massaging (a name
    plus an optional description). Unlike /analyze-market, the SWOT engine takes
    competitors as an *input* rather than retrieving them, so the caller controls
    the evidence set.
    """

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class SwotAnalysisRequest(BaseModel):
    """Shape of the POST /swot-analysis request body.

    Only the idea is required. ``competitors`` and ``market_context`` are optional
    context that sharpen the analysis — a SWOT of the bare idea is still valid,
    but the external quadrants (opportunities/threats) get much stronger with
    market context, and the internal ones (strengths/weaknesses) with competitors.
    """

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    industry: str | None = Field(default=None, max_length=100)
    competitors: list[SwotCompetitorIn] = Field(default_factory=list, max_length=20)
    market_context: str | None = Field(
        default=None,
        max_length=4000,
        description="Free-text market notes: size, growth, trends, regulation, timing.",
    )


class SwotItemOut(BaseModel):
    """One SWOT finding: the point itself plus why it matters.

    ``rationale`` keeps each finding auditable — it must trace back to the idea,
    a supplied competitor, or the market context, not to outside facts.
    """

    point: str = Field(description="The finding, stated as one concise phrase.")
    rationale: str = Field(description="One or two sentences grounding the point in the inputs.")


class SwotAnalysisResponse(BaseModel):
    """The four SWOT quadrants plus an honesty signal and provenance.

    Internal factors are strengths/weaknesses; external factors are
    opportunities/threats.
    """

    idea_title: str
    industry: str | None
    strengths: list[SwotItemOut]
    weaknesses: list[SwotItemOut]
    opportunities: list[SwotItemOut]
    threats: list[SwotItemOut]
    sufficient_context: bool = Field(
        description="The model's own signal that the inputs were rich enough to analyse well."
    )
    model: str = Field(description="Gemini model id that produced the analysis (empty if not called)")


# ---------------------------------------------------------------------------
# Multi-Agent Investment Committee schemas
# ---------------------------------------------------------------------------

class ToolCallRecord(BaseModel):
    """Details of a tool call initialization and the information retrieved."""

    tool_name: str = Field(description="Name of the tool that was called")
    input_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed when initializing the tool call",
    )
    status: str = Field(
        default="initialized",
        description="Execution status: initialized, completed, or failed",
    )
    retrieved_information: str | None = Field(
        default=None,
        description="Information / payload retrieved from the tool execution",
    )
    agent_name: str | None = Field(
        default=None,
        description="Name of the agent or component that initialized the tool call",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of tool initialization",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Execution duration in milliseconds",
    )


class AgentVerdict(BaseModel):
    """An individual agent's independent verdict on the startup."""

    agent_name: str = Field(description="Name of the agent (Bull Agent, Bear Agent, Moat Agent)")
    score: float = Field(ge=1.0, le=10.0, description="Score on a 1-10 scale")
    summary: str = Field(description="Concise thesis / positioning summary")
    key_points: list[str] = Field(description="Core arguments supporting the thesis")
    recommendation: str = Field(description="Actionable advice / stance")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Tool calls initialized by this agent and the information retrieved",
    )


class DebateCritique(BaseModel):
    """One agent's critique of the other committee members' verdicts."""

    agent_name: str
    critique_text: str


class DebateRound(BaseModel):
    """One round of cross-critique in the committee debate."""

    round_number: int = 1
    critiques: list[DebateCritique]


class InvestmentMemo(BaseModel):
    """Final synthesized investment committee memo and verdict."""

    startup_id: int
    startup_title: str
    industry: str
    overall_score: float = Field(ge=1.0, le=10.0, description="Lead partner consensus score (1-10)")
    verdict: str = Field(description="Decision: STRONG INVEST, INVEST WITH CONDITIONS, CAUTION / PASS, PASS")
    executive_summary: str
    key_strengths: list[str]
    key_risks: list[str]
    recommendations: list[str]
    agent_verdicts: list[AgentVerdict]
    debate_transcript: list[DebateRound]
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Consolidated tool calls initialized by committee agents and the information retrieved",
    )
    created_at: datetime


class WebSearchRequest(BaseModel):
    """Payload to initiate live web search intelligence."""

    query: str = Field(min_length=1, max_length=500, description="Web search query")
    search_type: str = Field(
        default="funding_and_news",
        description="Search category: funding_and_news, market_trends, or competitor_moves",
    )


class WebSearchResponse(BaseModel):
    """Result of live web search tool execution."""

    query: str
    search_type: str
    results: str
    tool_record: ToolCallRecord



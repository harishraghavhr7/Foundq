// Shared type definitions that mirror the backend API contract.

export interface IdeaCreate {
  title: string;
  description: string;
  industry: string;
}

export interface IdeaResponse extends IdeaCreate {
  id: number;
  created_at: string; // ISO timestamp
}

/**
 * A competitor company from the startup knowledge base
 * (startup_knowledge_base.csv). The forthcoming GET /competitors route should
 * serialize to this shape (the CSV's `startup_name` column maps to `name`).
 */
export interface Competitor {
  name: string;
  industry: string;
  description: string;
  website: string; // absolute URL
  country: string;
}

/** One item in a SWOT quadrant — a finding plus its rationale. */
export interface SwotItem {
  point: string; // The finding, stated as one concise phrase
  rationale: string; // One or two sentences grounding the point
}

/** SWOT analysis for an idea — four quadrants of findings with rationales. */
export interface SwotAnalysisResponse {
  idea_title: string;
  industry: string | null;
  strengths: SwotItem[];
  weaknesses: SwotItem[];
  opportunities: SwotItem[];
  threats: SwotItem[];
  sufficient_context: boolean;
  model: string;
}

export type Swot = SwotAnalysisResponse;

/** One factor's breakdown in viability scoring. */
export interface FactorBreakdown {
  factor: string;
  raw: number;
  direction: "positive" | "inverse";
  adjusted: number;
  weight: number;
  contribution: number;
  max_contribution: number;
  points_lost: number;
}

/** Market demand breakdown details. */
export interface MarketDemandBreakdown {
  industry_matched: string;
  trend_score: number;
  growth_score: number;
  competition_score: number;
  weighted_base: number;
  multiplier: number;
  weights: Record<string, number>;
}

/** Market demand assessment for an idea. */
export interface MarketDemandResponse {
  demand_score: number; // 0–100, higher is better
  band: string; // e.g. "Strong", "Moderate", "Weak"
  breakdown: MarketDemandBreakdown;
}

/** Overall viability assessment. */
export interface ViabilityResponse {
  final_score: number; // 0–100
  rating: string; // e.g. "Strong", "Promising", "Risky", "Weak"
  upside_score: number;
  risk: number;
  risk_severity: number;
  risk_multiplier: number;
  risk_discount_points: number;
  breakdown: FactorBreakdown[];
  summary: string;
}

export type DemandTrend = "rising" | "steady" | "declining";

export interface MarketSignal {
  label: string;
  value: string;
}

export interface MarketDemand {
  score: number; // 0–100
  trend: DemandTrend;
  summary: string;
  signals: MarketSignal[];
}

export interface ViabilityFactor {
  label: string;
  score: number; // 0–100
  weight: number; // 0–1, sum of all weights === 1
}

export interface ViabilityScore {
  score: number; // 0–100
  verdict: string; // "Strong" | "Promising" | "Risky" | "Weak"
  rationale: string;
  factors: ViabilityFactor[];
}

/** Multi-Agent Committee: Tool call initialization and retrieved information record */
export interface ToolCallRecord {
  tool_name: string;
  input_parameters: Record<string, any>;
  status: "initialized" | "completed" | "failed" | string;
  retrieved_information?: string | null;
  agent_name?: string | null;
  timestamp?: string;
  latency_ms?: number | null;
}

/** Multi-Agent Committee: individual agent verdict */
export interface AgentVerdict {
  agent_name: string;
  score: number; // 1-10
  summary: string;
  key_points: string[];
  recommendation: string;
  tool_calls?: ToolCallRecord[];
}

/** Multi-Agent Committee: debate critique statement */
export interface DebateCritique {
  agent_name: string;
  critique_text: string;
}

/** Multi-Agent Committee: debate round */
export interface DebateRound {
  round_number: number;
  critiques: DebateCritique[];
}

/** Final Lead Partner Investment Memo */
export interface InvestmentMemo {
  startup_id: number;
  startup_title: string;
  industry: string;
  overall_score: number; // 1-10
  verdict: "STRONG INVEST" | "INVEST WITH CONDITIONS" | "CAUTION / PASS" | "PASS" | string;
  executive_summary: string;
  key_strengths: string[];
  key_risks: string[];
  recommendations: string[];
  agent_verdicts: AgentVerdict[];
  debate_transcript: DebateRound[];
  tool_calls?: ToolCallRecord[];
  created_at: string;
}



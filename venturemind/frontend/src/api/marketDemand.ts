// Stub client for market-demand analysis.
//
// No backend route yet. We derive a *deterministic* score per idea (industry
// baseline + a stable hash-based jitter) so the same idea always reports the
// same demand — important for a believable demo. Swap for a real request
// (e.g. POST /analyze/demand) when the route ships.
import type { DemandTrend, IdeaResponse, MarketDemand } from "../types";

const INDUSTRY_DEMAND: Record<string, { base: number; trend: DemandTrend }> = {
  EdTech: { base: 72, trend: "steady" },
  FinTech: { base: 81, trend: "rising" },
  HealthTech: { base: 78, trend: "rising" },
  AgriTech: { base: 64, trend: "steady" },
  SaaS: { base: 75, trend: "steady" },
  "E-commerce": { base: 69, trend: "declining" },
};

const FALLBACK: { base: number; trend: DemandTrend } = { base: 60, trend: "steady" };

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Stable string hash so a given idea always yields the same jitter.
function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export async function analyzeMarketDemand(idea: IdeaResponse): Promise<MarketDemand> {
  await delay(750);

  const { base, trend } = INDUSTRY_DEMAND[idea.industry] ?? FALLBACK;
  const jitter = (hashString(`${idea.title}/${idea.industry}`) % 13) - 6; // ±6
  const score = clamp(base + jitter, 0, 100);

  const urgency = score >= 75 ? "Strong" : score >= 60 ? "Moderate" : "Emerging";
  const searchInterest: Record<DemandTrend, string> = {
    rising: "High and rising",
    steady: "Solid and stable",
    declining: "Softening",
  };
  const summaryTail: Record<DemandTrend, string> = {
    rising: "strong and accelerating",
    steady: "healthy and stable",
    declining: "mature and competitive",
  };

  return {
    score,
    trend,
    summary: `${idea.industry} demand looks ${summaryTail[trend]}, with buyer urgency rated ${urgency.toLowerCase()}.`,
    signals: [
      { label: "Search interest", value: searchInterest[trend] },
      { label: "Buyer urgency", value: urgency },
      { label: "Market maturity", value: trend === "declining" ? "Mature" : "Growing" },
      { label: "Competition", value: "Established players present" },
    ],
  };
}

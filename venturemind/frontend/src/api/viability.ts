// Stub client for the viability score.
//
// Viability is an *aggregate* of the other signals, so this stub reuses the
// real demand score (analyzeMarketDemand) and derives the remaining factors
// deterministically — the same idea always yields the same verdict, and the
// "Market demand" factor matches what the Market Demand section displays.
// Replace with a real request (e.g. POST /analyze/viability) when it ships.
import type { IdeaResponse, ViabilityFactor, ViabilityScore } from "../types";
import { analyzeMarketDemand } from "./marketDemand";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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

function verdictFor(score: number): string {
  if (score >= 75) return "Strong";
  if (score >= 60) return "Promising";
  if (score >= 45) return "Risky";
  return "Weak";
}

export async function analyzeViability(idea: IdeaResponse): Promise<ViabilityScore> {
  const demand = await analyzeMarketDemand(idea); // reuse → demand factor stays coherent
  await delay(400); // a little extra for the "aggregation" step

  const seed = hashString(`${idea.title}|${idea.industry}`);
  const competition = clamp(70 - (seed % 25), 0, 100); // fewer incumbents → more room
  const differentiation = clamp(55 + (seed % 30), 0, 100);
  const execution = clamp(60 + ((seed >> 3) % 25), 0, 100);

  const factors: ViabilityFactor[] = [
    { label: "Market demand", score: demand.score, weight: 0.35 },
    { label: "Competitive room", score: competition, weight: 0.25 },
    { label: "Differentiation", score: differentiation, weight: 0.25 },
    { label: "Execution readiness", score: execution, weight: 0.15 },
  ];

  const score = Math.round(factors.reduce((sum, f) => sum + f.score * f.weight, 0));
  const verdict = verdictFor(score);

  return {
    score,
    verdict,
    rationale: `Weighted across demand, competitive room, differentiation, and execution, “${idea.title}” scores ${score}/100 — ${verdict.toLowerCase()}.`,
    factors,
  };
}

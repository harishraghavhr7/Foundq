// Stub client for SWOT analysis.
//
// No backend route exists yet, so we synthesize an idea-aware SWOT (seeded by
// title + industry) to render the dashboard. Replace the body with a real
// request — e.g. POST /analyze/swot — when the route ships.
import type { IdeaResponse, Swot } from "../types";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function analyzeSwot(idea: IdeaResponse): Promise<Swot> {
  await delay(900); // SWOT "analysis" runs a touch slower than a lookup

  const { title, industry } = idea;

  return {
    strengths: [
      `Sharp focus on ${industry} with “${title}” as a clear wedge.`,
      "Lean software model keeps marginal costs low and iteration fast.",
      "Early-mover positioning helps shape the category narrative.",
    ],
    weaknesses: [
      "Pre-revenue — brand trust and distribution still have to be earned.",
      "A small team concentrates execution and key-person risk.",
      `Easy to blend into a crowded ${industry} field without sharp differentiation.`,
    ],
    opportunities: [
      `Rising ${industry} demand leaves room for a focused niche player.`,
      "Integrations and partnerships can shortcut distribution.",
      "AI-assisted features can compound into a durable moat.",
    ],
    threats: [
      `Well-funded incumbents already operate across ${industry}.`,
      "Low switching costs make early retention fragile.",
      "Regulatory or platform-policy shifts could reset unit economics.",
    ],
  };
}

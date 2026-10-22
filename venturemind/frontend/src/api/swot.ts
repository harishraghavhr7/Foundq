// Real API client for SWOT analysis calling the FastAPI Gemini backend.
import type { IdeaResponse, SwotAnalysisResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function analyzeSwot(idea: IdeaResponse): Promise<SwotAnalysisResponse> {
  const res = await fetch(`${API_BASE_URL}/swot-analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: idea.title,
      description: idea.description,
      industry: idea.industry,
    }),
  });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail);
  }

  return res.json();
}


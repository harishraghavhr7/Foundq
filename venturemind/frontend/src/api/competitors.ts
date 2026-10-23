// Live API client for competitor lookups using live web search intelligence.
import type { Competitor } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface CompetitorLookupParams {
  title: string;
  description: string;
  industry?: string;
  top_k?: number;
}

/**
 * Return live web search-discovered competitors for the startup idea.
 */
export async function fetchCompetitors(
  params: CompetitorLookupParams | string
): Promise<Competitor[]> {
  const payload =
    typeof params === "string"
      ? { title: params, description: params, industry: params, top_k: 4 }
      : {
          title: params.title,
          description: params.description,
          industry: params.industry,
          top_k: params.top_k ?? 4,
        };

  const res = await fetch(`${API_BASE_URL}/competitors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

  const data = await res.json();
  const rawList = data.competitors || [];

  return rawList.map((c: any) => ({
    name: c.name || c.startup_name || "Competitor",
    industry: c.industry || payload.industry || "Technology",
    description: c.description || "Active competitor identified via live web search.",
    website: c.website && c.website.startsWith("http") ? c.website : (c.website ? `https://${c.website}` : "https://www.google.com"),
    country: c.country || "Global",
  }));
}

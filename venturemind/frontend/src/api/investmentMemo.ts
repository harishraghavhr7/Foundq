import type { InvestmentMemo } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function analyzeStartup(
  startupId: number,
  forceRefresh: boolean = false
): Promise<InvestmentMemo> {
  const queryParam = forceRefresh ? "?force_refresh=true" : "";
  const url = `${API_BASE_URL}/startups/${startupId}/analyze${queryParam}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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


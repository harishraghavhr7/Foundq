// Thin API client for the ideas endpoints.
import type { IdeaCreate, IdeaResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function submitIdea(idea: IdeaCreate): Promise<IdeaResponse> {
  const res = await fetch(`${API_BASE_URL}/ideas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(idea),
  });

  if (!res.ok) {
    // Surface FastAPI's error detail when available.
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail);
  }

  return res.json();
}

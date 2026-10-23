import SectionCard from "./ui/SectionCard";
import CompetitorCard from "./CompetitorCard";
import { useAsync } from "../hooks/useAsync";
import { fetchCompetitors } from "../api/competitors";
import type { IdeaResponse } from "../types";

interface CompetitorsSectionProps {
  /** The analyzed idea, or null before one is submitted. */
  idea: IdeaResponse | null;
}

export default function CompetitorsSection({ idea }: CompetitorsSectionProps) {
  const { status, data, error } = useAsync(
    () => fetchCompetitors(idea!),
    [idea?.id, idea?.title, idea?.description, idea?.industry],
    { enabled: !!idea, errorMessage: "Failed to load competitors from web search." },
  );

  const competitors = data ?? [];
  const count = competitors.length;

  return (
    <SectionCard
      title="Competitors"
      icon="🥊"
      description={idea ? `Live web search intelligence on competitors in ${idea.industry}.` : undefined}
      status={status}
      error={error}
      emptyMessage="Submit an idea to scan the web for real-time competitors."
      loadingMessage="Searching the live web for market competitors…"
      accessory={
        status === "ready" && count > 0 ? (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
            {count} found
          </span>
        ) : undefined
      }
    >
      {count === 0 ? (
        <p className="text-sm text-slate-400">
          No direct competitors discovered on the web for {idea?.industry ?? "this vertical"} yet — that could be
          untapped market whitespace, or a sign to sharpen the search query.
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {competitors.map((competitor) => (
            <CompetitorCard key={competitor.name} competitor={competitor} />
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

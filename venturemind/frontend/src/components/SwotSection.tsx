import SectionCard from "./ui/SectionCard";
import SwotQuadrant from "./SwotQuadrant";
import { useAsync } from "../hooks/useAsync";
import { analyzeSwot } from "../api/swot";
import type { IdeaResponse, Swot } from "../types";

interface QuadrantConfig {
  key: "strengths" | "weaknesses" | "opportunities" | "threats";
  label: string;
  icon: string;
  headerClass: string;
  boxClass: string;
}

// Static class strings (never interpolated) so Tailwind's purge keeps them.
const QUADRANTS: QuadrantConfig[] = [
  { key: "strengths", label: "Strengths", icon: "💪", headerClass: "text-emerald-700", boxClass: "border-emerald-100 bg-emerald-50/60" },
  { key: "weaknesses", label: "Weaknesses", icon: "⚠️", headerClass: "text-rose-700", boxClass: "border-rose-100 bg-rose-50/60" },
  { key: "opportunities", label: "Opportunities", icon: "🚀", headerClass: "text-sky-700", boxClass: "border-sky-100 bg-sky-50/60" },
  { key: "threats", label: "Threats", icon: "🛡️", headerClass: "text-amber-700", boxClass: "border-amber-100 bg-amber-50/60" },
];

interface SwotSectionProps {
  /** The analyzed idea, or null before one is submitted. */
  idea: IdeaResponse | null;
}

export default function SwotSection({ idea }: SwotSectionProps) {
  const { status, data, error } = useAsync<Swot>(
    () => analyzeSwot(idea!),
    [idea?.id],
    { enabled: !!idea, errorMessage: "Failed to analyze SWOT." },
  );

  return (
    <SectionCard
      title="SWOT Analysis"
      icon="🧭"
      description={idea ? `Strategic snapshot for “${idea.title}”.` : undefined}
      status={status}
      error={error}
      emptyMessage="Submit an idea to generate a SWOT analysis."
      loadingMessage="Weighing strengths, weaknesses, opportunities, threats…"
    >
      {data && (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {QUADRANTS.map((quadrant) => (
              <SwotQuadrant
                key={quadrant.key}
                label={quadrant.label}
                icon={quadrant.icon}
                items={data[quadrant.key]}
                headerClass={quadrant.headerClass}
                boxClass={quadrant.boxClass}
              />
            ))}
          </div>
          {data.model && (
            <div className="flex items-center justify-between text-xs text-slate-400 pt-1 px-1">
              <span>Grounded analysis via {data.model}</span>
              {data.sufficient_context ? (
                <span className="text-emerald-600 font-medium">✓ High context grounding</span>
              ) : (
                <span className="text-amber-600 font-medium">⚠️ Limited context available</span>
              )}
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}

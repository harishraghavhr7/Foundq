import SectionCard from "./ui/SectionCard";
import ScoreGauge from "./ScoreGauge";
import { useAsync } from "../hooks/useAsync";
import { analyzeViability } from "../api/viability";
import type { IdeaResponse, ViabilityScore } from "../types";

// Static verdict → badge classes (never interpolated) so Tailwind keeps them.
const VERDICT_CLASS: Record<string, string> = {
  Strong: "bg-emerald-50 text-emerald-700",
  Promising: "bg-sky-50 text-sky-700",
  Risky: "bg-amber-50 text-amber-700",
  Weak: "bg-rose-50 text-rose-700",
};

interface ViabilityScoreSectionProps {
  /** The analyzed idea, or null before one is submitted. */
  idea: IdeaResponse | null;
}

export default function ViabilityScoreSection({ idea }: ViabilityScoreSectionProps) {
  const { status, data, error } = useAsync<ViabilityScore>(
    () => analyzeViability(idea!),
    [idea?.id],
    { enabled: !!idea, errorMessage: "Failed to compute the viability score." },
  );

  return (
    <SectionCard
      title="Viability Score"
      icon="🎯"
      description={idea ? `Overall investability for “${idea.title}”.` : undefined}
      status={status}
      error={error}
      emptyMessage="Submit an idea to compute its viability score."
      loadingMessage="Crunching the viability score…"
    >
      {data && (
        <div className="flex flex-col items-center gap-6 sm:flex-row">
          <div className="flex flex-col items-center gap-2">
            <ScoreGauge score={data.score} />
            <span
              className={`rounded-full px-3 py-1 text-sm font-semibold ${
                VERDICT_CLASS[data.verdict] ?? "bg-slate-100 text-slate-600"
              }`}
            >
              {data.verdict}
            </span>
          </div>

          <div className="flex-1 space-y-3 self-stretch">
            <p className="text-sm text-slate-600">{data.rationale}</p>
            <ul className="space-y-2.5">
              {data.factors.map((factor) => (
                <li key={factor.label}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-600">{factor.label}</span>
                    <span className="tabular-nums text-slate-400">
                      {factor.score} · {Math.round(factor.weight * 100)}% weight
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-slate-700"
                      style={{ width: `${factor.score}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

import SectionCard from "./ui/SectionCard";
import DemandMeter from "./DemandMeter";
import { useAsync } from "../hooks/useAsync";
import { analyzeMarketDemand } from "../api/marketDemand";
import type { IdeaResponse, MarketDemand } from "../types";

interface MarketDemandSectionProps {
  /** The analyzed idea, or null before one is submitted. */
  idea: IdeaResponse | null;
}

export default function MarketDemandSection({ idea }: MarketDemandSectionProps) {
  const { status, data, error } = useAsync<MarketDemand>(
    () => analyzeMarketDemand(idea!),
    [idea?.id],
    { enabled: !!idea, errorMessage: "Failed to gauge market demand." },
  );

  return (
    <SectionCard
      title="Market Demand"
      icon="📈"
      description={idea ? `How hungry is the ${idea.industry} market right now?` : undefined}
      status={status}
      error={error}
      emptyMessage="Submit an idea to gauge market demand."
      loadingMessage="Gauging market demand…"
    >
      {data && (
        <div className="space-y-4">
          <DemandMeter score={data.score} trend={data.trend} />
          <p className="text-sm text-slate-600">{data.summary}</p>
          <dl className="grid grid-cols-2 gap-3">
            {data.signals.map((signal) => (
              <div key={signal.label} className="rounded-lg border border-slate-200 px-3 py-2">
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  {signal.label}
                </dt>
                <dd className="mt-0.5 text-sm font-medium text-slate-800">{signal.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </SectionCard>
  );
}

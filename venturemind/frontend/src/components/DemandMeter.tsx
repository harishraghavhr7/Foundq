import type { DemandTrend } from "../types";

// Static class strings keyed by trend so Tailwind's purge keeps them.
const TREND_META: Record<DemandTrend, { label: string; icon: string; className: string }> = {
  rising: { label: "Rising", icon: "↑", className: "bg-emerald-50 text-emerald-700" },
  steady: { label: "Steady", icon: "→", className: "bg-slate-100 text-slate-600" },
  declining: { label: "Declining", icon: "↓", className: "bg-amber-50 text-amber-700" },
};

interface DemandMeterProps {
  score: number; // 0–100
  trend: DemandTrend;
}

/** A labeled demand gauge: a colored progress bar, numeric score, and trend pill. */
export default function DemandMeter({ score, trend }: DemandMeterProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const barColor =
    clamped >= 75 ? "bg-emerald-500" : clamped >= 55 ? "bg-amber-500" : "bg-rose-500";
  const meta = TREND_META[trend];

  return (
    <div>
      <div className="mb-1.5 flex items-end justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
          Demand score
        </span>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${meta.className}`}
        >
          <span aria-hidden>{meta.icon}</span>
          {meta.label}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div
          className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100"
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Market demand score"
        >
          <div
            className={`h-full rounded-full transition-all ${barColor}`}
            style={{ width: `${clamped}%` }}
          />
        </div>
        <span className="w-12 text-right text-lg font-bold tabular-nums text-slate-900">
          {clamped}
        </span>
      </div>
    </div>
  );
}

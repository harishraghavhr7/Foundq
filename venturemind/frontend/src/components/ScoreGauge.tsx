interface ScoreGaugeProps {
  score: number; // 0–100
}

/** A circular SVG gauge showing a 0–100 score, color-banded by value. */
export default function ScoreGauge({ score }: ScoreGaugeProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));

  const size = 160;
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  const arcColor =
    clamped >= 75
      ? "text-emerald-500"
      : clamped >= 60
        ? "text-amber-500"
        : clamped >= 45
          ? "text-orange-500"
          : "text-rose-500";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-slate-100"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`${arcColor} transition-all duration-700`}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-4xl font-bold tabular-nums text-slate-900">{clamped}</span>
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">/ 100</span>
      </div>
    </div>
  );
}

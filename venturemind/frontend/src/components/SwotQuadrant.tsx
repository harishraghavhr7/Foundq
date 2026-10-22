import type { SwotItem } from "../types";

interface SwotQuadrantProps {
  label: string;
  icon: string;
  items: (string | SwotItem)[];
  /** Tailwind text-color class for the header (e.g. "text-emerald-700"). */
  headerClass: string;
  /** Tailwind border/background classes for the quadrant box. */
  boxClass: string;
}

/** One of the four SWOT quadrants: a colored box with a bulleted list. */
export default function SwotQuadrant({ label, icon, items, headerClass, boxClass }: SwotQuadrantProps) {
  return (
    <div className={`rounded-xl border p-4 ${boxClass}`}>
      <h3 className={`mb-2.5 flex items-center gap-1.5 text-sm font-semibold ${headerClass}`}>
        <span aria-hidden>{icon}</span>
        {label}
      </h3>

      {items.length === 0 ? (
        <p className="text-sm text-slate-400">—</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, index) => {
            const isString = typeof item === "string";
            const point = isString ? item : item.point;
            const rationale = isString ? null : item.rationale;

            return (
              <li key={index} className="flex items-start gap-2 text-sm text-slate-700">
                <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                <div className="leading-snug">
                  <span className="font-medium text-slate-900">{point}</span>
                  {rationale && (
                    <p className="mt-0.5 text-xs text-slate-500">{rationale}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}


interface SwotQuadrantProps {
  label: string;
  icon: string;
  items: string[];
  /** Tailwind text-color class for the header (e.g. "text-emerald-700"). */
  headerClass: string;
  /** Tailwind border/background classes for the quadrant box. */
  boxClass: string;
}

/** One of the four SWOT quadrants: a colored box with a bulleted list. */
export default function SwotQuadrant({ label, icon, items, headerClass, boxClass }: SwotQuadrantProps) {
  return (
    <div className={`rounded-xl border p-4 ${boxClass}`}>
      <h3 className={`mb-2 flex items-center gap-1.5 text-sm font-semibold ${headerClass}`}>
        <span aria-hidden>{icon}</span>
        {label}
      </h3>

      {items.length === 0 ? (
        <p className="text-sm text-slate-400">—</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item, index) => (
            <li key={index} className="flex gap-2 text-sm text-slate-700">
              <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

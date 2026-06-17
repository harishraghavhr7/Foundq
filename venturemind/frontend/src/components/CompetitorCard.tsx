import type { Competitor } from "../types";

/** A single competitor, rendered as a list item inside CompetitorsSection. */
export default function CompetitorCard({ competitor }: { competitor: Competitor }) {
  const { name, description, website, country } = competitor;

  return (
    <li className="rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h3 className="truncate font-semibold text-slate-900">{name}</h3>
        <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {country}
        </span>
      </div>

      <p className="mt-1.5 line-clamp-3 text-sm text-slate-600">{description}</p>

      <a
        href={website}
        target="_blank"
        rel="noreferrer noopener"
        className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700"
      >
        Visit site
        <span aria-hidden>↗</span>
      </a>
    </li>
  );
}

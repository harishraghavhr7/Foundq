import type { ReactNode } from "react";

/**
 * Lifecycle of an async-backed section.
 * Omit `status` entirely for static sections (e.g. the idea form), in which
 * case `children` always render.
 */
export type SectionStatus = "idle" | "loading" | "error" | "ready";

interface SectionCardProps {
  /** Section heading, e.g. "Competitors". */
  title: string;
  /** Optional one-line description rendered under the title. */
  description?: string;
  /** Optional leading glyph (emoji or icon node) shown before the title. */
  icon?: ReactNode;
  /** Optional right-aligned slot: a badge, score, or action button. */
  accessory?: ReactNode;
  /**
   * Async lifecycle. When provided, the card renders the matching placeholder
   * for "idle" | "loading" | "error" and only shows `children` when "ready".
   * When omitted, `children` always render.
   */
  status?: SectionStatus;
  /** Message for the "idle" (not-yet-run) state. */
  emptyMessage?: string;
  /** Message for the "loading" state. */
  loadingMessage?: string;
  /** Error text for the "error" state. */
  error?: string;
  /** Extra classes for the outer card — handy for grid column spans. */
  className?: string;
  /** Ready-state content. */
  children?: ReactNode;
}

/**
 * Reusable section chrome for the dashboard: a titled card that also knows how
 * to render idle / loading / error placeholders. Every dashboard section
 * (Idea Form, Competitors, SWOT, Market Demand, Viability Score) is composed
 * inside one of these so spacing, headers, and async states stay consistent.
 */
export default function SectionCard({
  title,
  description,
  icon,
  accessory,
  status,
  emptyMessage = "No data yet.",
  loadingMessage = "Loading…",
  error,
  className = "",
  children,
}: SectionCardProps) {
  return (
    <section
      aria-busy={status === "loading"}
      className={`flex flex-col rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}
    >
      <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            {icon && (
              <span aria-hidden className="text-lg leading-none">
                {icon}
              </span>
            )}
            <span className="truncate">{title}</span>
          </h2>
          {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
        </div>
        {accessory && <div className="shrink-0">{accessory}</div>}
      </header>

      <div className="px-5 py-4">
        <SectionBody
          status={status}
          emptyMessage={emptyMessage}
          loadingMessage={loadingMessage}
          error={error}
        >
          {children}
        </SectionBody>
      </div>
    </section>
  );
}

function SectionBody({
  status,
  emptyMessage,
  loadingMessage,
  error,
  children,
}: {
  status?: SectionStatus;
  emptyMessage: string;
  loadingMessage: string;
  error?: string;
  children?: ReactNode;
}) {
  if (status === "loading") {
    return (
      <div role="status" className="flex items-center gap-3 text-sm text-slate-500">
        <Spinner />
        <span>{loadingMessage}</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
        {error ?? "Something went wrong."}
      </p>
    );
  }

  if (status === "idle") {
    return <p className="text-sm text-slate-400">{emptyMessage}</p>;
  }

  return <>{children}</>;
}

function Spinner() {
  return (
    <span
      aria-hidden
      className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
    />
  );
}

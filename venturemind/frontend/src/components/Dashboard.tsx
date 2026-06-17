import { useState } from "react";
import IdeaForm from "./IdeaForm";
import CompetitorsSection from "./CompetitorsSection";
import SwotSection from "./SwotSection";
import MarketDemandSection from "./MarketDemandSection";
import ViabilityScoreSection from "./ViabilityScoreSection";
import type { IdeaResponse } from "../types";

/**
 * Top-level dashboard. Owns the single piece of shared state — the analyzed
 * idea — and feeds it to every analysis section. Submitting the form sets the
 * idea, which lights up all four sections (they each load independently).
 */
export default function Dashboard() {
  const [currentIdea, setCurrentIdea] = useState<IdeaResponse | null>(null);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">VentureMind</h1>
        <p className="mt-1 text-sm text-slate-500">
          Pressure-test your startup idea — competitors, SWOT, market demand, and a viability
          score, all in one place.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Input column — sticks in view while you scroll the results on large screens. */}
        <div className="lg:col-span-4 lg:sticky lg:top-8 lg:self-start">
          <IdeaForm onAnalyzed={(idea) => setCurrentIdea(idea)} />
        </div>

        {/* Results column — the four analysis sections, in the requested order. */}
        <div className="grid gap-6 lg:col-span-8">
          <CompetitorsSection idea={currentIdea} />
          <SwotSection idea={currentIdea} />
          <MarketDemandSection idea={currentIdea} />
          <ViabilityScoreSection idea={currentIdea} />
        </div>
      </div>
    </div>
  );
}

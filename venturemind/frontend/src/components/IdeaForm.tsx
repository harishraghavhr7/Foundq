import { useState, type FormEvent } from "react";
import SectionCard from "./ui/SectionCard";
import { submitIdea } from "../api/ideas";
import type { IdeaCreate, IdeaResponse } from "../types";

// Mirror the backend's supported industries (industry_classifier.SUPPORTED_INDUSTRIES)
// so submitted ideas line up with the competitor knowledge base and classifier.
const INDUSTRIES = ["EdTech", "FinTech", "HealthTech", "AgriTech", "SaaS", "E-commerce"] as const;

type SubmitState =
  | { kind: "idle" | "submitting" }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

interface IdeaFormProps {
  /**
   * Fired after an idea is successfully persisted. The dashboard uses this to
   * kick off the competitor / SWOT / demand / viability pipeline. Optional so
   * the form still works standalone.
   */
  onAnalyzed?: (idea: IdeaResponse) => void;
}

const fieldLabel = "grid gap-1.5 text-sm font-medium text-slate-700";
const inputBase =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm " +
  "placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200 " +
  "disabled:cursor-not-allowed disabled:bg-slate-50";

export default function IdeaForm({ onAnalyzed }: IdeaFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [industry, setIndustry] = useState<string>(INDUSTRIES[0]);
  const [state, setState] = useState<SubmitState>({ kind: "idle" });

  const submitting = state.kind === "submitting";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setState({ kind: "submitting" });

    const payload: IdeaCreate = {
      title: title.trim(),
      description: description.trim(),
      industry,
    };

    try {
      const idea = await submitIdea(payload);
      setState({ kind: "success", message: `Idea #${idea.id} submitted — analyzing “${idea.title}”.` });
      onAnalyzed?.(idea);
    } catch (err) {
      setState({ kind: "error", message: err instanceof Error ? err.message : "Submission failed." });
    }
  }

  return (
    <SectionCard
      title="Your Startup Idea"
      icon="💡"
      description="Describe your idea — we'll size up the competition, SWOT, demand, and viability."
    >
      <form onSubmit={handleSubmit} className="grid gap-4">
        <label className={fieldLabel}>
          Startup title
          <input
            className={inputBase}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
            disabled={submitting}
            placeholder="e.g. AI Resume Builder"
          />
        </label>

        <label className={fieldLabel}>
          Description
          <textarea
            className={`${inputBase} resize-y`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            rows={4}
            disabled={submitting}
            placeholder="What does it do, and for whom?"
          />
        </label>

        <label className={fieldLabel}>
          Industry
          <select
            className={inputBase}
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            disabled={submitting}
          >
            {INDUSTRIES.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </label>

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Analyzing…" : "Analyze idea"}
        </button>

        {state.kind === "success" && (
          <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {state.message}
          </p>
        )}
        {state.kind === "error" && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {state.message}
          </p>
        )}
      </form>
    </SectionCard>
  );
}

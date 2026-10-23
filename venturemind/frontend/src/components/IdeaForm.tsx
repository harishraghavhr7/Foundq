import { useState, type FormEvent } from "react";
import SectionCard from "./ui/SectionCard";
import { submitIdea } from "../api/ideas";
import type { IdeaCreate, IdeaResponse } from "../types";


type SubmitState =
  | { kind: "idle" | "submitting" }
  | { kind: "success"; message: string; industry?: string }
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
  const [state, setState] = useState<SubmitState>({ kind: "idle" });

  const submitting = state.kind === "submitting";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setState({ kind: "submitting" });

    const payload: IdeaCreate = {
      title: title.trim(),
      description: description.trim(),
    };

    try {
      const idea = await submitIdea(payload);
      setState({
        kind: "success",
        message: `Idea #${idea.id} submitted — analyzing “${idea.title}”.`,
        industry: idea.industry,
      });
      onAnalyzed?.(idea);
    } catch (err) {
      setState({ kind: "error", message: err instanceof Error ? err.message : "Submission failed." });
    }
  }

  return (
    <SectionCard
      title="Your Startup Idea"
      icon="💡"
      description="Describe your idea — our AI automatically detects your industry and discovers live web competitors."
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

        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="inline-block text-blue-500">✦</span>
          <span>Industry will be automatically classified by AI upon analysis</span>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Analyzing…" : "Analyze idea"}
        </button>

        {state.kind === "success" && (
          <div role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800 border border-emerald-200">
            <p className="font-medium">{state.message}</p>
            {state.industry && (
              <p className="mt-1 text-xs text-emerald-700 flex items-center gap-1.5">
                <span className="font-semibold uppercase tracking-wider text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                  Auto-Detected Sector
                </span>
                <span>{state.industry}</span>
              </p>
            )}
          </div>
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

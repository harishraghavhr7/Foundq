import { useState } from "react";
import SectionCard from "./ui/SectionCard";
import { useAsync } from "../hooks/useAsync";
import { analyzeStartup } from "../api/investmentMemo";
import type { IdeaResponse, InvestmentMemo } from "../types";

interface InvestmentMemoSectionProps {
  idea: IdeaResponse | null;
}

const VERDICT_STYLES: Record<string, string> = {
  "STRONG INVEST": "bg-emerald-100 text-emerald-800 border-emerald-300",
  "INVEST WITH CONDITIONS": "bg-sky-100 text-sky-800 border-sky-300",
  "CAUTION / PASS": "bg-amber-100 text-amber-800 border-amber-300",
  "PASS": "bg-rose-100 text-rose-800 border-rose-300",
};

const AGENT_STYLES: Record<string, { badge: string; border: string; icon: string }> = {
  "Bull Agent": {
    badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
    border: "border-emerald-200 bg-emerald-50/20",
    icon: "🐂",
  },
  "Bear Agent": {
    badge: "bg-rose-50 text-rose-700 border-rose-200",
    border: "border-rose-200 bg-rose-50/20",
    icon: "🐻",
  },
  "Moat Agent": {
    badge: "bg-indigo-50 text-indigo-700 border-indigo-200",
    border: "border-indigo-200 bg-indigo-50/20",
    icon: "🏰",
  },
};

export default function InvestmentMemoSection({ idea }: InvestmentMemoSectionProps) {
  const [debateOpen, setDebateOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [expandedToolIdx, setExpandedToolIdx] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const { status, data, error } = useAsync<InvestmentMemo>(
    () => analyzeStartup(idea!.id, refreshKey > 0),
    [idea?.id, refreshKey],
    { enabled: !!idea?.id, errorMessage: "Failed to run investment committee analysis." }
  );


  return (
    <SectionCard
      title="Investment Committee & Memo"
      icon="🏛️"
      description={idea ? `Lead Partner deliberation and committee debate for “${idea.title}”.` : undefined}
      status={status}
      error={error}
      emptyMessage="Submit a startup idea to convene the AI Investment Committee."
      loadingMessage="Convening Bull, Bear, and Moat agents for committee deliberation…"
    >
      {data && (
        <div className="space-y-6">
          {/* Top Banner: Consensus Score & Verdict */}
          <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-gradient-to-r from-slate-50 via-white to-slate-50 p-5 sm:flex-row sm:items-center sm:justify-between shadow-sm">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Lead Partner Decision
                </span>
              </div>
              <div className="mt-1 flex items-center gap-3">
                <span
                  className={`inline-flex items-center rounded-lg border px-3 py-1 text-sm font-bold tracking-wide ${
                    VERDICT_STYLES[data.verdict] ?? "bg-slate-100 text-slate-800 border-slate-300"
                  }`}
                >
                  {data.verdict}
                </span>
                <span className="text-xs text-slate-500">
                  Synthesized across 3 partners + 1 cross-critique round
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-xs font-medium text-slate-500">Consensus Score</div>
                <div className="text-2xl font-black text-slate-900">{data.overall_score.toFixed(1)} <span className="text-xs text-slate-400">/ 10</span></div>
              </div>
              <button
                type="button"
                onClick={() => setRefreshKey((k) => k + 1)}
                title="Re-run committee analysis"
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-xs"
              >
                🔄 Refresh
              </button>

            </div>
          </div>

          {/* Executive Summary */}
          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Executive Summary
            </h4>
            <p className="text-sm leading-relaxed text-slate-700">{data.executive_summary}</p>
          </div>

          {/* 3 Committee Agent Cards Side-by-Side */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
              Multi-Agent Committee Perspectives
            </h4>

            <div className="grid gap-4 md:grid-cols-3">
              {data.agent_verdicts.map((agent) => {
                const styling = AGENT_STYLES[agent.agent_name] ?? {
                  badge: "bg-slate-50 text-slate-700 border-slate-200",
                  border: "border-slate-200 bg-white",
                  icon: "👤",
                };
                return (
                  <div
                    key={agent.agent_name}
                    className={`flex flex-col justify-between rounded-xl border p-4 shadow-xs transition-all ${styling.border}`}
                  >
                    <div>
                      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                        <div className="flex items-center gap-1.5 font-semibold text-sm text-slate-800">
                          <span>{styling.icon}</span>
                          <span>{agent.agent_name}</span>
                        </div>
                        <span className={`rounded-md border px-2 py-0.5 text-xs font-bold ${styling.badge}`}>
                          {agent.score.toFixed(1)} / 10
                        </span>
                      </div>

                      <p className="mt-2.5 text-xs font-medium text-slate-700 leading-relaxed">
                        {agent.summary}
                      </p>

                      <div className="mt-3">
                        <span className="text-[11px] font-semibold uppercase text-slate-400">
                          Key Observations
                        </span>
                        <ul className="mt-1 space-y-1">
                          {agent.key_points.map((pt, idx) => (
                            <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-600">
                              <span className="text-slate-400 shrink-0">•</span>
                              <span>{pt}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    <div className="mt-4 pt-2.5 border-t border-slate-100">
                      <span className="text-[11px] font-semibold uppercase text-slate-400">
                        Recommendation
                      </span>
                      <p className="mt-0.5 text-xs text-slate-600 italic">
                        "{agent.recommendation}"
                      </p>
                      {agent.tool_calls && agent.tool_calls.length > 0 && (
                        <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-slate-500 font-medium">
                          <span>🛠️</span>
                          <span>{agent.tool_calls.length} tool{agent.tool_calls.length > 1 ? "s" : ""} initialized</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

            </div>
          </div>

          {/* Tool Calls & Retrieved Intelligence Accordion */}
          {data.tool_calls && data.tool_calls.length > 0 && (
            <div className="rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <button
                type="button"
                onClick={() => setToolsOpen((prev) => !prev)}
                className="flex w-full items-center justify-between bg-slate-50 px-4 py-3 text-left hover:bg-slate-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-base">🛠️</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Agent Tool Calls & Retrieved Intelligence ({data.tool_calls.length} Invocations)
                  </span>
                </div>
                <span className="text-xs text-slate-500 font-medium">
                  {toolsOpen ? "Hide Tool Calls ▲" : "View Tool Calls ▼"}
                </span>
              </button>

              {toolsOpen && (
                <div className="divide-y divide-slate-100 bg-white p-4 space-y-4">
                  {data.tool_calls.map((toolCall, idx) => {
                    const isExpanded = expandedToolIdx === idx;
                    return (
                      <div key={idx} className="rounded-lg border border-slate-200 bg-slate-50/50 p-3.5 space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                              {toolCall.tool_name}
                            </span>
                            {toolCall.agent_name && (
                              <span className="text-xs font-semibold text-slate-600 bg-white border border-slate-200 px-2 py-0.5 rounded-full">
                                {toolCall.agent_name}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs">
                            {toolCall.latency_ms !== null && toolCall.latency_ms !== undefined && (
                              <span className="text-slate-400 font-mono text-[11px]">
                                {toolCall.latency_ms.toFixed(1)}ms
                              </span>
                            )}
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider border ${
                                toolCall.status === "completed"
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : toolCall.status === "failed"
                                  ? "bg-rose-50 text-rose-700 border-rose-200"
                                  : "bg-amber-50 text-amber-700 border-amber-200"
                              }`}
                            >
                              {toolCall.status}
                            </span>
                          </div>
                        </div>

                        {/* Initialization Parameters */}
                        <div className="text-xs">
                          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-1">
                            Initialization Parameters:
                          </div>
                          <div className="rounded bg-slate-900 p-2 font-mono text-[11px] text-emerald-400 overflow-x-auto">
                            {JSON.stringify(toolCall.input_parameters, null, 2)}
                          </div>
                        </div>

                        {/* Retrieved Information */}
                        {toolCall.retrieved_information && (
                          <div className="text-xs">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                                Information Retrieved:
                              </span>
                              <button
                                type="button"
                                onClick={() => setExpandedToolIdx(isExpanded ? null : idx)}
                                className="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium"
                              >
                                {isExpanded ? "Collapse" : "Expand Full Output"}
                              </button>
                            </div>
                            <div
                              className={`rounded border border-slate-200 bg-white p-2.5 font-sans text-xs text-slate-700 whitespace-pre-wrap ${
                                isExpanded ? "" : "max-h-28 overflow-hidden relative"
                              }`}
                            >
                              {toolCall.retrieved_information}
                              {!isExpanded && (
                                <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white to-transparent pointer-events-none" />
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Debate & Cross-Critique Accordion */}
          {data.debate_transcript && data.debate_transcript.length > 0 && (
            <div className="rounded-xl border border-slate-200 overflow-hidden">
              <button
                type="button"
                onClick={() => setDebateOpen((prev) => !prev)}
                className="flex w-full items-center justify-between bg-slate-50 px-4 py-3 text-left hover:bg-slate-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-base">⚔️</span>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Committee Debate & Cross-Critique Transcript ({data.debate_transcript.length} Round)
                  </span>
                </div>
                <span className="text-xs text-slate-400 font-medium">
                  {debateOpen ? "Hide Debate ▲" : "View Debate ▼"}
                </span>
              </button>

              {debateOpen && (
                <div className="divide-y divide-slate-100 bg-white p-4 space-y-4">
                  {data.debate_transcript.map((round) => (
                    <div key={round.round_number} className="space-y-3">
                      <div className="text-xs font-semibold text-slate-400 uppercase">
                        Round {round.round_number} Exchanges
                      </div>
                      <div className="grid gap-3 sm:grid-cols-3">
                        {round.critiques.map((critique, idx) => (
                          <div key={idx} className="rounded-lg bg-slate-50 p-3 border border-slate-200 text-xs">
                            <div className="font-semibold text-slate-800 mb-1 flex items-center gap-1">
                              <span>💬</span>
                              <span>{critique.agent_name}</span>
                            </div>
                            <p className="text-slate-600 leading-relaxed italic">
                              "{critique.critique_text}"
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Synthesis Details: Strengths, Risks & Next Steps */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/30 p-4">
              <h5 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-emerald-800 mb-2">
                <span>✅</span>
                <span>Core Strengths</span>
              </h5>
              <ul className="space-y-1.5">
                {data.key_strengths.map((s, idx) => (
                  <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-700">
                    <span className="text-emerald-500 font-bold shrink-0">+</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-rose-100 bg-rose-50/30 p-4">
              <h5 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-rose-800 mb-2">
                <span>⚠️</span>
                <span>Key Risks</span>
              </h5>
              <ul className="space-y-1.5">
                {data.key_risks.map((r, idx) => (
                  <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-700">
                    <span className="text-rose-500 font-bold shrink-0">-</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-sky-100 bg-sky-50/30 p-4">
              <h5 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-sky-800 mb-2">
                <span>📋</span>
                <span>Required Milestones</span>
              </h5>
              <ul className="space-y-1.5">
                {data.recommendations.map((rec, idx) => (
                  <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-700">
                    <span className="text-sky-500 font-bold shrink-0">→</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

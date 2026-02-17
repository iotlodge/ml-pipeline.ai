"use client";

import { useState, useEffect } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { PipelineGraph } from "@/components/pipeline/PipelineGraph";
import { PipelineControls } from "@/components/pipeline/PipelineControls";
import { PhaseTimeline } from "@/components/pipeline/PhaseTimeline";
import { ResultsPanel } from "@/components/results/ResultsPanel";
import { TokenCounter } from "@/components/pipeline/TokenCounter";
import { usePipeline } from "@/hooks/usePipeline";
import type { PhaseKey } from "@/lib/types";
import { Activity, AlertCircle } from "lucide-react";

export default function Dashboard() {
  const { run, loading, error, elapsed, launch, reset } = usePipeline();
  const [activePhase, setActivePhase] = useState<PhaseKey | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [objectives, setObjectives] = useState(
    "Predict the target variable using the best classification model. " +
    "Focus on recall and generalization."
  );

  // Auto-select the latest completed phase
  useEffect(() => {
    if (!run?.phases) return;
    const completed = run.phases
      .filter((p) => p.status === "completed")
      .map((p) => p.phase);
    if (completed.length > 0 && !activePhase) {
      setActivePhase(completed[completed.length - 1] as PhaseKey);
    }
  }, [run?.phases, activePhase]);

  const status = run?.status || "idle";
  const hasErrors = run?.errors && run.errors.length > 0;

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar
        status={status as "idle" | "pending" | "running" | "completed" | "completed_with_errors" | "failed"}
        pipelineId={run?.pipeline_id}
      />

      <main className="flex-1 mx-auto max-w-screen-2xl w-full px-4 md:px-6 py-6">
        {/* Error banner */}
        {error && (
          <div className="mb-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30
                          flex items-center gap-3 animate-slide-up">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Pipeline errors collapsible */}
        {hasErrors && (
          <div className="mb-4 animate-slide-up">
            <button
              onClick={() => setShowErrors(!showErrors)}
              className="w-full p-3 rounded-lg bg-amber-500/10 border border-amber-500/30
                         flex items-center gap-3 text-left hover:bg-amber-500/15
                         transition-colors"
            >
              <AlertCircle className="h-4 w-4 text-amber-500 flex-shrink-0" />
              <span className="text-sm font-medium text-amber-600 dark:text-amber-400">
                {run!.errors!.length} pipeline error{run!.errors!.length > 1 ? "s" : ""}
              </span>
            </button>
            {showErrors && (
              <div className="mt-2 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]
                              space-y-2 animate-fade-in">
                {run!.errors!.map((err, i) => (
                  <p key={i} className="text-xs font-mono text-red-500 dark:text-red-400">
                    {err}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Main layout grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* Left column: Controls + Graph (full height for graph) */}
          <div className="lg:col-span-3 space-y-6">
            <PipelineControls
              onLaunch={launch}
              onReset={() => { reset(); setActivePhase(null); }}
              loading={loading}
              elapsed={elapsed}
              hasRun={!!run && !loading}
              objectives={objectives}
              onObjectivesChange={setObjectives}
            />
            <PipelineGraph
              phases={run?.phases || []}
              criticDecisions={run?.critic_decisions}
              pipelineStatus={status}
            />
          </div>

          {/* Center column: Results */}
          <div className="lg:col-span-6">
            {run ? (
              <ResultsPanel
                run={run}
                activePhase={activePhase}
                onPhaseChange={setActivePhase}
              />
            ) : (
              /* Empty state */
              <div className="glass-card p-16 text-center">
                <div className="relative inline-block mb-6">
                  <Activity className="h-16 w-16 text-neural-400/30" />
                  <div className="absolute inset-0 animate-pulse-slow">
                    <Activity className="h-16 w-16 text-neural-400/10" />
                  </div>
                </div>
                <h2 className="text-xl font-bold text-[var(--text-primary)] mb-2">
                  Ready to Observe
                </h2>
                <p className="text-sm text-[var(--text-tertiary)] max-w-md mx-auto">
                  Launch a pipeline to watch the autonomous ML system analyze your data,
                  engineer features, train models, and self-critique in real time.
                </p>
              </div>
            )}
          </div>

          {/* Right column: Phase Timeline + Token Counter + Run Summary */}
          <div className="lg:col-span-3 space-y-6">
            <PhaseTimeline
              phases={run?.phases || []}
              onPhaseClick={(p) => setActivePhase(p as PhaseKey)}
              activePhase={activePhase}
            />

            {/* Token Counter — lives here to give graph more space */}
            <TokenCounter
              usage={run?.token_usage}
              isRunning={loading}
            />

            {/* Run summary — appears on completion */}
            {run && ["completed", "completed_with_errors"].includes(run.status) && (
              <div className="glass-card p-4 animate-slide-up">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
                  Run Summary
                </h4>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Total Time</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">
                      {run.phases
                        ? `${run.phases.reduce((a, p) => a + (p.duration_seconds || 0), 0).toFixed(0)}s`
                        : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Phases</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">
                      {run.phases?.length ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">Critic Iterations</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">
                      {run.critic_decisions?.length ?? 0}
                    </span>
                  </div>
                  {run.model?.best_model_name && (
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Best Model</span>
                      <span className="font-mono font-bold text-emerald-500 dark:text-emerald-400 truncate ml-2">
                        {run.model.best_model_name}
                      </span>
                    </div>
                  )}
                  {run.errors && run.errors.length > 0 && (
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Errors</span>
                      <span className="font-mono font-bold text-red-500">
                        {run.errors.length}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] py-4 mt-8">
        <div className="mx-auto max-w-screen-2xl px-6 flex items-center justify-between">
          <p className="text-[11px] text-[var(--text-tertiary)]">
            Neural Observatory v0.1 &mdash; LangGraph Autonomous ML Pipeline
          </p>
          <p className="text-[11px] text-[var(--text-tertiary)]">
            Powered by LangGraph + FastAPI
          </p>
        </div>
      </footer>
    </div>
  );
}

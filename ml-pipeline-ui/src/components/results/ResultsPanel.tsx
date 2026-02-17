"use client";

import type { PipelineRun, PhaseKey } from "@/lib/types";
import { DataProfilePanel } from "./DataProfilePanel";
import { FeaturePanel } from "./FeaturePanel";
import { VisualizationPanel } from "./VisualizationPanel";
import { ModelPanel } from "./ModelPanel";
import { EvaluationPanel } from "./EvaluationPanel";
import { MarkdownText } from "./MarkdownText";
import { PHASE_META } from "@/lib/types";
import {
  ScanSearch, Wrench, BarChart3, Brain,
  CheckCircle2, MessageSquareWarning, Inbox,
} from "lucide-react";
import { clsx } from "clsx";

const ICONS: Record<string, React.ReactNode> = {
  data_profiling: <ScanSearch className="h-4 w-4" />,
  feature_engineering: <Wrench className="h-4 w-4" />,
  visualization: <BarChart3 className="h-4 w-4" />,
  model_training: <Brain className="h-4 w-4" />,
  evaluation: <CheckCircle2 className="h-4 w-4" />,
  critic_review: <MessageSquareWarning className="h-4 w-4" />,
};

interface ResultsPanelProps {
  run: PipelineRun;
  activePhase: PhaseKey | null;
  onPhaseChange: (phase: PhaseKey) => void;
}

export function ResultsPanel({ run, activePhase, onPhaseChange }: ResultsPanelProps) {
  // Determine which phases have data
  const available: PhaseKey[] = [];
  if (run.data_profile) available.push("data_profiling");
  if (run.feature_engineering) available.push("feature_engineering");
  if (run.visualizations) available.push("visualization");
  if (run.model) available.push("model_training");
  if (run.evaluation) available.push("evaluation");
  if (run.critic_decisions && run.critic_decisions.length > 0) available.push("critic_review");

  const selected = activePhase && available.includes(activePhase) ? activePhase : available[0] || null;

  if (available.length === 0) {
    return (
      <div className="glass-card p-12 text-center">
        <Inbox className="h-12 w-12 mx-auto text-[var(--text-tertiary)] mb-4" />
        <p className="text-sm text-[var(--text-tertiary)]">
          Results will appear here as phases complete
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Phase tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1 custom-scrollbar">
        {available.map((key) => {
          const meta = PHASE_META.find((m) => m.key === key);
          const isActive = selected === key;
          return (
            <button
              key={key}
              onClick={() => onPhaseChange(key)}
              className={clsx(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium",
                "whitespace-nowrap transition-all duration-300",
                isActive
                  ? "bg-neural-500/10 text-neural-500 dark:text-neural-300 border border-neural-500/30"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] border border-transparent",
              )}
            >
              {ICONS[key]}
              {meta?.label || key}
            </button>
          );
        })}
      </div>

      {/* Phase content */}
      <div>
        {selected === "data_profiling" && run.data_profile && (
          <DataProfilePanel profile={run.data_profile} />
        )}
        {selected === "feature_engineering" && run.feature_engineering && (
          <FeaturePanel data={run.feature_engineering} />
        )}
        {selected === "visualization" && run.visualizations && (
          <VisualizationPanel viz={run.visualizations} pipelineId={run.pipeline_id} />
        )}
        {selected === "model_training" && run.model && (
          <ModelPanel model={run.model} />
        )}
        {selected === "evaluation" && run.evaluation && (
          <EvaluationPanel evaluation={run.evaluation} />
        )}
        {selected === "critic_review" && run.critic_decisions && (
          <div className="glass-card p-4 animate-fade-in">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
              Critic Review Log
            </h4>
            <div className="space-y-3">
              {run.critic_decisions.map((cd, i) => {
                const label = cd.decision || cd.assessment || "review";
                const isFinalize = label.toLowerCase().includes("finalize") || label.toLowerCase().includes("accept");
                return (
                  <div
                    key={i}
                    className={clsx(
                      "p-3 rounded-lg border transition-all",
                      isFinalize
                        ? "border-emerald-500/30 bg-emerald-500/5 dark:bg-emerald-500/10"
                        : "border-amber-500/30 bg-amber-500/5 dark:bg-amber-500/10",
                    )}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={clsx(
                        "text-xs font-bold px-2 py-0.5 rounded",
                        isFinalize
                          ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                          : "bg-amber-500/20 text-amber-600 dark:text-amber-400",
                      )}>
                        Iteration {cd.iteration ?? i + 1}
                      </span>
                      <span className="text-sm font-semibold text-[var(--text-primary)]">
                        {label}
                      </span>
                      {cd.confidence != null && (
                        <span className="text-[10px] font-mono text-[var(--text-tertiary)] ml-auto">
                          conf: {(cd.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {cd.reasoning && (
                      <MarkdownText text={cd.reasoning} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

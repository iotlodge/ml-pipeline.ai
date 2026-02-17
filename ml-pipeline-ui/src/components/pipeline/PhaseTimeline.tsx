"use client";

import type { PhaseInfo } from "@/lib/types";
import { PHASE_META } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import {
  ScanSearch, Wrench, BarChart3, Brain,
  CheckCircle2, MessageSquareWarning,
} from "lucide-react";
import { clsx } from "clsx";

const ICONS: Record<string, React.ReactNode> = {
  "data_profiling": <ScanSearch className="h-4 w-4" />,
  "feature_engineering": <Wrench className="h-4 w-4" />,
  "visualization": <BarChart3 className="h-4 w-4" />,
  "model_training": <Brain className="h-4 w-4" />,
  "evaluation": <CheckCircle2 className="h-4 w-4" />,
  "critic_review": <MessageSquareWarning className="h-4 w-4" />,
};

function formatDuration(s?: number): string {
  if (!s) return "—";
  return s >= 60 ? `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s` : `${s.toFixed(1)}s`;
}

interface PhaseTimelineProps {
  phases: PhaseInfo[];
  onPhaseClick?: (phase: string) => void;
  activePhase?: string | null;
}

export function PhaseTimeline({ phases, onPhaseClick, activePhase }: PhaseTimelineProps) {
  // Build a full timeline using PHASE_META order, merging actual phase data
  const timeline = PHASE_META.map((meta) => {
    // Could have multiple entries for critic_review
    const matching = phases.filter((p) => p.phase === meta.key);
    const last = matching.length > 0 ? matching[matching.length - 1] : null;
    return {
      ...meta,
      status: last?.status || "pending",
      duration: last?.duration_seconds,
      error: last?.error,
      count: matching.length,
    };
  });

  return (
    <div className="glass-card p-4">
      <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-4 uppercase tracking-wider">
        Phase Timeline
      </h3>

      <div className="space-y-1">
        {timeline.map((phase, i) => {
          const isActive = activePhase === phase.key;
          return (
            <button
              key={`${phase.key}-${i}`}
              onClick={() => onPhaseClick?.(phase.key)}
              className={clsx(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left",
                "transition-all duration-300 group",
                isActive
                  ? "bg-neural-500/10 border border-neural-500/30 dark:bg-neural-500/15"
                  : "hover:bg-[var(--bg-tertiary)] border border-transparent",
                phase.status === "pending" && !phase.duration && "opacity-40",
              )}
            >
              {/* Icon with status ring */}
              <div className={clsx(
                "relative flex items-center justify-center w-8 h-8 rounded-lg",
                "transition-all duration-500",
                phase.status === "running"
                  ? "bg-neural-500/20 text-neural-400"
                  : phase.status === "completed"
                  ? "bg-emerald-500/10 text-emerald-500 dark:text-emerald-400"
                  : phase.status === "will_rerun"
                  ? "bg-amber-500/10 text-amber-500 dark:text-amber-400"
                  : phase.status === "error"
                  ? "bg-red-500/10 text-red-500"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]",
              )}>
                {ICONS[phase.key]}
                {phase.status === "running" && (
                  <span className="absolute inset-0 rounded-lg border-2 border-neural-400 animate-pulse opacity-50" />
                )}
                {phase.status === "will_rerun" && (
                  <span className="absolute inset-0 rounded-lg border border-amber-400/50 border-dashed animate-pulse opacity-40" />
                )}
              </div>

              {/* Label + description */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                    {phase.label}
                  </span>
                  {phase.count > 1 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded
                                     bg-amber-500/10 text-amber-600 dark:text-amber-400">
                      x{phase.count}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[var(--text-tertiary)] truncate">
                  {phase.status === "running" ? phase.description :
                   phase.error ? phase.error.slice(0, 60) :
                   phase.description}
                </p>
              </div>

              {/* Duration + status */}
              <div className="flex flex-col items-end gap-1">
                <StatusBadge status={phase.status} />
                {phase.duration != null && (
                  <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
                    {formatDuration(phase.duration)}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

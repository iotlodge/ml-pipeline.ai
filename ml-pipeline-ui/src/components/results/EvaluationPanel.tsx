"use client";

import type { Evaluation } from "@/lib/types";
import { MetricsCard } from "./MetricsCard";
import { MarkdownText } from "./MarkdownText";
import { ShieldCheck, AlertTriangle, Lightbulb } from "lucide-react";
import { clsx } from "clsx";

interface EvaluationPanelProps {
  evaluation: Evaluation;
}

export function EvaluationPanel({ evaluation }: EvaluationPanelProps) {
  // Backend may send test_metrics instead of metrics; merge both
  const rawMetrics = { ...(evaluation.test_metrics || {}), ...(evaluation.metrics || {}) };
  // Inject cv_mean / cv_std if present
  if (evaluation.cv_mean != null) rawMetrics["cv_mean"] = evaluation.cv_mean;
  if (evaluation.cv_std != null) rawMetrics["cv_std"] = evaluation.cv_std;
  const metricEntries = Object.entries(rawMetrics);

  const overfitRisk = evaluation.overfitting_risk?.toLowerCase() || "";
  const riskColor = overfitRisk.includes("high") ? "danger"
    : overfitRisk.includes("moderate") ? "warning"
    : "success";

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {metricEntries.slice(0, 4).map(([key, val]) => (
          <MetricsCard
            key={key}
            label={key.replace(/_/g, " ")}
            value={val}
            color={Number(val) > 0.8 ? "success" : Number(val) > 0.6 ? "warning" : "danger"}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Overfitting risk */}
        {evaluation.overfitting_risk && (
          <div className="glass-card p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3 flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5" />
              Overfitting Assessment
            </h4>
            <div className={clsx(
              "inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold",
              riskColor === "danger" && "bg-red-500/10 text-red-600 dark:text-red-400",
              riskColor === "warning" && "bg-amber-500/10 text-amber-600 dark:text-amber-400",
              riskColor === "success" && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
            )}>
              {riskColor === "danger" ? <AlertTriangle className="h-4 w-4" /> :
               riskColor === "warning" ? <AlertTriangle className="h-4 w-4" /> :
               <ShieldCheck className="h-4 w-4" />}
              {evaluation.overfitting_risk}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {evaluation.recommendations && evaluation.recommendations.length > 0 && (
          <div className="glass-card p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3 flex items-center gap-2">
              <Lightbulb className="h-3.5 w-3.5" />
              Recommendations
            </h4>
            <ul className="space-y-2">
              {evaluation.recommendations.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Summary */}
      {evaluation.summary && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2">
            Evaluation Summary
          </h4>
          <MarkdownText text={evaluation.summary} />
        </div>
      )}

      {/* Additional metrics */}
      {metricEntries.length > 4 && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
            All Metrics
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {metricEntries.map(([key, val]) => (
              <div key={key} className="px-3 py-2 rounded-md bg-[var(--bg-tertiary)]">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] block">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-sm font-bold font-mono text-[var(--text-primary)]">
                  {typeof val === "number" ? (val < 1 ? `${(val * 100).toFixed(1)}%` : val.toFixed(3)) : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

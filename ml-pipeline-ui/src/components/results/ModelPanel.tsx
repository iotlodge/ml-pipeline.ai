"use client";

import type { ModelResult, ModelCandidate } from "@/lib/types";
import { MetricsCard } from "./MetricsCard";
import { Trophy, Target, BarChart2 } from "lucide-react";
import { clsx } from "clsx";

interface ModelPanelProps {
  model: ModelResult;
}

function getCandidateName(c: ModelCandidate): string {
  return c.name || c.model_name || c.algorithm || "Unknown";
}

export function ModelPanel({ model }: ModelPanelProps) {
  const candidates = model.candidates || [];
  const bestName = model.best_model_name || "";
  const featureImp = model.feature_importance
    ? Object.entries(model.feature_importance)
        .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
        .slice(0, 12)
    : [];

  const maxImp = featureImp.length > 0 ? Math.max(...featureImp.map(([, v]) => Math.abs(v))) : 1;

  // Find best candidate metrics
  const best = candidates.find((c) => getCandidateName(c) === bestName) || candidates[0];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Best model metrics */}
      {best && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          <MetricsCard
            label="Best Model"
            value={bestName || getCandidateName(best)}
            icon={<Trophy className="h-3.5 w-3.5" />}
            color="success"
          />
          <MetricsCard
            label="Accuracy"
            value={best.accuracy ?? 0}
            color={Number(best.accuracy) > 0.8 ? "success" : "warning"}
          />
          <MetricsCard
            label="Recall"
            value={best.recall ?? 0}
            color={Number(best.recall) > 0.7 ? "success" : Number(best.recall) > 0.5 ? "warning" : "danger"}
            icon={<Target className="h-3.5 w-3.5" />}
          />
          <MetricsCard
            label="F1 Score"
            value={best.f1 ?? 0}
            color={Number(best.f1) > 0.7 ? "success" : "warning"}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Candidate comparison */}
        {candidates.length > 0 && (
          <div className="glass-card p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3 flex items-center gap-2">
              <BarChart2 className="h-3.5 w-3.5" />
              Model Candidates ({candidates.length})
            </h4>
            <div className="overflow-x-auto custom-scrollbar">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="text-left py-2 pr-3 font-semibold text-[var(--text-tertiary)]">Model</th>
                    <th className="text-right py-2 px-2 font-semibold text-[var(--text-tertiary)]">Acc</th>
                    <th className="text-right py-2 px-2 font-semibold text-[var(--text-tertiary)]">Prec</th>
                    <th className="text-right py-2 px-2 font-semibold text-[var(--text-tertiary)]">Recall</th>
                    <th className="text-right py-2 pl-2 font-semibold text-[var(--text-tertiary)]">F1</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c, i) => {
                    const name = getCandidateName(c);
                    const isBest = name === bestName;
                    return (
                      <tr
                        key={i}
                        className={clsx(
                          "border-b border-[var(--border)] last:border-0 transition-colors",
                          isBest && "bg-emerald-500/5 dark:bg-emerald-500/10",
                        )}
                      >
                        <td className="py-2 pr-3">
                          <div className="flex items-center gap-1.5">
                            {isBest && <Trophy className="h-3 w-3 text-amber-500" />}
                            <span className={clsx(
                              "font-mono",
                              isBest ? "font-bold text-[var(--text-primary)]" : "text-[var(--text-secondary)]",
                            )}>
                              {name}
                            </span>
                          </div>
                        </td>
                        <td className="text-right py-2 px-2 font-mono text-[var(--text-secondary)]">
                          {c.accuracy != null ? `${(Number(c.accuracy) * 100).toFixed(1)}%` : "—"}
                        </td>
                        <td className="text-right py-2 px-2 font-mono text-[var(--text-secondary)]">
                          {c.precision != null ? `${(Number(c.precision) * 100).toFixed(1)}%` : "—"}
                        </td>
                        <td className="text-right py-2 px-2 font-mono text-[var(--text-secondary)]">
                          {c.recall != null ? `${(Number(c.recall) * 100).toFixed(1)}%` : "—"}
                        </td>
                        <td className="text-right py-2 pl-2 font-mono text-[var(--text-secondary)]">
                          {c.f1 != null ? `${(Number(c.f1) * 100).toFixed(1)}%` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Feature importance */}
        {featureImp.length > 0 && (
          <div className="glass-card p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
              Feature Importance (Top {featureImp.length})
            </h4>
            <div className="space-y-2">
              {featureImp.map(([name, imp]) => {
                const pct = (Math.abs(imp) / maxImp) * 100;
                const isNeg = imp < 0;
                return (
                  <div key={name}>
                    <div className="flex justify-between text-[11px] mb-0.5">
                      <span className="font-mono text-[var(--text-primary)] truncate max-w-[60%]">
                        {name}
                      </span>
                      <span className={clsx(
                        "font-mono",
                        isNeg ? "text-red-500" : "text-emerald-500 dark:text-emerald-400",
                      )}>
                        {isNeg ? "" : "+"}{imp.toFixed(4)}
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
                      <div
                        className={clsx(
                          "h-full rounded-full transition-all duration-700 ease-out",
                          isNeg
                            ? "bg-gradient-to-r from-red-400 to-red-500"
                            : "bg-gradient-to-r from-neural-400 to-cyber-500",
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
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

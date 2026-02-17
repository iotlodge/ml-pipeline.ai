"use client";

import type { DataProfile } from "@/lib/types";
import { MetricsCard } from "./MetricsCard";
import { MarkdownText } from "./MarkdownText";
import { Database, Columns3, AlertTriangle } from "lucide-react";

interface DataProfilePanelProps {
  profile: DataProfile;
}

export function DataProfilePanel({ profile }: DataProfilePanelProps) {
  const missingEntries = profile.missing_pct
    ? Object.entries(profile.missing_pct).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])
    : [];

  const targetDist = profile.target_distribution
    ? Object.entries(profile.target_distribution)
    : [];

  const totalRows = profile.shape?.[0] ?? 0;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Top metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricsCard
          label="Rows"
          value={totalRows.toLocaleString()}
          icon={<Database className="h-3.5 w-3.5" />}
          color="default"
        />
        <MetricsCard
          label="Features"
          value={String(profile.shape?.[1] ?? 0)}
          icon={<Columns3 className="h-3.5 w-3.5" />}
          color="default"
        />
        <MetricsCard
          label="Target"
          value={profile.target_column || "—"}
          color="success"
        />
        <MetricsCard
          label="Missing Cols"
          value={String(missingEntries.length)}
          icon={<AlertTriangle className="h-3.5 w-3.5" />}
          color={missingEntries.length > 3 ? "warning" : "default"}
        />
      </div>

      {/* Key findings */}
      {profile.key_findings && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2">
            Key Findings
          </h4>
          <MarkdownText text={profile.key_findings} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Target distribution */}
        {targetDist.length > 0 && (
          <div className="glass-card p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
              Target Distribution
            </h4>
            <div className="space-y-2">
              {targetDist.map(([label, count]) => {
                const pct = totalRows > 0 ? (Number(count) / totalRows) * 100 : 0;
                return (
                  <div key={label}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-medium text-[var(--text-primary)]">{label}</span>
                      <span className="font-mono text-[var(--text-secondary)]">
                        {Number(count).toLocaleString()} ({pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-neural-500 to-cyber-500
                                   transition-all duration-700 ease-out"
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Missing values */}
        {missingEntries.length > 0 && (
          <div className="glass-card p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
              Missing Values
            </h4>
            <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
              {missingEntries.slice(0, 10).map(([col, pct]) => (
                <div key={col}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-mono text-[var(--text-primary)] truncate max-w-[60%]">
                      {col}
                    </span>
                    <span className={`font-mono ${pct > 20 ? "text-red-500" : "text-amber-500"}`}>
                      {pct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500
                        ${pct > 20 ? "bg-red-500" : "bg-amber-500"}`}
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Columns list */}
      {profile.columns && profile.columns.length > 0 && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
            Features ({profile.columns.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {profile.columns.map((col) => (
              <span
                key={col}
                className="px-2 py-1 text-[11px] font-mono rounded-md
                           bg-[var(--bg-tertiary)] text-[var(--text-secondary)]
                           border border-[var(--border)]"
              >
                {col}
                {profile.dtypes?.[col] && (
                  <span className="ml-1 text-[var(--text-tertiary)]">
                    ({profile.dtypes[col]})
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import type { FeatureEngineering } from "@/lib/types";
import { MetricsCard } from "./MetricsCard";
import { Layers, Plus, ArrowRight } from "lucide-react";

interface FeaturePanelProps {
  data: FeatureEngineering;
}

export function FeaturePanel({ data }: FeaturePanelProps) {
  const shape = data.final_shape || data.new_shape;
  return (
    <div className="space-y-4 animate-fade-in">
      {/* Metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <MetricsCard
          label="New Features"
          value={String(data.new_columns?.length ?? 0)}
          icon={<Plus className="h-3.5 w-3.5" />}
          color="success"
        />
        <MetricsCard
          label="Final Shape"
          value={shape ? `${shape[0]} x ${shape[1]}` : "—"}
          icon={<Layers className="h-3.5 w-3.5" />}
          color="default"
        />
        <MetricsCard
          label="Transforms"
          value={String(data.transformations?.length ?? 0)}
          icon={<ArrowRight className="h-3.5 w-3.5" />}
          color="default"
        />
      </div>

      {/* New columns */}
      {data.new_columns && data.new_columns.length > 0 && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
            Generated Features ({data.new_columns.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {data.new_columns.map((col) => (
              <span
                key={col}
                className="px-2 py-1 text-[11px] font-mono rounded-md
                           bg-cyber-500/10 text-cyber-600 dark:text-cyber-400
                           border border-cyber-500/20"
              >
                + {col}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Transformations */}
      {data.transformations && data.transformations.length > 0 && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
            Applied Transformations
          </h4>
          <ul className="space-y-2">
            {data.transformations.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-cyber-500 flex-shrink-0" />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

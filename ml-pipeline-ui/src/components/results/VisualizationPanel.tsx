"use client";

import { useEffect, useState } from "react";
import type { Visualization } from "@/lib/types";
import type { PlotInfo } from "@/lib/api";
import { getPipelinePlots, getPlotImageUrl } from "@/lib/api";
import { BarChart3, ZoomIn, X, Image as ImageIcon, Loader2 } from "lucide-react";
import { clsx } from "clsx";
import { MarkdownText } from "./MarkdownText";

interface VisualizationPanelProps {
  viz: Visualization;
  pipelineId: string;
}

export function VisualizationPanel({ viz, pipelineId }: VisualizationPanelProps) {
  const [plots, setPlots] = useState<PlotInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchPlots() {
      try {
        const result = await getPipelinePlots(pipelineId);
        if (!cancelled) setPlots(result);
      } catch {
        // Plots not available yet
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchPlots();
    // Retry once after 3s if no plots (might still be generating)
    const timer = setTimeout(() => {
      if (!cancelled) fetchPlots();
    }, 3000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [pipelineId]);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Insights — rendered as markdown */}
      {(viz.interpretation || viz.key_insights) && (
        <div className="glass-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2 flex items-center gap-2">
            <BarChart3 className="h-3.5 w-3.5" />
            EDA Insights
          </h4>
          <MarkdownText text={viz.interpretation || viz.key_insights || ""} />
        </div>
      )}

      {/* Plot grid */}
      {loading ? (
        <div className="glass-card p-8 text-center">
          <Loader2 className="h-6 w-6 mx-auto text-[var(--text-tertiary)] animate-spin mb-2" />
          <p className="text-sm text-[var(--text-tertiary)]">Loading visualizations...</p>
        </div>
      ) : plots.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {plots.map((plot) => (
            <div
              key={plot.filename}
              className="glass-card p-3 group cursor-pointer transition-all duration-300 hover:border-neural-500/30"
              onClick={() => setExpanded(plot.filename)}
            >
              <div className="flex items-center justify-between mb-2">
                <h5 className="text-xs font-semibold text-[var(--text-secondary)]">{plot.title}</h5>
                <ZoomIn className="h-3.5 w-3.5 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="relative rounded-lg overflow-hidden bg-[var(--bg-primary)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getPlotImageUrl(pipelineId, plot.filename)}
                  alt={plot.title}
                  className="w-full h-auto rounded-lg"
                  loading="lazy"
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass-card p-6 text-center">
          <ImageIcon className="h-8 w-8 mx-auto text-[var(--text-tertiary)] mb-2" />
          <p className="text-sm text-[var(--text-tertiary)]">
            {viz.plot_count ? `${viz.plot_count} plots generated (images loading...)` : "No visualizations available"}
          </p>
        </div>
      )}

      {/* Lightbox */}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setExpanded(null)}
        >
          <div className="relative max-w-5xl max-h-[90vh] w-full">
            <button
              className="absolute -top-10 right-0 text-white/80 hover:text-white transition-colors"
              onClick={() => setExpanded(null)}
            >
              <X className="h-6 w-6" />
            </button>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getPlotImageUrl(pipelineId, expanded)}
              alt="Plot"
              className="w-full h-auto rounded-xl shadow-2xl"
            />
          </div>
        </div>
      )}
    </div>
  );
}

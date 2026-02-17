"use client";

import { useEffect, useRef, useMemo } from "react";
import type { PhaseInfo, CriticDecision } from "@/lib/types";
import {
  ScanSearch, Wrench, BarChart3, Brain,
  CheckCircle2, MessageSquareWarning, Rocket, Flag,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Pipeline graph — custom SVG with animated nodes                    */
/* ------------------------------------------------------------------ */

interface GraphNode {
  id: string;
  label: string;
  phaseKey?: string;
  icon: React.ReactNode;
  x: number;
  y: number;
  type: "start" | "end" | "phase" | "decision";
}

interface GraphEdge {
  from: string;
  to: string;
  label?: string;
  type?: "normal" | "loop";
}

const ICON_SIZE = 16;

const NODES: GraphNode[] = [
  { id: "start", label: "START", icon: <Rocket size={ICON_SIZE} />, x: 300, y: 30, type: "start" },
  { id: "dp", label: "Data Profiler", phaseKey: "data_profiling", icon: <ScanSearch size={ICON_SIZE} />, x: 300, y: 110, type: "phase" },
  { id: "fe", label: "Feature Engineer", phaseKey: "feature_engineering", icon: <Wrench size={ICON_SIZE} />, x: 300, y: 190, type: "phase" },
  { id: "viz", label: "Visualizer", phaseKey: "visualization", icon: <BarChart3 size={ICON_SIZE} />, x: 300, y: 270, type: "phase" },
  { id: "mt", label: "Model Trainer", phaseKey: "model_training", icon: <Brain size={ICON_SIZE} />, x: 300, y: 350, type: "phase" },
  { id: "eval", label: "Evaluator", phaseKey: "evaluation", icon: <CheckCircle2 size={ICON_SIZE} />, x: 300, y: 430, type: "phase" },
  { id: "critic", label: "Critic", phaseKey: "critic_review", icon: <MessageSquareWarning size={ICON_SIZE} />, x: 300, y: 510, type: "decision" },
  { id: "end", label: "END", icon: <Flag size={ICON_SIZE} />, x: 300, y: 600, type: "end" },
];

const EDGES: GraphEdge[] = [
  { from: "start", to: "dp" },
  { from: "dp", to: "fe" },
  { from: "fe", to: "viz" },
  { from: "viz", to: "mt" },
  { from: "mt", to: "eval" },
  { from: "eval", to: "critic" },
  { from: "critic", to: "end", label: "finalize" },
  { from: "critic", to: "fe", label: "refine", type: "loop" },
  { from: "critic", to: "mt", label: "retrain", type: "loop" },
];

function getPhaseStatus(
  phaseKey: string | undefined,
  phases: PhaseInfo[],
  pipelineStatus: string,
): "pending" | "running" | "completed" | "error" | "will_rerun" {
  if (!phaseKey) return "pending";
  const matching = phases.filter((p) => p.phase === phaseKey);
  if (matching.length === 0) return "pending";
  const last = matching[matching.length - 1];
  return last.status;
}

interface PipelineGraphProps {
  phases: PhaseInfo[];
  criticDecisions?: CriticDecision[];
  pipelineStatus: string;
}

export function PipelineGraph({ phases, criticDecisions, pipelineStatus }: PipelineGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  const nodeStates = useMemo(() => {
    const map: Record<string, string> = {};
    NODES.forEach((n) => {
      if (n.type === "start") {
        map[n.id] = pipelineStatus !== "pending" ? "completed" : "running";
      } else if (n.type === "end") {
        map[n.id] = ["completed", "completed_with_errors"].includes(pipelineStatus) ? "completed" : "pending";
      } else {
        map[n.id] = getPhaseStatus(n.phaseKey, phases, pipelineStatus);
      }
    });
    return map;
  }, [phases, pipelineStatus]);

  const nodeColors = (state: string) => {
    switch (state) {
      case "running":
        return {
          fill: "var(--node-running, #7c3aed)",
          stroke: "#a78bfa",
          text: "#ffffff",
          glow: "rgba(124, 58, 237, 0.5)",
        };
      case "completed":
        return {
          fill: "var(--node-completed, #059669)",
          stroke: "#34d399",
          text: "#ffffff",
          glow: "rgba(5, 150, 105, 0.3)",
        };
      case "will_rerun":
        return {
          fill: "var(--node-will-rerun, #d97706)",
          stroke: "#fbbf24",
          text: "#ffffff",
          glow: "rgba(217, 119, 6, 0.3)",
        };
      case "error":
        return {
          fill: "var(--node-error, #dc2626)",
          stroke: "#f87171",
          text: "#ffffff",
          glow: "rgba(220, 38, 38, 0.4)",
        };
      default:
        return {
          fill: "var(--node-pending-fill, #1e293b)",
          stroke: "var(--node-pending-stroke, #334155)",
          text: "var(--node-pending-text, #64748b)",
          glow: "none",
        };
    }
  };

  return (
    <div className="glass-card p-4 overflow-hidden">
      <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">
        Pipeline Topology
      </h3>
      <svg
        ref={svgRef}
        viewBox="0 0 600 640"
        className="w-full h-auto"
        style={{ maxHeight: "600px" }}
      >
        {/* CSS variables for light/dark mode */}
        <style>{`
          :root {
            --node-pending-fill: #e2e8f0;
            --node-pending-stroke: #cbd5e1;
            --node-pending-text: #64748b;
            --edge-color: #94a3b8;
            --node-running: #7c3aed;
            --node-completed: #059669;
            --node-error: #dc2626;
          }
          .dark {
            --node-pending-fill: #1e293b;
            --node-pending-stroke: #334155;
            --node-pending-text: #64748b;
            --edge-color: #475569;
          }
        `}</style>

        <defs>
          <marker id="arrow" viewBox="0 0 10 7" refX="10" refY="3.5"
                  markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 3.5 L 0 7 z" fill="var(--edge-color)" />
          </marker>
          <marker id="arrow-loop" viewBox="0 0 10 7" refX="10" refY="3.5"
                  markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 3.5 L 0 7 z" fill="#f59e0b" />
          </marker>
          {/* Glow filter */}
          <filter id="glow-running">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-completed">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Edges */}
        {EDGES.map((e) => {
          const from = NODES.find((n) => n.id === e.from)!;
          const to = NODES.find((n) => n.id === e.to)!;
          const isLoop = e.type === "loop";

          if (isLoop) {
            // Curved path for loop-back edges
            const side = to.id === "fe" ? -1 : 1;
            const cpX = from.x + side * 160;
            const midY = (from.y + to.y) / 2;
            return (
              <g key={`${e.from}-${e.to}`}>
                <path
                  d={`M ${from.x + side * 70} ${from.y}
                      C ${cpX} ${from.y}, ${cpX} ${to.y}, ${to.x + side * 70} ${to.y}`}
                  fill="none"
                  stroke="#f59e0b"
                  strokeWidth="1.5"
                  strokeDasharray="6 4"
                  opacity="0.6"
                  markerEnd="url(#arrow-loop)"
                />
                {e.label && (
                  <text x={cpX + side * 5} y={midY} textAnchor="middle"
                        className="text-[10px] fill-amber-500 font-medium">
                    {e.label}
                  </text>
                )}
              </g>
            );
          }

          return (
            <g key={`${e.from}-${e.to}`}>
              <line
                x1={from.x} y1={from.y + 25}
                x2={to.x} y2={to.y - 25}
                stroke="var(--edge-color)"
                strokeWidth="1.5"
                markerEnd="url(#arrow)"
                opacity="0.5"
              />
              {e.label && (
                <text
                  x={(from.x + to.x) / 2 + 15}
                  y={(from.y + to.y) / 2 + 5}
                  className="text-[10px] fill-emerald-500 dark:fill-emerald-400 font-medium"
                >
                  {e.label}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {NODES.map((node) => {
          const state = nodeStates[node.id] || "pending";
          const colors = nodeColors(state);
          const isDecision = node.type === "decision";
          const isTerminal = node.type === "start" || node.type === "end";
          const w = isTerminal ? 100 : 140;
          const h = isTerminal ? 36 : 44;

          return (
            <g
              key={node.id}
              filter={state === "running" ? "url(#glow-running)" :
                      state === "completed" || state === "will_rerun" ? "url(#glow-completed)" : undefined}
              className="transition-all duration-700"
            >
              {/* Running pulse ring */}
              {state === "running" && (
                <rect
                  x={node.x - w / 2 - 4} y={node.y - h / 2 - 4}
                  width={w + 8} height={h + 8}
                  rx={isDecision ? 6 : isTerminal ? 20 : 10}
                  fill="none" stroke={colors.stroke}
                  strokeWidth="2" opacity="0.4"
                >
                  <animate attributeName="opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
                </rect>
              )}
              {/* Will-rerun gentle pulse */}
              {state === "will_rerun" && (
                <rect
                  x={node.x - w / 2 - 3} y={node.y - h / 2 - 3}
                  width={w + 6} height={h + 6}
                  rx={isDecision ? 5 : isTerminal ? 19 : 9}
                  fill="none" stroke={colors.stroke}
                  strokeWidth="1.5" opacity="0.3"
                  strokeDasharray="6 4"
                >
                  <animate attributeName="opacity" values="0.3;0.1;0.3" dur="3s" repeatCount="indefinite" />
                </rect>
              )}

              {/* Main node rect */}
              <rect
                x={node.x - w / 2} y={node.y - h / 2}
                width={w} height={h}
                rx={isDecision ? 4 : isTerminal ? 18 : 8}
                fill={colors.fill}
                stroke={colors.stroke}
                strokeWidth={state === "running" ? 2.5 : 1.5}
                className="transition-all duration-500"
              />

              {/* Decision diamond overlay */}
              {isDecision && (
                <rect
                  x={node.x - w / 2} y={node.y - h / 2}
                  width={w} height={h}
                  rx={4}
                  fill="none"
                  stroke={colors.stroke}
                  strokeWidth={state === "running" ? 2.5 : 1.5}
                  strokeDasharray={state === "pending" ? "4 2" : "none"}
                />
              )}

              {/* Label */}
              <text
                x={node.x} y={node.y + 1}
                textAnchor="middle" dominantBaseline="middle"
                fill={colors.text}
                className="text-[11px] font-semibold"
                style={{ userSelect: "none" }}
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Critic decisions legend */}
      {criticDecisions && criticDecisions.length > 0 && (
        <div className="mt-3 border-t border-[var(--border)] pt-3 space-y-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
            Critic Iterations
          </p>
          {criticDecisions.map((cd, i) => {
            const label = cd.decision || cd.assessment || "review";
            const isFinalize = label.toLowerCase().includes("finalize") || label.toLowerCase().includes("accept");
            return (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className={`inline-block w-2 h-2 rounded-full
                ${isFinalize ? "bg-emerald-500" : "bg-amber-500"}`}
              />
              <span className="font-mono text-[var(--text-secondary)]">
                #{cd.iteration ?? i + 1}
              </span>
              <span className="font-medium text-[var(--text-primary)]">
                {label}
              </span>
              {cd.reasoning && (
                <span className="text-[var(--text-tertiary)] truncate max-w-[200px]">
                  — {cd.reasoning}
                </span>
              )}
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

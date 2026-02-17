"use client";

import { Brain, Activity } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { GraphModalTrigger } from "./GraphModal";
import type { PipelineStatus } from "@/lib/types";

const STATUS_COLORS: Record<PipelineStatus | "idle", string> = {
  idle: "bg-gray-400",
  pending: "bg-amber-400",
  running: "bg-emerald-400 animate-pulse",
  completed: "bg-emerald-500",
  completed_with_errors: "bg-amber-500",
  failed: "bg-red-500",
};

interface NavbarProps {
  status?: PipelineStatus | "idle";
  pipelineId?: string;
}

export function Navbar({ status = "idle", pipelineId }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--bg-secondary)]/80 backdrop-blur-xl">
      <div className="mx-auto max-w-screen-2xl flex items-center justify-between px-6 h-16">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Brain className="h-7 w-7 text-neural-400" />
            <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[var(--bg-secondary)]">
              <div className={`w-full h-full rounded-full ${STATUS_COLORS[status]}`} />
            </div>
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">
              <span className="text-gradient">Neural Observatory</span>
            </h1>
            <p className="text-[10px] font-medium uppercase tracking-widest text-[var(--text-tertiary)]">
              Autonomous ML Pipeline
            </p>
          </div>
        </div>

        {/* Center — status */}
        <div className="hidden md:flex items-center gap-3">
          {pipelineId && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full
                            bg-[var(--bg-tertiary)] border border-[var(--border)]">
              <Activity className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />
              <span className="text-xs font-mono text-[var(--text-secondary)]">
                {pipelineId.slice(0, 8)}
              </span>
              <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full
                ${status === "running" ? "bg-emerald-500/10 text-emerald-500" :
                  status === "completed" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" :
                  status === "failed" ? "bg-red-500/10 text-red-500" :
                  status === "completed_with_errors" ? "bg-amber-500/10 text-amber-600 dark:text-amber-400" :
                  "bg-gray-500/10 text-gray-500"}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[status]}`} />
                {status}
              </span>
            </div>
          )}
        </div>

        {/* Right */}
        <div className="flex items-center gap-1">
          <GraphModalTrigger />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

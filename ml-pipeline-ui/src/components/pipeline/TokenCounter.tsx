"use client";

import { useEffect, useRef, useState } from "react";
import type { TokenUsage } from "@/lib/types";
import { Cpu, ArrowDownToLine, ArrowUpFromLine, Zap, Hash } from "lucide-react";
import { clsx } from "clsx";

interface TokenCounterProps {
  usage: TokenUsage | undefined;
  isRunning: boolean;
}

/** Animate a number counting up smoothly */
function useAnimatedValue(target: number, duration = 600): number {
  const [display, setDisplay] = useState(0);
  const prevRef = useRef(0);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const start = prevRef.current;
    const diff = target - start;
    if (diff === 0) return;

    const startTime = performance.now();
    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + diff * eased);
      setDisplay(current);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        prevRef.current = target;
      }
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return display;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function TokenCounter({ usage, isRunning }: TokenCounterProps) {
  const input = useAnimatedValue(usage?.input_tokens ?? 0);
  const output = useAnimatedValue(usage?.output_tokens ?? 0);
  const total = useAnimatedValue(usage?.total_tokens ?? 0);
  const calls = usage?.llm_calls ?? 0;

  const hasData = total > 0;

  return (
    <div className={clsx(
      "glass-card p-4 relative overflow-hidden transition-all duration-500",
      isRunning && hasData && "glow-active",
    )}>
      {/* Animated background pulse when running */}
      {isRunning && hasData && (
        <div className="absolute inset-0 bg-gradient-to-r from-neural-500/5 via-cyber-500/5 to-neural-500/5
                        animate-progress opacity-50 pointer-events-none" />
      )}

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={clsx(
              "flex items-center justify-center w-6 h-6 rounded-md",
              isRunning && hasData
                ? "bg-neural-500/20 text-neural-400"
                : "bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]",
            )}>
              <Cpu className="h-3.5 w-3.5" />
            </div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              LLM Tokens
            </h3>
          </div>
          {isRunning && hasData && (
            <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-neural-400">
              <span className="w-1.5 h-1.5 rounded-full bg-neural-400 animate-pulse" />
              Live
            </span>
          )}
        </div>

        {/* Total — big hero number */}
        <div className="mb-3">
          <div className={clsx(
            "text-3xl font-bold font-mono tracking-tight transition-colors duration-300",
            hasData ? "text-gradient" : "text-[var(--text-tertiary)]",
          )}>
            {formatNumber(total)}
          </div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] mt-0.5">
            Total Tokens
          </p>
        </div>

        {/* Breakdown grid */}
        <div className="grid grid-cols-3 gap-2">
          {/* Input tokens */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-2">
            <div className="flex items-center gap-1 mb-1">
              <ArrowDownToLine className="h-3 w-3 text-cyber-500" />
              <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
                In
              </span>
            </div>
            <span className="text-sm font-bold font-mono text-cyber-500 dark:text-cyber-400">
              {formatNumber(input)}
            </span>
          </div>

          {/* Output tokens */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-2">
            <div className="flex items-center gap-1 mb-1">
              <ArrowUpFromLine className="h-3 w-3 text-neural-400" />
              <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
                Out
              </span>
            </div>
            <span className="text-sm font-bold font-mono text-neural-400 dark:text-neural-300">
              {formatNumber(output)}
            </span>
          </div>

          {/* Call count */}
          <div className="rounded-lg bg-[var(--bg-tertiary)] p-2">
            <div className="flex items-center gap-1 mb-1">
              <Hash className="h-3 w-3 text-amber-500" />
              <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">
                Calls
              </span>
            </div>
            <span className="text-sm font-bold font-mono text-amber-500 dark:text-amber-400">
              {calls}
            </span>
          </div>
        </div>

        {/* Token ratio bar */}
        {hasData && (
          <div className="mt-3">
            <div className="flex justify-between text-[9px] font-mono text-[var(--text-tertiary)] mb-1">
              <span>Input {((usage!.input_tokens / usage!.total_tokens) * 100).toFixed(0)}%</span>
              <span>Output {((usage!.output_tokens / usage!.total_tokens) * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden flex">
              <div
                className="h-full bg-gradient-to-r from-cyber-500 to-cyber-400 transition-all duration-700"
                style={{ width: `${(usage!.input_tokens / usage!.total_tokens) * 100}%` }}
              />
              <div
                className="h-full bg-gradient-to-r from-neural-400 to-neural-500 transition-all duration-700"
                style={{ width: `${(usage!.output_tokens / usage!.total_tokens) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

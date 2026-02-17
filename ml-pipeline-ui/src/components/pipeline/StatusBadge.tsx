"use client";

import { clsx } from "clsx";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const STYLES: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  running: "bg-neural-500/10 text-neural-500 dark:bg-neural-500/20 dark:text-neural-300",
  completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  will_rerun: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  completed_with_errors: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  failed: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full font-semibold",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        STYLES[status] || STYLES.pending,
      )}
    >
      {(status === "running" || status === "will_rerun") && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {status === "will_rerun" ? "re-run" : status}
    </span>
  );
}

"use client";

import { clsx } from "clsx";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricsCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  color?: "default" | "success" | "warning" | "danger";
  icon?: React.ReactNode;
}

const COLOR_MAP = {
  default: "from-neural-500/10 to-neural-600/10 dark:from-neural-500/20 dark:to-neural-600/20",
  success: "from-emerald-500/10 to-emerald-600/10 dark:from-emerald-500/20 dark:to-emerald-600/20",
  warning: "from-amber-500/10 to-amber-600/10 dark:from-amber-500/20 dark:to-amber-600/20",
  danger: "from-red-500/10 to-red-600/10 dark:from-red-500/20 dark:to-red-600/20",
};

const VALUE_COLOR = {
  default: "text-neural-500 dark:text-neural-300",
  success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  danger: "text-red-600 dark:text-red-400",
};

export function MetricsCard({
  label, value, subtitle, trend, color = "default", icon,
}: MetricsCardProps) {
  const fmtValue = typeof value === "number"
    ? value < 1 ? `${(value * 100).toFixed(1)}%` : value.toFixed(2)
    : value;

  return (
    <div className={clsx(
      "rounded-lg px-3 py-3 bg-gradient-to-br border border-[var(--border)]",
      "transition-all duration-300 hover:border-[var(--border-hover)]",
      "min-w-0",
      COLOR_MAP[color],
    )}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
          {label}
        </span>
        {icon && <span className="text-[var(--text-tertiary)]">{icon}</span>}
      </div>
      <div className="flex items-end gap-2 min-w-0">
        <span
          className={clsx(
            "font-bold font-mono leading-tight truncate",
            typeof value === "string" && value.length > 10 ? "text-sm" :
            typeof value === "string" && value.length > 6 ? "text-base" : "text-2xl",
            VALUE_COLOR[color],
          )}
          title={typeof value === "string" ? value : undefined}
        >
          {fmtValue}
        </span>
        {trend && (
          <span className="mb-1">
            {trend === "up" ? <TrendingUp className="h-4 w-4 text-emerald-500" /> :
             trend === "down" ? <TrendingDown className="h-4 w-4 text-red-500" /> :
             <Minus className="h-4 w-4 text-gray-400" />}
          </span>
        )}
      </div>
      {subtitle && (
        <p className="text-[11px] text-[var(--text-tertiary)] mt-1">{subtitle}</p>
      )}
    </div>
  );
}

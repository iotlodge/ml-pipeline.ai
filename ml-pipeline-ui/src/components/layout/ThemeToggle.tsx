"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-9 h-9" />;

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="relative w-9 h-9 rounded-lg border border-[var(--border)]
                 bg-[var(--bg-tertiary)] hover:border-neural-400
                 flex items-center justify-center transition-all duration-300
                 hover:shadow-[0_0_12px_rgba(124,58,237,0.2)]"
      aria-label="Toggle theme"
    >
      <Sun
        className={`h-4 w-4 transition-all duration-300 absolute
                    ${isDark ? "rotate-90 scale-0 opacity-0" : "rotate-0 scale-100 opacity-100"}
                    text-amber-500`}
      />
      <Moon
        className={`h-4 w-4 transition-all duration-300 absolute
                    ${isDark ? "rotate-0 scale-100 opacity-100" : "-rotate-90 scale-0 opacity-0"}
                    text-neural-300`}
      />
    </button>
  );
}

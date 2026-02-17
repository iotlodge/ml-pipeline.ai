"use client";

import { useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { Network, X, ExternalLink } from "lucide-react";

const GRAPH_URL = "/api/v1/graph/html";

function GraphModal({ onClose }: { onClose: () => void }) {
  // ESC to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  return createPortal(
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
      onClick={onClose}
    >
      {/* Backdrop */}
      <div
        style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
        className="animate-fade-in"
      />

      {/* Panel — near-fullscreen */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          maxWidth: "1400px",
          borderRadius: "16px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
        className="border border-[var(--border)] shadow-2xl bg-[var(--bg-primary)] animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-2.5 border-b border-[var(--border)] bg-[var(--bg-secondary)]"
          style={{ flexShrink: 0 }}
        >
          <div className="flex items-center gap-2.5">
            <Network className="h-4 w-4 text-neural-400" />
            <span className="text-sm font-semibold text-[var(--text-primary)]">
              Pipeline Architecture
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]">
              LangGraph
            </span>
          </div>
          <div className="flex items-center gap-1">
            <a
              href={GRAPH_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors"
              title="Open in new tab"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
              title="Close (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Iframe — takes all remaining space */}
        <iframe
          src={GRAPH_URL}
          style={{ flex: 1, width: "100%", border: "none", background: "#0f0f23" }}
          title="Pipeline Graph Architecture"
        />
      </div>
    </div>,
    document.body,
  );
}

export function GraphModalTrigger() {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="p-2 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-all duration-200"
        title="View LangGraph Architecture"
        aria-label="View pipeline graph architecture"
      >
        <Network className="h-4 w-4" />
      </button>

      {open && <GraphModal onClose={close} />}
    </>
  );
}

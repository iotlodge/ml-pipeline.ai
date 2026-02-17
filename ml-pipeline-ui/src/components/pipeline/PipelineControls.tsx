"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { Play, RotateCcw, Upload, Clock, Zap, ChevronDown, ChevronUp, Pencil } from "lucide-react";

interface PipelineControlsProps {
  onLaunch: (file?: File, objectives?: string) => void;
  onReset: () => void;
  loading: boolean;
  elapsed: number;
  hasRun: boolean;
  objectives?: string;
  onObjectivesChange?: (v: string) => void;
}

function formatElapsed(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

export function PipelineControls({
  onLaunch, onReset, loading, elapsed, hasRun,
  objectives = "", onObjectivesChange,
}: PipelineControlsProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [showObjectives, setShowObjectives] = useState(false);

  // Prevent browser from opening dropped files anywhere on the page
  useEffect(() => {
    const prevent = (e: DragEvent) => { e.preventDefault(); e.stopPropagation(); };
    window.addEventListener("dragover", prevent);
    window.addEventListener("drop", prevent);
    return () => {
      window.removeEventListener("dragover", prevent);
      window.removeEventListener("drop", prevent);
    };
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    const f = e.dataTransfer.files?.[0] || null;
    if (f) setFile(f);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
  };

  const handleLaunch = () => {
    onLaunch(file || undefined, objectives || undefined);
  };

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-neural-400" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            Mission Control
          </h3>
        </div>
        {loading && (
          <div className="flex items-center gap-1.5 text-xs font-mono text-neural-400">
            <Clock className="h-3.5 w-3.5 animate-pulse" />
            {formatElapsed(elapsed)}
          </div>
        )}
      </div>

      {/* File upload area */}
      <div
        onClick={() => fileRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative mb-3 border-2 border-dashed rounded-lg p-4 text-center cursor-pointer
                   transition-all duration-300 group
                   ${dragging
                     ? "border-neural-400 bg-neural-500/10 dark:bg-neural-500/20"
                     : "border-[var(--border)] hover:border-neural-400 hover:bg-neural-500/5 dark:hover:bg-neural-500/10"
                   }`}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.parquet,.json"
          onChange={handleFileChange}
          className="hidden"
        />
        <Upload className="h-6 w-6 mx-auto mb-2 text-[var(--text-tertiary)]
                          group-hover:text-neural-400 transition-colors" />
        {file ? (
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {file.name}
            <span className="text-[var(--text-tertiary)] ml-2">
              ({(file.size / 1024).toFixed(1)} KB)
            </span>
          </p>
        ) : (
          <p className="text-sm text-[var(--text-tertiary)]">
            Drop CSV, Parquet, or JSON — or use demo data
          </p>
        )}
      </div>

      {/* Objectives editor (collapsible) */}
      <div className="mb-4">
        <button
          onClick={() => setShowObjectives(!showObjectives)}
          disabled={loading}
          className="w-full flex items-center justify-between text-xs text-[var(--text-tertiary)]
                     hover:text-[var(--text-secondary)] transition-colors disabled:opacity-50"
        >
          <span className="flex items-center gap-1.5">
            <Pencil className="h-3 w-3" />
            Pipeline Objectives
          </span>
          {showObjectives ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
        {showObjectives && (
          <textarea
            value={objectives}
            onChange={(e) => onObjectivesChange?.(e.target.value)}
            disabled={loading}
            rows={3}
            placeholder="Describe your ML objectives..."
            className="mt-2 w-full text-xs rounded-lg border border-[var(--border)]
                       bg-[var(--bg-primary)] text-[var(--text-primary)]
                       placeholder:text-[var(--text-tertiary)]
                       p-3 resize-none focus:outline-none focus:border-neural-400
                       transition-colors disabled:opacity-50"
          />
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        {!hasRun || loading ? (
          <button
            onClick={handleLaunch}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5
                       rounded-lg font-semibold text-sm text-white
                       bg-gradient-to-r from-neural-500 to-neural-600
                       hover:from-neural-400 hover:to-neural-500
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-300
                       shadow-lg shadow-neural-500/20 hover:shadow-neural-500/40"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Launch Pipeline
              </>
            )}
          </button>
        ) : (
          <button
            onClick={() => {
              setFile(null);
              onReset();
            }}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5
                       rounded-lg font-semibold text-sm
                       border border-[var(--border)] text-[var(--text-secondary)]
                       hover:border-neural-400 hover:text-neural-400
                       transition-all duration-300"
          >
            <RotateCcw className="h-4 w-4" />
            New Run
          </button>
        )}
      </div>

      {/* Progress bar */}
      {loading && (
        <div className="mt-4 h-1 rounded-full bg-[var(--bg-tertiary)] overflow-hidden">
          <div className="h-full rounded-full progress-shimmer bg-neural-500/30" />
        </div>
      )}
    </div>
  );
}

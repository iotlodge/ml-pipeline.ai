"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { startPipeline, getPipelineStatus } from "@/lib/api";
import type { PipelineRun, PipelineStatus } from "@/lib/types";

const POLL_INTERVAL = 2000; // 2s while running
const TERMINAL: PipelineStatus[] = ["completed", "completed_with_errors", "failed"];

export function usePipeline() {
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const launch = useCallback(async (file?: File, objectives?: string) => {
    setError(null);
    setLoading(true);
    setElapsed(0);
    startTimeRef.current = Date.now();

    try {
      const { pipeline_id } = await startPipeline(file, objectives);

      // Initial state
      setRun({
        pipeline_id,
        status: "pending",
        phases: [],
        errors: [],
      });

      // Elapsed timer
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);

      // Status polling
      pollRef.current = setInterval(async () => {
        try {
          const data = await getPipelineStatus(pipeline_id);
          setRun(data);

          if (TERMINAL.includes(data.status)) {
            if (pollRef.current) clearInterval(pollRef.current);
            if (timerRef.current) clearInterval(timerRef.current);
            setLoading(false);
          }
        } catch (err) {
          console.error("Poll error:", err);
        }
      }, POLL_INTERVAL);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start pipeline");
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (pollRef.current) clearInterval(pollRef.current);
    setRun(null);
    setError(null);
    setLoading(false);
    setElapsed(0);
  }, []);

  return { run, loading, error, elapsed, launch, reset };
}

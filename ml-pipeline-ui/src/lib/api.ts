/* ------------------------------------------------------------------ */
/*  API client — talks to the FastAPI backend                          */
/* ------------------------------------------------------------------ */

import type { PipelineRun, PipelineRunRaw } from "./types";
import { transformRun } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...opts?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

/* -- Dataset upload ------------------------------------------------ */

async function uploadDataset(file: File): Promise<{ path: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/v1/datasets/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Upload failed (${res.status}): ${body}`);
  }
  return res.json();
}

/* -- Pipeline endpoints -------------------------------------------- */

const DEFAULT_DATASET = "/tmp/ml-pipeline/uploads/sample_data.csv";
const DEFAULT_OBJECTIVES =
  "Predict the target variable using the best classification model. " +
  "Focus on recall and generalization.";

export async function startPipeline(file?: File, objectives?: string): Promise<{ pipeline_id: string }> {
  let datasetPath = DEFAULT_DATASET;
  let format = "csv";

  // Step 1: Upload file if provided
  if (file) {
    const upload = await uploadDataset(file);
    datasetPath = upload.path;
    const ext = (upload.filename || "").split(".").pop()?.toLowerCase();
    if (ext === "parquet") format = "parquet";
    else if (ext === "json") format = "json";
  }

  // Step 2: Create pipeline with JSON body
  return request("/api/v1/pipelines", {
    method: "POST",
    body: JSON.stringify({
      dataset_path: datasetPath,
      objectives: objectives?.trim() || DEFAULT_OBJECTIVES,
      dataset_format: format,
    }),
  });
}

export async function getPipelineStatus(id: string): Promise<PipelineRun> {
  const raw = await request<PipelineRunRaw>(`/api/v1/pipelines/${id}`);
  return transformRun(raw);
}

/* -- Plot endpoints ----------------------------------------------- */

export interface PlotInfo {
  filename: string;
  title: string;
  url: string;
}

export async function getPipelinePlots(id: string): Promise<PlotInfo[]> {
  return request<PlotInfo[]>(`/api/v1/pipelines/${id}/plots`);
}

export function getPlotImageUrl(pipelineId: string, filename: string): string {
  return `${BASE}/api/v1/pipelines/${pipelineId}/plots/${filename}`;
}

/* -- Graph endpoints ---------------------------------------------- */

export async function getMermaidDefinition(): Promise<string> {
  const res = await fetch(`${BASE}/api/v1/graph/mermaid`);
  if (!res.ok) throw new Error("Failed to fetch mermaid");
  return res.text();
}

export function getGraphHtmlUrl(): string {
  return `${BASE}/api/v1/graph/html`;
}

/* -- Health ------------------------------------------------------- */

export async function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

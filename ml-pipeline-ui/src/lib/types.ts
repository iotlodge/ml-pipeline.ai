/* ------------------------------------------------------------------ */
/*  Pipeline domain types — mirrors the FastAPI backend schema         */
/* ------------------------------------------------------------------ */

export type PipelineStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type PhaseKey =
  | "data_profiling"
  | "feature_engineering"
  | "visualization"
  | "model_training"
  | "evaluation"
  | "critic_review";

export interface PhaseInfo {
  phase: PhaseKey;
  status: "pending" | "running" | "completed" | "error" | "will_rerun";
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  error?: string;
}

export interface DataProfile {
  shape?: [number, number];
  columns?: string[];
  dtypes?: Record<string, string>;
  missing_pct?: Record<string, number>;
  numeric_stats?: Record<string, Record<string, number>>;
  target_column?: string;
  target_distribution?: Record<string, number>;
  key_findings?: string;
  /* Backend summary key */
  task_type?: string;
}

export interface FeatureEngineering {
  new_columns?: string[];
  final_shape?: [number, number];
  transformations?: string[];
  /* Backend summary keys */
  new_shape?: [number, number];
  validation_passed?: boolean;
}

export interface Visualization {
  charts?: string[];
  interpretation?: string;
  /* Backend summary keys */
  plot_count?: number;
  plot_paths?: string[];
  key_insights?: string;
}

export interface ModelCandidate {
  name?: string;
  model_name?: string;
  algorithm?: string;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  cv_mean?: number;
  [key: string]: unknown;
}

export interface ModelResult {
  best_model_name?: string;
  candidates?: ModelCandidate[];
  feature_importance?: Record<string, number>;
}

export interface Evaluation {
  metrics?: Record<string, number>;
  classification_report?: string;
  summary?: string;
  recommendations?: string[];
  overfitting_risk?: string;
  /* Backend summary keys */
  test_metrics?: Record<string, number>;
  cv_mean?: number;
  cv_std?: number;
}

export interface CriticDecision {
  iteration?: number;
  decision?: string;
  reasoning?: string;
  /* Backend summary keys */
  assessment?: string;
  confidence?: number;
}

/* Raw shape from the backend PipelineStatusResponse */
export interface PipelineRunRaw {
  pipeline_id: string;
  status: PipelineStatus;
  current_phase?: string;
  objectives?: string;
  phase_timings?: Record<string, number>;
  loop_count?: number;
  errors?: Array<{ phase?: string; error?: string } | string>;
  data_profile?: DataProfile;
  feature_engineering?: FeatureEngineering;
  visualizations?: Visualization;
  model?: ModelResult;
  evaluation?: Evaluation;
  critic_decisions?: CriticDecision[];
  token_usage?: TokenUsage;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  llm_calls: number;
}

/* Enriched shape used by UI components */
export interface PipelineRun {
  pipeline_id: string;
  status: PipelineStatus;
  current_phase?: string;
  objectives?: string;
  phases?: PhaseInfo[];
  loop_count?: number;
  errors?: string[];
  data_profile?: DataProfile;
  feature_engineering?: FeatureEngineering;
  visualizations?: Visualization;
  model?: ModelResult;
  evaluation?: Evaluation;
  critic_decisions?: CriticDecision[];
  token_usage?: TokenUsage;
}

/* Phase ordering for deriving PhaseInfo[] from phase_timings */
const PHASE_ORDER: PhaseKey[] = [
  "data_profiling",
  "feature_engineering",
  "visualization",
  "model_training",
  "evaluation",
  "critic_review",
];

/** Transform backend raw response into the enriched UI shape */
export function transformRun(raw: PipelineRunRaw): PipelineRun {
  // Derive phases from phase_timings + current_phase
  // Critic stores timings as critic_review_1, critic_review_2, etc. — sum them up
  const timings = raw.phase_timings || {};

  // Pre-compute critic total by summing all critic_review_N keys
  let criticTotal = timings["critic_review"] ?? 0;
  for (const [k, v] of Object.entries(timings)) {
    if (k.startsWith("critic_review_") && typeof v === "number") {
      criticTotal += v;
    }
  }

  // Detect loop-back: if current_phase is earlier than phases that already ran,
  // those later phases should show "will_rerun" instead of staying "completed"
  const currentPhase = raw.current_phase ?? "";
  const currentIdx = PHASE_ORDER.indexOf(currentPhase as PhaseKey);
  const isRunning = raw.status === "running";
  const isFinalized = currentPhase === "finalized";
  const isLooping = isRunning && (raw.loop_count ?? 0) > 0 && !isFinalized;

  const phases: PhaseInfo[] = PHASE_ORDER.map((key, idx) => {
    const duration = key === "critic_review" ? (criticTotal > 0 ? criticTotal : undefined) : timings[key];
    const isCurrent = currentPhase === key;
    const criticDone = key === "critic_review" && isFinalized;
    const hasRun = (duration != null && duration > 0) || criticDone;

    let status: PhaseInfo["status"] = "pending";
    if (isCurrent && isRunning) {
      status = "running";
    } else if (hasRun) {
      // During a loop-back, phases AFTER the current running phase flip to "will_rerun"
      // so the user sees the pipeline going back through them
      if (isLooping && currentIdx >= 0 && idx > currentIdx && key !== "critic_review") {
        status = "will_rerun";
      } else {
        status = "completed";
      }
    }
    return { phase: key, status, duration_seconds: duration };
  });

  // Check for errored phases
  const rawErrors = raw.errors || [];
  const errorStrings: string[] = [];
  for (const e of rawErrors) {
    if (typeof e === "string") {
      errorStrings.push(e);
    } else if (e && typeof e === "object") {
      const msg = e.error || JSON.stringify(e);
      errorStrings.push(e.phase ? `[${e.phase}] ${msg}` : msg);
      // Mark phase as errored
      if (e.phase) {
        const p = phases.find((ph) => ph.phase === e.phase);
        if (p) p.status = "error";
      }
    }
  }

  return {
    pipeline_id: raw.pipeline_id,
    status: raw.status,
    current_phase: raw.current_phase,
    objectives: raw.objectives,
    phases,
    loop_count: raw.loop_count,
    errors: errorStrings.length > 0 ? errorStrings : undefined,
    data_profile: raw.data_profile,
    feature_engineering: raw.feature_engineering,
    visualizations: raw.visualizations,
    model: raw.model,
    evaluation: raw.evaluation,
    critic_decisions: raw.critic_decisions,
    token_usage: raw.token_usage,
  };
}

/* ------------------------------------------------------------------ */
/*  Phase metadata for UI rendering                                    */
/* ------------------------------------------------------------------ */

export interface PhaseMeta {
  key: PhaseKey;
  label: string;
  icon: string;
  description: string;
  color: string;
}

export const PHASE_META: PhaseMeta[] = [
  {
    key: "data_profiling",
    label: "Data Profiler",
    icon: "scan-search",
    description: "Analyzing dataset structure, distributions, and quality",
    color: "from-violet-500 to-purple-600",
  },
  {
    key: "feature_engineering",
    label: "Feature Engineer",
    icon: "wrench",
    description: "Generating and transforming features for model training",
    color: "from-cyan-500 to-blue-600",
  },
  {
    key: "visualization",
    label: "Visualizer",
    icon: "bar-chart-3",
    description: "Creating exploratory data analysis visualizations",
    color: "from-emerald-500 to-green-600",
  },
  {
    key: "model_training",
    label: "Model Trainer",
    icon: "brain",
    description: "Training and comparing candidate ML models",
    color: "from-orange-500 to-amber-600",
  },
  {
    key: "evaluation",
    label: "Evaluator",
    icon: "check-circle-2",
    description: "Evaluating model performance and generalization",
    color: "from-rose-500 to-pink-600",
  },
  {
    key: "critic_review",
    label: "Critic",
    icon: "message-square-warning",
    description: "Reviewing results and deciding next action",
    color: "from-yellow-500 to-orange-600",
  },
];

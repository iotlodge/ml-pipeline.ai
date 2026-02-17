"""Pipeline state schema — the nervous system of the entire graph.

Every node reads from and writes to PipelineState.
All sub-types are TypedDicts for LangGraph state compatibility.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


# ── Enums ─────────────────────────────────────────────────────────────────────


class MLPhase(str, Enum):
    """Pipeline phases — used for tracking and routing."""

    INITIALIZED = "initialized"
    DATA_PROFILING = "data_profiling"
    FEATURE_ENGINEERING = "feature_engineering"
    VISUALIZATION = "visualization"
    MODEL_TRAINING = "model_training"
    EVALUATION = "evaluation"
    CRITIC_REVIEW = "critic_review"
    FINALIZED = "finalized"


class TaskType(str, Enum):
    """ML task type — inferred from data + objectives."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    UNKNOWN = "unknown"


# ── Sub-Types ─────────────────────────────────────────────────────────────────


class DataSourceRef(TypedDict):
    """Reference to input dataset."""

    source_type: str  # "local", "s3", "url"
    location: str     # File path, S3 URI, or URL
    format: str       # "csv", "parquet", "json"
    size_bytes: int


class DataProfile(TypedDict):
    """Output from data profiling phase."""

    shape: list[int]  # [rows, cols]
    dtypes: dict[str, str]
    missing_counts: dict[str, int]
    missing_pct: dict[str, float]
    numeric_stats: dict[str, dict[str, float]]
    categorical_stats: dict[str, dict[str, int]]
    correlation_top: list[dict[str, Any]]  # Top correlated pairs
    key_findings: str  # LLM-generated summary
    target_column: str | None  # Inferred or specified target
    task_type: str  # "classification", "regression", etc.


class FeatureArtifact(TypedDict):
    """A single engineered feature."""

    name: str
    code_snippet: str  # Python expression that generates it
    source_columns: list[str]
    dtype: str
    rationale: str  # Why this feature was created


class FeatureEngineering(TypedDict):
    """Output from feature engineering phase."""

    features: list[FeatureArtifact]
    code_executed: str  # Full code that was run
    new_columns: list[str]
    dropped_columns: list[str]
    new_shape: list[int]
    validation_passed: bool
    validation_notes: str


class PlotArtifact(TypedDict):
    """A generated visualization."""

    title: str
    plot_type: str  # "histogram", "scatter", "heatmap", etc.
    file_path: str  # Path to saved PNG
    description: str  # What the plot shows
    interpretation: str  # LLM interpretation of patterns


class VisualizationOutput(TypedDict):
    """Output from visualization phase."""

    plots: list[PlotArtifact]
    key_insights: str  # LLM synthesis of all plots
    feature_suggestions: list[str]  # Additional features suggested by patterns
    modeling_concerns: list[str]  # Issues spotted (class imbalance, etc.)


class ModelCandidate(TypedDict):
    """A model evaluated during training."""

    name: str  # "RandomForest", "XGBoost", etc.
    algorithm: str  # sklearn class name
    hyperparams: dict[str, Any]
    cv_mean: float
    cv_std: float
    train_score: float
    val_score: float
    training_time_sec: float


class ModelArtifact(TypedDict):
    """Final trained model output."""

    best_model_name: str
    task_type: str
    candidates: list[ModelCandidate]
    best_hyperparams: dict[str, Any]
    feature_importance: dict[str, float]
    serialized_path: str  # Path to saved model file
    training_code: str  # Code that was executed
    target_column: str
    feature_columns: list[str]


class EvaluationMetrics(TypedDict):
    """Model evaluation results."""

    # Cross-validation
    cv_scores: list[float]
    cv_mean: float
    cv_std: float

    # Test set metrics
    test_metrics: dict[str, float]  # accuracy, f1, rmse, etc.

    # Overfitting check
    train_test_gap: float  # train_score - test_score
    overfitting_risk: str  # "low", "moderate", "high"

    # Artifacts
    evaluation_code: str
    plot_paths: list[str]  # Confusion matrix, ROC, residuals, etc.
    summary: str  # LLM interpretation of results


class CriticDecision(TypedDict):
    """Decision from Critic review — immutable history entry."""

    iteration: int
    overall_assessment: str  # "finalize", "refine_features", "retrain_model"
    confidence: float  # 0.0 to 1.0
    concerns: list[str]
    recommendations: list[str]
    reasoning: str


class PhaseError(TypedDict):
    """Error recorded during a pipeline phase."""

    phase: str
    error_type: str
    error_message: str
    recoverable: bool


# ── Main Pipeline State ───────────────────────────────────────────────────────


class PipelineState(TypedDict):
    """Master state object flowing through the entire LangGraph pipeline.

    Design principles:
    - All phase outputs are Optional (phases may not have run yet)
    - Errors accumulate; Critic reviews them
    - Decision logs are append-only history
    - Human gates are explicit state flags
    """

    # ── Input ─────────────────────────────────────────────────────────────
    pipeline_id: str
    user_objectives: str
    data_source: DataSourceRef

    # ── Phase Outputs (accumulated as pipeline progresses) ────────────────
    data_profile: DataProfile | None
    feature_engineering: FeatureEngineering | None
    visualizations: VisualizationOutput | None
    model: ModelArtifact | None
    evaluation: EvaluationMetrics | None

    # ── Critic Loop Control ───────────────────────────────────────────────
    critic_decisions: list[CriticDecision]
    loop_count: int
    max_loops: int

    # ── Execution Metadata ────────────────────────────────────────────────
    current_phase: str
    phase_timings: dict[str, float]  # phase_name -> seconds
    errors: list[PhaseError]

    # ── Working Directory (sandbox file I/O) ──────────────────────────────
    working_dir: str

    # ── Human-in-the-Loop ─────────────────────────────────────────────────
    awaiting_human_approval: bool
    human_feedback: str | None


# ── State Initialization Helper ───────────────────────────────────────────────


def create_initial_state(
    pipeline_id: str,
    objectives: str,
    data_source: DataSourceRef,
    working_dir: str,
    max_loops: int = 3,
) -> PipelineState:
    """Create a fresh pipeline state with all fields initialized."""
    return PipelineState(
        pipeline_id=pipeline_id,
        user_objectives=objectives,
        data_source=data_source,
        data_profile=None,
        feature_engineering=None,
        visualizations=None,
        model=None,
        evaluation=None,
        critic_decisions=[],
        loop_count=0,
        max_loops=max_loops,
        current_phase=MLPhase.INITIALIZED.value,
        phase_timings={},
        errors=[],
        working_dir=working_dir,
        awaiting_human_approval=False,
        human_feedback=None,
    )

"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────


class PipelineCreateRequest(BaseModel):
    """Request to create and execute a new ML pipeline."""

    dataset_path: str = Field(
        ...,
        description="Path to the input dataset (local path or S3 URI)",
        examples=["/data/titanic.csv", "s3://my-bucket/data/train.csv"],
    )
    objectives: str = Field(
        ...,
        description="Natural language description of the ML objective",
        examples=["Predict survival on the Titanic based on passenger features"],
    )
    dataset_format: str = Field(
        default="csv",
        description="Dataset file format",
        pattern="^(csv|parquet|json)$",
    )
    max_loops: Optional[int] = Field(
        default=None,
        description="Max critic review loop iterations (default from config)",
        ge=1,
        le=10,
    )
    llm_provider: Optional[str] = Field(
        default=None,
        description="Override LLM provider for this run",
        pattern="^(anthropic|openai)$",
    )


# ── Responses ─────────────────────────────────────────────────────────────────


class PipelineCreateResponse(BaseModel):
    """Response after pipeline creation."""

    pipeline_id: str
    status: str
    message: str = "Pipeline execution started"


class PipelineStatusResponse(BaseModel):
    """Pipeline status and results summary."""

    pipeline_id: str
    status: str
    current_phase: str = ""
    objectives: str = ""
    phase_timings: dict[str, float] = {}
    loop_count: int = 0
    errors: list[dict[str, Any]] = []
    data_profile: Optional[dict[str, Any]] = None
    feature_engineering: Optional[dict[str, Any]] = None
    visualizations: Optional[dict[str, Any]] = None
    model: Optional[dict[str, Any]] = None
    evaluation: Optional[dict[str, Any]] = None
    critic_decisions: Optional[list[dict[str, Any]]] = None
    token_usage: Optional[dict[str, int]] = None


class ArtifactListResponse(BaseModel):
    """List of artifact file paths."""

    pipeline_id: str
    artifacts: list[str]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    llm_provider: str = ""
    sandbox_type: str = ""

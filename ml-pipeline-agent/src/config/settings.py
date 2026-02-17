"""Application settings — single source of truth for all configuration."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Env-driven configuration. All values overridable via environment variables."""

    # ── Core ──────────────────────────────────────────────────────────────
    ENV: Literal["dev", "staging", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"

    # ── LLM Providers ─────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["anthropic", "openai"] = "anthropic"
    LLM_MODEL_CLAUDE: str = "claude-sonnet-4-5-20250929"
    LLM_MODEL_OPENAI: str = "gpt-4o"
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # ── Sandbox Execution ─────────────────────────────────────────────────
    SANDBOX_TYPE: Literal["subprocess", "docker"] = "subprocess"
    SANDBOX_TIMEOUT_SEC: int = 60
    SANDBOX_MEMORY_LIMIT_MB: int = 512

    # ── Pipeline ──────────────────────────────────────────────────────────
    MAX_LOOPS: int = 3
    CHECKPOINT_ENABLED: bool = True
    CHECKPOINT_BACKEND: Literal["memory", "sqlite"] = "sqlite"
    CHECKPOINT_PATH: str = "/tmp/ml-pipeline/checkpoints"

    # ── Artifact Storage ──────────────────────────────────────────────────
    ARTIFACT_STORAGE: Literal["local", "s3"] = "local"
    ARTIFACT_LOCAL_PATH: str = "/tmp/ml-pipeline/artifacts"
    ARTIFACT_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    # ── API ───────────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # ── Observability ─────────────────────────────────────────────────────
    LANGSMITH_ENABLED: bool = False
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "ml-pipeline-agent"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

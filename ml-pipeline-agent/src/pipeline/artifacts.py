"""Artifact storage — local filesystem and S3 support for models, plots, and metadata."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ArtifactStore:
    """Manages storage and retrieval of pipeline artifacts (models, plots, metadata)."""

    def __init__(self, base_path: str | None = None) -> None:
        self._base_path = Path(base_path or settings.ARTIFACT_LOCAL_PATH)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def pipeline_dir(self, pipeline_id: str) -> Path:
        """Get or create the artifact directory for a pipeline run."""
        d = self._base_path / pipeline_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_metadata(self, pipeline_id: str, metadata: dict[str, Any]) -> Path:
        """Save pipeline metadata as JSON."""
        path = self.pipeline_dir(pipeline_id) / "metadata.json"
        path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
        logger.info("Metadata saved", pipeline_id=pipeline_id, path=str(path))
        return path

    def load_metadata(self, pipeline_id: str) -> dict[str, Any] | None:
        """Load pipeline metadata."""
        path = self.pipeline_dir(pipeline_id) / "metadata.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def copy_from_working_dir(self, pipeline_id: str, working_dir: str) -> list[str]:
        """Copy relevant artifacts from sandbox working dir to persistent storage."""
        src = Path(working_dir)
        dst = self.pipeline_dir(pipeline_id)
        copied = []

        # Copy model files
        for pattern in ["*.joblib", "*.pkl", "*.json"]:
            for f in src.glob(pattern):
                shutil.copy2(f, dst / f.name)
                copied.append(str(dst / f.name))

        # Copy plots
        plots_dir = src / "plots"
        if plots_dir.exists():
            dst_plots = dst / "plots"
            dst_plots.mkdir(exist_ok=True)
            for f in plots_dir.glob("*.png"):
                shutil.copy2(f, dst_plots / f.name)
                copied.append(str(dst_plots / f.name))

        # Copy eval plots
        eval_dir = src / "eval_plots"
        if eval_dir.exists():
            dst_eval = dst / "eval_plots"
            dst_eval.mkdir(exist_ok=True)
            for f in eval_dir.glob("*.png"):
                shutil.copy2(f, dst_eval / f.name)
                copied.append(str(dst_eval / f.name))

        # Copy engineered dataset
        eng = src / "df_engineered.csv"
        if eng.exists():
            shutil.copy2(eng, dst / "df_engineered.csv")
            copied.append(str(dst / "df_engineered.csv"))

        logger.info("Artifacts copied", pipeline_id=pipeline_id, count=len(copied))
        return copied

    def list_artifacts(self, pipeline_id: str) -> list[str]:
        """List all artifact paths for a pipeline."""
        d = self.pipeline_dir(pipeline_id)
        return [str(f) for f in d.rglob("*") if f.is_file()]

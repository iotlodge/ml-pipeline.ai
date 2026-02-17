"""Pipeline executor — orchestrates graph execution, checkpointing, and state management."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from src.config.settings import settings
from src.graph.builder import build_pipeline_graph
from src.llm.base import LLMProvider
from src.pipeline.artifacts import ArtifactStore
from src.sandbox.base import ExecutionSandbox
from src.state.schema import DataSourceRef, PipelineState, create_initial_state
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Keys from state updates that carry phase output data
_PHASE_OUTPUT_KEYS = (
    "data_profile",
    "feature_engineering",
    "visualizations",
    "model",
    "evaluation",
    "critic_decisions",
)


class PipelineRun:
    """Represents a pipeline execution run."""

    def __init__(self, pipeline_id: str, status: str = "running") -> None:
        self.pipeline_id = pipeline_id
        self.status = status


class PipelineExecutor:
    """Manages pipeline graph execution lifecycle."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        sandbox: ExecutionSandbox,
    ) -> None:
        self._llm = llm_provider
        self._sandbox = sandbox
        self._artifact_store = ArtifactStore()

        # Checkpointer
        if settings.CHECKPOINT_BACKEND == "sqlite":
            try:
                import aiosqlite
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

                db_path = Path(settings.CHECKPOINT_PATH)
                db_path.mkdir(parents=True, exist_ok=True)
                # from_conn_string returns an async context manager —
                # use the lower-level constructor with a direct connection instead
                import asyncio

                async def _make_sqlite_saver() -> AsyncSqliteSaver:
                    conn = await aiosqlite.connect(str(db_path / "checkpoints.db"))
                    saver = AsyncSqliteSaver(conn)
                    await saver.setup()
                    return saver

                # Run in existing or new event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're inside an async context — schedule as a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        self._checkpointer = pool.submit(
                            lambda: asyncio.run(_make_sqlite_saver())
                        ).result()
                except RuntimeError:
                    # No running loop — safe to asyncio.run
                    self._checkpointer = asyncio.run(_make_sqlite_saver())

                logger.info("SQLite checkpointer initialized", path=str(db_path / "checkpoints.db"))
            except (ImportError, Exception) as e:
                logger.warning("SQLite checkpointer not available, falling back to memory", error=str(e))
                self._checkpointer = MemorySaver()
        else:
            self._checkpointer = MemorySaver()

        # Build graph
        self._graph = build_pipeline_graph(
            llm_provider=self._llm,
            sandbox=self._sandbox,
            checkpointer=self._checkpointer,
        )

        # In-memory state cache — written on EVERY node completion, not just at the end
        self._states: dict[str, dict[str, Any]] = {}

    def register_pipeline(self, pipeline_id: str, objectives: str, dataset_path: str) -> None:
        """Register a pipeline immediately so status polling works before execution starts."""
        self._states[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "objectives": objectives,
            "current_phase": "queued",
            "status": "running",
            "phase_timings": {},
            "loop_count": 0,
            "errors": [],
            "dataset_path": dataset_path,
        }

    async def execute(
        self,
        dataset_path: str,
        objectives: str,
        *,
        pipeline_id: str | None = None,
        dataset_format: str = "csv",
        max_loops: int | None = None,
    ) -> PipelineRun:
        """Execute a complete ML pipeline.

        Args:
            dataset_path: Path to the input dataset file.
            objectives: User's ML objective in natural language.
            pipeline_id: Externally-provided ID (from route). Generated if None.
            dataset_format: File format ("csv", "parquet", "json").
            max_loops: Override max critic loop count.

        Returns:
            PipelineRun with pipeline_id and final status.
        """
        if pipeline_id is None:
            pipeline_id = str(uuid.uuid4())

        # Create isolated working directory
        working_dir = tempfile.mkdtemp(prefix=f"pipeline_{pipeline_id[:8]}_")

        # Build data source ref
        data_source = DataSourceRef(
            source_type="local",
            location=dataset_path,
            format=dataset_format,
            size_bytes=Path(dataset_path).stat().st_size if Path(dataset_path).exists() else 0,
        )

        # Initialize state
        initial_state = create_initial_state(
            pipeline_id=pipeline_id,
            objectives=objectives,
            data_source=data_source,
            working_dir=working_dir,
            max_loops=max_loops or settings.MAX_LOOPS,
        )

        # Update cached state to "running"
        self._states[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "objectives": objectives,
            "current_phase": "initialized",
            "status": "running",
            "phase_timings": {},
            "loop_count": 0,
            "errors": [],
            "working_dir": working_dir,
        }

        logger.info(
            "Starting pipeline execution",
            pipeline_id=pipeline_id,
            dataset=dataset_path,
            objectives=objectives[:100],
        )

        # Execute graph
        config = {"configurable": {"thread_id": pipeline_id}}
        final_state: PipelineState | None = None

        try:
            async for event in self._graph.astream(initial_state, config=config):
                # event is a dict of node_name -> state_updates
                for node_name, state_update in event.items():
                    if isinstance(state_update, dict):
                        # Update cached state on EVERY node completion
                        phase = state_update.get("current_phase", "")
                        logger.info(
                            "Node completed",
                            pipeline_id=pipeline_id,
                            node=node_name,
                            phase=phase,
                        )
                        # Merge updates into cached state
                        cached = self._states.get(pipeline_id, {})
                        cached["current_phase"] = phase
                        cached["status"] = "running"
                        if "phase_timings" in state_update:
                            cached["phase_timings"] = state_update["phase_timings"]
                        if "errors" in state_update:
                            cached["errors"] = state_update["errors"]
                        if "loop_count" in state_update:
                            cached["loop_count"] = state_update["loop_count"]

                        # Propagate phase output data so status endpoint shows results
                        for key in _PHASE_OUTPUT_KEYS:
                            if key in state_update and state_update[key] is not None:
                                cached[key] = _summarize_phase_output(key, state_update[key])

                        self._states[pipeline_id] = cached

            # Get final state from checkpointer
            snapshot = await self._graph.aget_state(config)
            if snapshot and snapshot.values:
                final_state = snapshot.values

        except Exception as e:
            logger.error("Pipeline execution failed", pipeline_id=pipeline_id, error=str(e))
            # Update cached state with failure
            if pipeline_id in self._states:
                self._states[pipeline_id]["status"] = "failed"
                self._states[pipeline_id]["errors"] = self._states[pipeline_id].get("errors", []) + [
                    {"phase": "execution", "error_type": type(e).__name__, "error_message": str(e), "recoverable": False}
                ]
            return PipelineRun(pipeline_id=pipeline_id, status="failed")

        # Persist artifacts and final state
        if final_state:
            self._states[pipeline_id] = _state_to_metadata(final_state)
            self._states[pipeline_id]["status"] = "completed"
            self._artifact_store.copy_from_working_dir(pipeline_id, working_dir)
            self._artifact_store.save_metadata(pipeline_id, self._states[pipeline_id])

        status = "completed"
        if final_state and final_state.get("errors"):
            status = "completed_with_errors"
            self._states[pipeline_id]["status"] = status

        logger.info(
            "Pipeline execution finished",
            pipeline_id=pipeline_id,
            status=status,
            phases_completed=list(final_state.get("phase_timings", {}).keys()) if final_state else [],
        )

        return PipelineRun(pipeline_id=pipeline_id, status=status)

    async def get_status(self, pipeline_id: str) -> dict[str, Any] | None:
        """Get pipeline status and summary."""
        # Check in-memory cache first (live state)
        state = self._states.get(pipeline_id)
        if state:
            # Inject live token usage from the LLM provider
            snap = self._llm.token_usage.snapshot()
            state["token_usage"] = {
                "input_tokens": snap.input_tokens,
                "output_tokens": snap.output_tokens,
                "total_tokens": snap.total_tokens,
                "llm_calls": snap.llm_calls,
            }
            return state

        # Fall back to persisted artifacts
        metadata = self._artifact_store.load_metadata(pipeline_id)
        if metadata:
            return metadata

        return None

    async def list_pipelines(self) -> list[dict[str, Any]]:
        """List all known pipelines with basic status."""
        return [
            {
                "pipeline_id": pid,
                "status": state.get("status", "unknown"),
                "current_phase": state.get("current_phase", "unknown"),
                "objectives": state.get("objectives", "")[:100],
            }
            for pid, state in self._states.items()
        ]

    async def get_artifacts(self, pipeline_id: str) -> list[str]:
        """List artifact paths for a pipeline."""
        return self._artifact_store.list_artifacts(pipeline_id)


def _summarize_phase_output(key: str, data: Any) -> Any:
    """Create a serializable summary of phase output for the status cache.

    Handles both TypedDict-style dicts and dataclass-like objects.
    """
    def _get(obj: Any, field: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(field, default)
        return getattr(obj, field, default)

    try:
        if key == "data_profile":
            return {
                "shape": _get(data, "shape"),
                "task_type": _get(data, "task_type"),
                "target_column": _get(data, "target_column"),
                "key_findings": _truncate(_get(data, "key_findings", ""), 500),
            }
        elif key == "feature_engineering":
            return {
                "new_columns": _get(data, "new_columns", []),
                "new_shape": _get(data, "new_shape"),
                "validation_passed": _get(data, "validation_passed"),
            }
        elif key == "visualizations":
            plots = _get(data, "plots", [])
            plot_paths = []
            if plots:
                for p in plots:
                    fp = _get(p, "file_path", "")
                    if fp:
                        plot_paths.append(fp)
            return {
                "plot_count": len(plots) if plots else 0,
                "plot_paths": plot_paths,
                "key_insights": _truncate(_get(data, "key_insights", ""), 500),
            }
        elif key == "model":
            fi = _get(data, "feature_importance", {})
            # Pass through full candidates + feature_importance so the UI can render
            raw_candidates = _get(data, "candidates", [])
            candidates = []
            for c in (raw_candidates or []):
                candidates.append(_normalize_candidate(c))
            return {
                "best_model_name": _get(data, "best_model_name", "unknown"),
                "task_type": _get(data, "task_type"),
                "candidates": candidates,
                "feature_importance": dict(list(fi.items())[:15]) if isinstance(fi, dict) else {},
            }
        elif key == "evaluation":
            return {
                "cv_mean": _get(data, "cv_mean", 0),
                "cv_std": _get(data, "cv_std", 0),
                "test_metrics": _get(data, "test_metrics", {}),
                "overfitting_risk": _get(data, "overfitting_risk", "unknown"),
                "summary": _truncate(_get(data, "summary", ""), 500),
            }
        elif key == "critic_decisions":
            if isinstance(data, list):
                return [
                    {
                        "iteration": _get(d, "iteration", 0),
                        "assessment": _get(d, "overall_assessment", ""),
                        "confidence": _get(d, "confidence", 0),
                        "reasoning": _truncate(_get(d, "reasoning", ""), 200),
                    }
                    for d in data
                ]
            return data
    except Exception as e:
        logger.warning("Failed to summarize phase output", key=key, error=str(e))
        return {"error": f"Could not summarize: {str(e)}"}

    return data


def _normalize_candidate(c: Any) -> dict[str, Any]:
    """Normalize a model candidate to consistent keys for the frontend.

    LLM-generated JSON and TypedDict candidates may use varying key names.
    This maps them all to: name, accuracy, precision, recall, f1, cv_mean.
    """
    def _v(obj: Any, *keys: str) -> Any:
        for k in keys:
            val = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
            if val is not None:
                return val
        return None

    cv_mean = _v(c, "cv_mean", "cv_score", "mean_cv_score", "cross_val_mean")
    val_score = _v(c, "val_score", "test_score")
    accuracy = _v(c, "accuracy", "test_accuracy", "acc")
    # Fall back to cv_mean or val_score if no explicit accuracy
    if accuracy is None:
        accuracy = val_score if val_score is not None else cv_mean

    return {
        "name": _v(c, "name", "model_name", "algorithm", "model") or "Unknown",
        "accuracy": accuracy,
        "precision": _v(c, "precision", "precision_macro", "precision_weighted", "test_precision"),
        "recall": _v(c, "recall", "recall_macro", "recall_weighted", "test_recall"),
        "f1": _v(c, "f1", "f1_macro", "f1_weighted", "f1_score", "test_f1"),
        "cv_mean": cv_mean,
        "cv_std": _v(c, "cv_std", "cv_std_dev"),
        "train_score": _v(c, "train_score", "train_accuracy"),
        "val_score": val_score,
    }


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string to max_len characters."""
    if not isinstance(s, str):
        return str(s)[:max_len]
    return s[:max_len] if len(s) > max_len else s


def _state_to_metadata(state: PipelineState) -> dict[str, Any]:
    """Convert pipeline state to a serializable metadata dict."""
    metadata: dict[str, Any] = {
        "pipeline_id": state["pipeline_id"],
        "objectives": state["user_objectives"],
        "current_phase": state["current_phase"],
        "phase_timings": state.get("phase_timings", {}),
        "loop_count": state.get("loop_count", 0),
        "errors": state.get("errors", []),
        "working_dir": state.get("working_dir", ""),
    }

    if state.get("data_profile"):
        dp = state["data_profile"]
        metadata["data_profile"] = {
            "shape": dp["shape"],
            "task_type": dp["task_type"],
            "target_column": dp["target_column"],
            "key_findings": dp["key_findings"][:500],
        }

    if state.get("feature_engineering"):
        fe = state["feature_engineering"]
        metadata["feature_engineering"] = {
            "new_columns": fe["new_columns"],
            "new_shape": fe["new_shape"],
            "validation_passed": fe["validation_passed"],
        }

    if state.get("visualizations"):
        viz = state["visualizations"]
        plots = viz.get("plots", []) if isinstance(viz, dict) else getattr(viz, "plots", [])
        plot_paths = []
        if plots:
            for p in (plots or []):
                fp = p.get("file_path", "") if isinstance(p, dict) else getattr(p, "file_path", "")
                if fp:
                    plot_paths.append(fp)
        metadata["visualizations"] = {
            "plot_count": len(plots) if plots else 0,
            "plot_paths": plot_paths,
            "key_insights": _truncate(
                viz.get("key_insights", "") if isinstance(viz, dict) else getattr(viz, "key_insights", ""),
                500,
            ),
        }

    if state.get("model"):
        m = state["model"]
        raw_candidates = m.get("candidates", []) if isinstance(m, dict) else getattr(m, "candidates", [])
        candidates = [_normalize_candidate(c) for c in (raw_candidates or [])]
        fi = m.get("feature_importance", {}) if isinstance(m, dict) else getattr(m, "feature_importance", {})
        metadata["model"] = {
            "best_model_name": m["best_model_name"] if isinstance(m, dict) else getattr(m, "best_model_name", "unknown"),
            "task_type": m["task_type"] if isinstance(m, dict) else getattr(m, "task_type", None),
            "candidates": candidates,
            "feature_importance": dict(list(fi.items())[:15]) if isinstance(fi, dict) else {},
        }

    if state.get("evaluation"):
        ev = state["evaluation"]
        metadata["evaluation"] = {
            "cv_mean": ev["cv_mean"],
            "cv_std": ev["cv_std"],
            "test_metrics": ev["test_metrics"],
            "overfitting_risk": ev["overfitting_risk"],
            "summary": ev["summary"],
        }

    if state.get("critic_decisions"):
        metadata["critic_decisions"] = [
            {
                "iteration": d["iteration"],
                "assessment": d["overall_assessment"],
                "confidence": d["confidence"],
                "reasoning": d["reasoning"],
            }
            for d in state["critic_decisions"]
        ]

    return metadata

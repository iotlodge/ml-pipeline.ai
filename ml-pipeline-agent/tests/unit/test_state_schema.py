"""Tests for state schema initialization and helpers."""

from __future__ import annotations

from src.state.schema import (
    DataSourceRef,
    MLPhase,
    PipelineState,
    TaskType,
    create_initial_state,
)


class TestStateSchema:
    def test_create_initial_state(self) -> None:
        ds = DataSourceRef(
            source_type="local",
            location="/data/test.csv",
            format="csv",
            size_bytes=1024,
        )
        state = create_initial_state(
            pipeline_id="test-123",
            objectives="Predict churn",
            data_source=ds,
            working_dir="/tmp/test",
        )

        assert state["pipeline_id"] == "test-123"
        assert state["user_objectives"] == "Predict churn"
        assert state["current_phase"] == MLPhase.INITIALIZED.value
        assert state["loop_count"] == 0
        assert state["max_loops"] == 3
        assert state["data_profile"] is None
        assert state["model"] is None
        assert state["errors"] == []
        assert state["critic_decisions"] == []
        assert state["awaiting_human_approval"] is False

    def test_custom_max_loops(self) -> None:
        ds = DataSourceRef(source_type="local", location="/test.csv", format="csv", size_bytes=0)
        state = create_initial_state(
            pipeline_id="test",
            objectives="test",
            data_source=ds,
            working_dir="/tmp",
            max_loops=5,
        )
        assert state["max_loops"] == 5

    def test_ml_phase_enum(self) -> None:
        assert MLPhase.DATA_PROFILING.value == "data_profiling"
        assert MLPhase.FINALIZED.value == "finalized"

    def test_task_type_enum(self) -> None:
        assert TaskType.CLASSIFICATION.value == "classification"
        assert TaskType.REGRESSION.value == "regression"

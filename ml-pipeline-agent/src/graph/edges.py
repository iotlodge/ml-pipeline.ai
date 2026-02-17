"""Conditional edge routing — Critic decision drives loop-back or finalization."""

from __future__ import annotations

from typing import Literal

from src.state.schema import PipelineState
from src.utils.logging import get_logger

logger = get_logger(__name__)


def route_from_critic(
    state: PipelineState,
) -> Literal["feature_engineer", "model_trainer", "finalize"]:
    """Conditional routing based on Critic's latest decision.

    Routes:
        "feature_engineer" — Critic found feature issues, loop back
        "model_trainer"    — Critic found model issues, retrain
        "finalize"         — Pipeline complete (or max loops hit)
    """
    if not state.get("critic_decisions"):
        logger.warning("No critic decisions found, finalizing")
        return "finalize"

    latest = state["critic_decisions"][-1]
    assessment = latest["overall_assessment"]

    # Safety: max loops guard (should already be handled by critic node, but belt + suspenders)
    if state["loop_count"] >= state["max_loops"]:
        logger.info("Max loops reached at routing level, forcing finalize")
        return "finalize"

    if assessment == "refine_features":
        logger.info(
            "Routing back to feature engineering",
            iteration=latest["iteration"],
            concerns=latest["concerns"],
        )
        return "feature_engineer"

    elif assessment == "retrain_model":
        logger.info(
            "Routing back to model training",
            iteration=latest["iteration"],
            concerns=latest["concerns"],
        )
        return "model_trainer"

    else:
        logger.info(
            "Finalizing pipeline",
            confidence=latest["confidence"],
        )
        return "finalize"

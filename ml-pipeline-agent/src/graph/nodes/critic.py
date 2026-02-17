"""Critic Node — reviews entire pipeline, decides to finalize or loop back."""

from __future__ import annotations

import json
import time
from typing import Any

from src.llm.base import LLMProvider
from src.llm.prompts import CRITIC_REVIEW, SYSTEM_CRITIC
from src.state.schema import (
    CriticDecision,
    MLPhase,
    PhaseError,
    PipelineState,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


def critic_node(llm: LLMProvider):
    """Factory: returns the critic review node function.

    The Critic does NOT execute code — it reviews the entire decision chain
    and decides whether to finalize or route back to a specific phase.
    """

    async def node(state: PipelineState) -> dict[str, Any]:
        logger.info(
            "Starting critic review",
            pipeline_id=state["pipeline_id"],
            iteration=state["loop_count"] + 1,
        )
        start = time.monotonic()

        state_updates: dict[str, Any] = {
            "current_phase": MLPhase.CRITIC_REVIEW.value,
        }

        try:
            # Build comprehensive summary for the critic
            profile_summary = "Not available"
            if state.get("data_profile"):
                dp = state["data_profile"]
                profile_summary = (
                    f"Shape: {dp['shape']}, Task: {dp['task_type']}, "
                    f"Target: {dp['target_column']}\n"
                    f"Key findings: {dp['key_findings'][:500]}"
                )

            features_summary = "Not available"
            if state.get("feature_engineering"):
                fe = state["feature_engineering"]
                features_summary = (
                    f"New features: {fe['new_columns']}, "
                    f"Shape: {fe['new_shape']}, "
                    f"Validation: {'passed' if fe['validation_passed'] else 'FAILED'}\n"
                    f"Notes: {fe['validation_notes'][:300]}"
                )

            viz_insights = "Not available"
            if state.get("visualizations"):
                viz_insights = state["visualizations"]["key_insights"][:500]

            model_summary = "Not available"
            if state.get("model"):
                m = state["model"]
                model_summary = (
                    f"Best model: {m['best_model_name']}, "
                    f"Candidates evaluated: {len(m['candidates'])}\n"
                    f"Top feature importances: {dict(list(m['feature_importance'].items())[:5])}"
                )

            eval_metrics = "Not available"
            if state.get("evaluation"):
                ev = state["evaluation"]
                eval_metrics = (
                    f"CV mean: {ev['cv_mean']:.4f} (±{ev['cv_std']:.4f})\n"
                    f"Test metrics: {json.dumps(ev['test_metrics'])}\n"
                    f"Overfitting risk: {ev['overfitting_risk']} "
                    f"(train-test gap: {ev['train_test_gap']:.4f})\n"
                    f"Summary: {ev['summary'][:300]}"
                )

            errors_summary = "None"
            if state["errors"]:
                errors_summary = json.dumps(
                    [{"phase": e["phase"], "error": e["error_message"][:100]} for e in state["errors"]],
                    indent=2,
                )

            previous_decisions = "None"
            if state["critic_decisions"]:
                previous_decisions = json.dumps(
                    [
                        {
                            "iteration": d["iteration"],
                            "assessment": d["overall_assessment"],
                            "concerns": d["concerns"],
                        }
                        for d in state["critic_decisions"]
                    ],
                    indent=2,
                )

            # 1. LLM critic review
            decision = await llm.invoke_with_structured_output(
                CRITIC_REVIEW.format(
                    objectives=state["user_objectives"],
                    profile_summary=profile_summary,
                    features_summary=features_summary,
                    viz_insights=viz_insights,
                    model_summary=model_summary,
                    eval_metrics=eval_metrics,
                    errors=errors_summary,
                    loop_count=state["loop_count"] + 1,
                    max_loops=state["max_loops"],
                    previous_decisions=previous_decisions,
                ),
                system=SYSTEM_CRITIC,
                response_schema={
                    "overall_assessment": "string",
                    "confidence": "number",
                    "concerns": ["string"],
                    "recommendations": ["string"],
                    "reasoning": "string",
                },
                temperature=0.3,
            )

            # 2. Validate assessment value
            valid_assessments = {"finalize", "refine_features", "retrain_model"}
            assessment = decision.get("overall_assessment", "finalize")
            if assessment not in valid_assessments:
                logger.warning(f"Invalid critic assessment: {assessment}, defaulting to finalize")
                assessment = "finalize"

            # 3. Force finalize if at max loops
            if state["loop_count"] + 1 >= state["max_loops"] and assessment != "finalize":
                logger.info(
                    "Max loops reached, forcing finalization",
                    requested=assessment,
                    loop_count=state["loop_count"] + 1,
                )
                decision["concerns"].append(
                    f"Forced finalization: reached max loop limit ({state['max_loops']})"
                )
                assessment = "finalize"

            # 4. Build critic decision
            critic_decision = CriticDecision(
                iteration=state["loop_count"] + 1,
                overall_assessment=assessment,
                confidence=min(1.0, max(0.0, decision.get("confidence", 0.5))),
                concerns=decision.get("concerns", []),
                recommendations=decision.get("recommendations", []),
                reasoning=decision.get("reasoning", ""),
            )

            elapsed = time.monotonic() - start

            # 5. Update state
            state_updates["critic_decisions"] = state["critic_decisions"] + [critic_decision]
            state_updates["loop_count"] = state["loop_count"] + (0 if assessment == "finalize" else 1)
            state_updates["phase_timings"] = {
                **state["phase_timings"],
                f"critic_review_{state['loop_count'] + 1}": round(elapsed, 2),
            }

            if assessment == "finalize":
                state_updates["current_phase"] = MLPhase.FINALIZED.value

            logger.info(
                "Critic review complete",
                pipeline_id=state["pipeline_id"],
                assessment=assessment,
                confidence=decision.get("confidence"),
                elapsed=f"{elapsed:.2f}s",
            )

        except Exception as e:
            logger.error("Critic review error", error=str(e))
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="critic_review",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    recoverable=False,
                )
            ]
            # On critic failure, finalize to avoid stuck pipeline
            state_updates["critic_decisions"] = state["critic_decisions"] + [
                CriticDecision(
                    iteration=state["loop_count"] + 1,
                    overall_assessment="finalize",
                    confidence=0.0,
                    concerns=[f"Critic failed: {e}"],
                    recommendations=["Manual review required"],
                    reasoning="Forced finalization due to critic error.",
                )
            ]

        return state_updates

    return node

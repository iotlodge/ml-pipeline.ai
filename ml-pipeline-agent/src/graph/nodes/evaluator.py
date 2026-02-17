"""Evaluator Node — cross-validation, test metrics, overfitting analysis."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from src.llm.base import LLMProvider
from src.llm.prompts import EVALUATION_CODE, SYSTEM_ML_ANALYST, SYSTEM_ML_ENGINEER
from src.sandbox.base import ExecutionSandbox
from src.state.schema import (
    EvaluationMetrics,
    MLPhase,
    PhaseError,
    PipelineState,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

EVAL_WRAPPER = """
import pandas as pd
import numpy as np
import joblib
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# MODEL AND DATA ARE ALREADY LOADED — DO NOT RE-LOAD
# `best_model` is your trained model. `X_test`, `y_test`,
# `X_train`, `y_train` are ready. `eval_dir` is for plots.
# ============================================================

working_dir = '{working_dir}'

# Load test data
X_test = pd.read_csv(f'{{working_dir}}/X_test.csv')
y_test = pd.read_csv(f'{{working_dir}}/y_test.csv').iloc[:, 0]
X_train = pd.read_csv(f'{{working_dir}}/X_train.csv')
y_train = pd.read_csv(f'{{working_dir}}/y_train.csv').iloc[:, 0]

# Load model
model_path = f'{{working_dir}}/best_model.joblib'
if os.path.exists(model_path):
    best_model = joblib.load(model_path)
else:
    print(json.dumps({{'error': 'Model file not found'}}))
    exit(1)

eval_dir = f'{{working_dir}}/eval_plots'
os.makedirs(eval_dir, exist_ok=True)

print(f"Model loaded: {{type(best_model).__name__}}, X_test: {{X_test.shape}}")

# ---- Agent-generated evaluation code starts ----
# REMINDER: best_model, X_test, y_test, X_train, y_train are already loaded.
# eval_dir is set for saving plots. Do NOT call joblib.load() or pd.read_csv().
{agent_code}
# ---- Agent-generated evaluation code ends ----
"""


def evaluator_node(llm: LLMProvider, sandbox: ExecutionSandbox):
    """Factory: returns the evaluation node function."""

    async def node(state: PipelineState) -> dict[str, Any]:
        logger.info("Starting evaluation", pipeline_id=state["pipeline_id"])
        start = time.monotonic()

        state_updates: dict[str, Any] = {
            "current_phase": MLPhase.EVALUATION.value,
        }

        model = state.get("model")
        profile = state.get("data_profile")
        if not model or not profile:
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="evaluation",
                    error_type="MissingDependency",
                    error_message="Model or profile not available",
                    recoverable=False,
                )
            ]
            return state_updates

        try:
            # 1. Generate evaluation code via LLM
            training_metrics = {}
            if model["candidates"]:
                # Candidates may use "name", "model_name", "algorithm", etc.
                best = None
                for c in model["candidates"]:
                    if not isinstance(c, dict):
                        continue
                    cname = c.get("name") or c.get("model_name") or c.get("algorithm") or ""
                    if cname == model["best_model_name"]:
                        best = c
                        break
                if best is None and model["candidates"]:
                    first = model["candidates"][0]
                    best = first if isinstance(first, dict) else {}
                if best is None:
                    best = {}
                training_metrics = {
                    "cv_mean": best.get("cv_mean", 0),
                    "train_score": best.get("train_score", 0),
                    "val_score": best.get("val_score", 0),
                }

            agent_code = await llm.invoke(
                EVALUATION_CODE.format(
                    objectives=state["user_objectives"],
                    task_type=profile["task_type"],
                    best_model_name=model["best_model_name"],
                    training_metrics=json.dumps(training_metrics),
                ),
                system=SYSTEM_ML_ENGINEER,
                temperature=0.4,
            )
            agent_code = _clean_code_block(agent_code)
            agent_code = _sanitize_eval_code(agent_code)

            # 2. Execute evaluation
            full_code = EVAL_WRAPPER.format(
                agent_code=agent_code,
                working_dir=state["working_dir"],
            )

            result = await sandbox.execute(
                full_code,
                working_dir=state["working_dir"],
                timeout_sec=120,
            )

            if result.failed:
                logger.warning("Evaluation code failed, requesting fix", error=result.error_message)
                # Retry once
                fix_prompt = (
                    f"The following evaluation code failed:\n```python\n{agent_code}\n```\n"
                    f"Error: {result.stderr}\n\n"
                    f"IMPORTANT: best_model, X_test, y_test, X_train, y_train are ALREADY LOADED. "
                    f"eval_dir is already set. Do NOT use joblib.load(), pd.read_csv(), or plt.show(). "
                    f"Fix the code. Return ONLY corrected executable Python code, no markdown."
                )
                agent_code = await llm.invoke(fix_prompt, system=SYSTEM_ML_ENGINEER, temperature=0.3)
                agent_code = _clean_code_block(agent_code)
                agent_code = _sanitize_eval_code(agent_code)

                full_code = EVAL_WRAPPER.format(
                    agent_code=agent_code,
                    working_dir=state["working_dir"],
                )
                result = await sandbox.execute(full_code, working_dir=state["working_dir"], timeout_sec=120)

                if result.failed:
                    state_updates["errors"] = state["errors"] + [
                        PhaseError(
                            phase="evaluation",
                            error_type=result.error_type or "ExecutionError",
                            error_message=f"Evaluation failed after retry: {result.error_message}",
                            recoverable=True,
                        )
                    ]
                    return state_updates

            # 3. Parse evaluation results
            eval_output = _parse_eval_output(result.stdout)

            # 4. LLM interpretation of results (analysis, not code generation)
            summary = await llm.invoke(
                f"Summarize these model evaluation results in 3-4 sentences. "
                f"Focus on model quality, overfitting risk, and whether it meets "
                f"the objective: {state['user_objectives']}\n\n"
                f"Metrics: {json.dumps(eval_output)}",
                system=SYSTEM_ML_ANALYST,
                temperature=0.5,
            )

            # 5. Calculate overfitting risk
            train_score = eval_output.get("train_score", 0)
            test_score = eval_output.get("test_score", 0)
            gap = train_score - test_score
            overfitting_risk = "low" if gap < 0.05 else "moderate" if gap < 0.15 else "high"

            eval_metrics = EvaluationMetrics(
                cv_scores=eval_output.get("cv_scores", []),
                cv_mean=eval_output.get("cv_mean", 0.0),
                cv_std=eval_output.get("cv_std", 0.0),
                test_metrics=eval_output.get("test_metrics", {}),
                train_test_gap=round(gap, 4),
                overfitting_risk=overfitting_risk,
                evaluation_code=agent_code,
                plot_paths=eval_output.get("plot_paths", []),
                summary=summary,
            )

            elapsed = time.monotonic() - start
            state_updates["evaluation"] = eval_metrics
            state_updates["phase_timings"] = {
                **state["phase_timings"],
                "evaluation": round(elapsed, 2),
            }

            logger.info(
                "Evaluation complete",
                pipeline_id=state["pipeline_id"],
                overfitting_risk=overfitting_risk,
                elapsed=f"{elapsed:.2f}s",
            )

        except Exception as e:
            logger.error("Evaluation error", error=str(e))
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="evaluation",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    recoverable=True,
                )
            ]

        return state_updates

    return node


def _sanitize_eval_code(code: str) -> str:
    """Remove patterns the LLM might generate that conflict with the wrapper."""
    lines = code.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Remove any pd.read_csv / pd.read_* calls (wrapper already loads data)
        if re.match(r'.*pd\.read_(csv|parquet|json|excel|feather)\s*\(', stripped):
            cleaned.append(f"# REMOVED (data already loaded): {stripped}")
            continue
        # Remove joblib.load calls (wrapper already loads model)
        if re.match(r'.*joblib\.load\s*\(', stripped):
            cleaned.append(f"# REMOVED (model already loaded): {stripped}")
            continue
        # Remove plt.show() calls
        if re.match(r'.*plt\.show\s*\(', stripped):
            cleaned.append(f"# REMOVED (no display): {stripped}")
            continue
        # Remove os.makedirs (wrapper handles it)
        if re.match(r'.*os\.makedirs\s*\(', stripped):
            cleaned.append(f"# REMOVED (dirs already created): {stripped}")
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _parse_eval_output(stdout: str) -> dict[str, Any]:
    """Parse structured JSON from evaluation stdout."""
    lines = stdout.strip().splitlines()
    for line in reversed(lines):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def _clean_code_block(code: str) -> str:
    code = code.strip()
    if code.startswith("```python"):
        code = code[len("```python"):]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()

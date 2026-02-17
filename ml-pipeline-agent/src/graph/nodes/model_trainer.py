"""Model Trainer Node — model selection, training, hyperparameter optimization."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from src.llm.base import LLMProvider
from src.llm.prompts import MODEL_SELECTION_CODE, SYSTEM_ML_ENGINEER
from src.sandbox.base import ExecutionSandbox
from src.state.schema import (
    MLPhase,
    ModelArtifact,
    PhaseError,
    PipelineState,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

TRAINING_WRAPPER = """
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
import joblib
import json
import os
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# DATA IS ALREADY LOADED — DO NOT RE-LOAD OR RE-SPLIT
# The variables X_train, X_test, y_train, y_test are ready.
# Just use them directly for model training.
# ============================================================

# Load engineered dataset
engineered_path = '{working_dir}/df_engineered.csv'
if os.path.exists(engineered_path):
    df = pd.read_csv(engineered_path)
else:
    df = pd.read_{format}('{location}')

target_column = '{target_column}'
feature_columns = [c for c in df.columns if c != target_column]

# Separate features/target
X = df[feature_columns]
y = df[target_column]

# Handle remaining non-numeric columns
for col in X.select_dtypes(include=['object', 'category']).columns:
    X[col] = pd.Categorical(X[col]).codes

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42,
    stratify=y if '{task_type}' == 'classification' and y.nunique() <= 50 else None
)

# Save test set for evaluator
X_test.to_csv('{working_dir}/X_test.csv', index=False)
y_test.to_csv('{working_dir}/y_test.csv', index=False)
X_train.to_csv('{working_dir}/X_train.csv', index=False)
y_train.to_csv('{working_dir}/y_train.csv', index=False)

print(f"Data loaded: X_train={{X_train.shape}}, X_test={{X_test.shape}}")

# ---- Agent-generated training code starts ----
# REMINDER: X_train, X_test, y_train, y_test are already defined above.
# Do NOT call pd.read_csv(), train_test_split(), or any file loading.
{agent_code}
# ---- Agent-generated training code ends ----
"""


def model_trainer_node(llm: LLMProvider, sandbox: ExecutionSandbox):
    """Factory: returns the model training node function."""

    async def node(state: PipelineState) -> dict[str, Any]:
        logger.info("Starting model training", pipeline_id=state["pipeline_id"])
        start = time.monotonic()

        state_updates: dict[str, Any] = {
            "current_phase": MLPhase.MODEL_TRAINING.value,
        }

        profile = state.get("data_profile")
        if not profile:
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="model_training",
                    error_type="MissingDependency",
                    error_message="Data profile not available",
                    recoverable=False,
                )
            ]
            return state_updates

        target_column = profile["target_column"] or "target"
        task_type = profile["task_type"]
        feature_columns = [c for c in profile["dtypes"] if c != target_column]

        try:
            # Build context from previous phases
            viz_insights = ""
            if state.get("visualizations"):
                viz_insights = state["visualizations"]["key_insights"]

            fe_summary = ""
            if state.get("feature_engineering"):
                fe = state["feature_engineering"]
                fe_summary = f"New features: {fe['new_columns']}. Shape: {fe['new_shape']}"

            # Include critic feedback if looping back
            critic_context = ""
            if state["critic_decisions"]:
                latest = state["critic_decisions"][-1]
                if latest["overall_assessment"] == "retrain_model":
                    critic_context = (
                        f"\n\nPREVIOUS CRITIC FEEDBACK (iteration {latest['iteration']}):\n"
                        f"Concerns: {json.dumps(latest['concerns'])}\n"
                        f"Recommendations: {json.dumps(latest['recommendations'])}\n"
                        f"Address these issues in your model selection and training."
                    )

            # 1. Generate training code via LLM
            agent_code = await llm.invoke(
                MODEL_SELECTION_CODE.format(
                    objectives=state["user_objectives"] + critic_context,
                    task_type=task_type,
                    target_column=target_column,
                    feature_columns=feature_columns[:30],  # Truncate for prompt size
                    shape=profile["shape"],
                    key_insights=f"{viz_insights}\n{fe_summary}",
                ),
                system=SYSTEM_ML_ENGINEER,
                temperature=0.4,
            )
            agent_code = _clean_code_block(agent_code)
            agent_code = _sanitize_agent_code(agent_code)

            # 2. Execute training code
            ds = state["data_source"]
            full_code = TRAINING_WRAPPER.format(
                format=ds["format"],
                location=ds["location"],
                target_column=target_column,
                task_type=task_type,
                agent_code=agent_code,
                working_dir=state["working_dir"],
            )

            result = await sandbox.execute(
                full_code,
                working_dir=state["working_dir"],
                timeout_sec=300,  # Training can take longer
            )

            if result.failed:
                logger.warning("Training code failed, requesting fix", error=result.error_message)
                # Retry once with stronger constraints
                fix_prompt = (
                    f"The following training code failed:\n```python\n{agent_code}\n```\n"
                    f"Error: {result.stderr}\n\n"
                    f"IMPORTANT: X_train, X_test, y_train, y_test are ALREADY LOADED. "
                    f"Do NOT use pd.read_csv() or train_test_split(). "
                    f"Fix the code. Return ONLY corrected executable Python code, no markdown."
                )
                agent_code = await llm.invoke(fix_prompt, system=SYSTEM_ML_ENGINEER, temperature=0.3)
                agent_code = _clean_code_block(agent_code)
                agent_code = _sanitize_agent_code(agent_code)

                full_code = TRAINING_WRAPPER.format(
                    format=ds["format"],
                    location=ds["location"],
                    target_column=target_column,
                    task_type=task_type,
                    agent_code=agent_code,
                    working_dir=state["working_dir"],
                )
                result = await sandbox.execute(full_code, working_dir=state["working_dir"], timeout_sec=300)

                if result.failed:
                    state_updates["errors"] = state["errors"] + [
                        PhaseError(
                            phase="model_training",
                            error_type=result.error_type or "ExecutionError",
                            error_message=f"Training failed after retry: {result.error_message}",
                            recoverable=True,
                        )
                    ]
                    return state_updates

            # 3. Parse training results from stdout
            training_output = _parse_training_output(result.stdout)

            # 4. Build model artifact
            model_artifact = ModelArtifact(
                best_model_name=training_output.get("best_model", "unknown"),
                task_type=task_type,
                candidates=training_output.get("candidates", []),
                best_hyperparams=training_output.get("best_hyperparams", {}),
                feature_importance=training_output.get("feature_importance", {}),
                serialized_path=f"{state['working_dir']}/best_model.joblib",
                training_code=agent_code,
                target_column=target_column,
                feature_columns=feature_columns,
            )

            elapsed = time.monotonic() - start
            state_updates["model"] = model_artifact
            state_updates["phase_timings"] = {
                **state["phase_timings"],
                "model_training": round(elapsed, 2),
            }

            logger.info(
                "Model training complete",
                pipeline_id=state["pipeline_id"],
                best_model=training_output.get("best_model"),
                elapsed=f"{elapsed:.2f}s",
            )

        except Exception as e:
            logger.error("Model training error", error=str(e))
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="model_training",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    recoverable=True,
                )
            ]

        return state_updates

    return node


def _sanitize_agent_code(code: str) -> str:
    """Remove dangerous patterns the LLM might generate despite prompt instructions."""
    lines = code.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Remove any pd.read_csv / pd.read_* calls (wrapper already loads data)
        if re.match(r'.*pd\.read_(csv|parquet|json|excel|feather)\s*\(', stripped):
            cleaned.append(f"# REMOVED (data already loaded): {stripped}")
            continue
        # Remove any train_test_split calls (wrapper already splits)
        if 'train_test_split(' in stripped and not stripped.startswith('#'):
            cleaned.append(f"# REMOVED (already split): {stripped}")
            continue
        # Remove os.makedirs / os.path / pathlib directory operations
        if re.match(r'.*os\.(makedirs|mkdir|path\.join)\s*\(', stripped):
            cleaned.append(f"# REMOVED (env handles dirs): {stripped}")
            continue
        if re.match(r'.*(Path\(|pathlib)', stripped) and 'mkdir' in stripped:
            cleaned.append(f"# REMOVED (env handles dirs): {stripped}")
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _parse_training_output(stdout: str) -> dict[str, Any]:
    """Parse structured JSON from training stdout."""
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

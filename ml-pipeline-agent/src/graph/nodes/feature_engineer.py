"""Feature Engineer Node — generates, executes, and validates feature engineering code."""

from __future__ import annotations

import json
import time
from typing import Any

from src.llm.base import LLMProvider
from src.llm.prompts import (
    FEATURE_ENGINEERING_CODE,
    FEATURE_VALIDATION,
    SYSTEM_ML_ENGINEER,
)
from src.sandbox.base import ExecutionSandbox
from src.state.schema import (
    FeatureEngineering,
    MLPhase,
    PhaseError,
    PipelineState,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Wrapper that saves engineered df and reports results
CODE_WRAPPER = """
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

df = pd.read_{format}('{location}')
original_columns = list(df.columns)

# ---- Agent-generated code starts ----
{agent_code}
# ---- Agent-generated code ends ----

# Report results
new_columns = [c for c in df_engineered.columns if c not in original_columns]
dropped_columns = [c for c in original_columns if c not in df_engineered.columns]

# Save engineered dataset
df_engineered.to_csv('{working_dir}/df_engineered.csv', index=False)

result = {{
    'new_columns': new_columns,
    'dropped_columns': dropped_columns,
    'new_shape': list(df_engineered.shape),
    'new_dtypes': df_engineered.dtypes.astype(str).to_dict(),
    'null_counts': df_engineered.isnull().sum().to_dict(),
}}
print(json.dumps(result, default=str))
"""


def feature_engineer_node(llm: LLMProvider, sandbox: ExecutionSandbox):
    """Factory: returns the feature engineering node function."""

    async def node(state: PipelineState) -> dict[str, Any]:
        logger.info("Starting feature engineering", pipeline_id=state["pipeline_id"])
        start = time.monotonic()

        state_updates: dict[str, Any] = {
            "current_phase": MLPhase.FEATURE_ENGINEERING.value,
        }

        profile = state.get("data_profile")
        if not profile:
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="feature_engineering",
                    error_type="MissingDependency",
                    error_message="Data profile not available",
                    recoverable=False,
                )
            ]
            return state_updates

        try:
            # 1. Generate feature engineering code via LLM
            # Include critic feedback if looping back
            critic_context = ""
            if state["critic_decisions"]:
                latest = state["critic_decisions"][-1]
                if latest["overall_assessment"] == "refine_features":
                    critic_context = (
                        f"\n\nPREVIOUS CRITIC FEEDBACK (iteration {latest['iteration']}):\n"
                        f"Concerns: {json.dumps(latest['concerns'])}\n"
                        f"Recommendations: {json.dumps(latest['recommendations'])}\n"
                        f"Address these issues in your feature engineering."
                    )

            agent_code = await llm.invoke(
                FEATURE_ENGINEERING_CODE.format(
                    objectives=state["user_objectives"] + critic_context,
                    profile_summary=profile["key_findings"],
                    dtypes=json.dumps(profile["dtypes"], indent=2),
                    shape=profile["shape"],
                ),
                system=SYSTEM_ML_ENGINEER,
                temperature=0.4,
            )

            # Clean markdown code blocks if present
            agent_code = _clean_code_block(agent_code)

            # 2. Execute in sandbox
            ds = state["data_source"]
            full_code = CODE_WRAPPER.format(
                format=ds["format"],
                location=ds["location"],
                agent_code=agent_code,
                working_dir=state["working_dir"],
            )

            result = await sandbox.execute(
                full_code,
                working_dir=state["working_dir"],
                timeout_sec=120,
            )

            if result.failed:
                logger.warning(
                    "Feature engineering code failed, requesting fix",
                    error=result.error_message,
                )
                # Retry once with error context
                fix_prompt = (
                    f"The following code failed:\n```python\n{agent_code}\n```\n"
                    f"Error: {result.stderr}\n\n"
                    f"Fix the code. Return ONLY the corrected Python code."
                )
                agent_code = await llm.invoke(fix_prompt, system=SYSTEM_ML_ENGINEER, temperature=0.3)
                agent_code = _clean_code_block(agent_code)

                full_code = CODE_WRAPPER.format(
                    format=ds["format"],
                    location=ds["location"],
                    agent_code=agent_code,
                    working_dir=state["working_dir"],
                )
                result = await sandbox.execute(full_code, working_dir=state["working_dir"], timeout_sec=120)

                if result.failed:
                    state_updates["errors"] = state["errors"] + [
                        PhaseError(
                            phase="feature_engineering",
                            error_type=result.error_type or "ExecutionError",
                            error_message=f"Code failed after retry: {result.error_message}",
                            recoverable=True,
                        )
                    ]
                    return state_updates

            # 3. Parse results
            fe_result = json.loads(result.stdout.strip().splitlines()[-1])

            # 4. Validate features via LLM
            validation_response = await llm.invoke_with_structured_output(
                FEATURE_VALIDATION.format(
                    objectives=state["user_objectives"],
                    original_columns=list(profile["dtypes"].keys()),
                    new_features=fe_result["new_columns"],
                    feature_code=agent_code,
                ),
                system=SYSTEM_ML_ENGINEER,
                response_schema={
                    "leakage_risks": ["string"],
                    "quality_issues": ["string"],
                    "recommendations": ["string"],
                    "approved": "boolean",
                },
                temperature=0.3,
            )

            # 5. Build output
            feature_artifacts = [
                {
                    "name": col,
                    "code_snippet": "",
                    "source_columns": [],
                    "dtype": fe_result.get("new_dtypes", {}).get(col, "unknown"),
                    "rationale": "",
                }
                for col in fe_result["new_columns"]
            ]

            fe_output = FeatureEngineering(
                features=feature_artifacts,
                code_executed=agent_code,
                new_columns=fe_result["new_columns"],
                dropped_columns=fe_result["dropped_columns"],
                new_shape=fe_result["new_shape"],
                validation_passed=validation_response.get("approved", False),
                validation_notes=json.dumps({
                    "leakage_risks": validation_response.get("leakage_risks", []),
                    "quality_issues": validation_response.get("quality_issues", []),
                    "recommendations": validation_response.get("recommendations", []),
                }),
            )

            elapsed = time.monotonic() - start
            state_updates["feature_engineering"] = fe_output
            state_updates["phase_timings"] = {
                **state["phase_timings"],
                "feature_engineering": round(elapsed, 2),
            }

            logger.info(
                "Feature engineering complete",
                pipeline_id=state["pipeline_id"],
                new_features=len(fe_result["new_columns"]),
                validation=validation_response.get("approved"),
                elapsed=f"{elapsed:.2f}s",
            )

        except Exception as e:
            logger.error("Feature engineering error", error=str(e))
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="feature_engineering",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    recoverable=True,
                )
            ]

        return state_updates

    return node


def _clean_code_block(code: str) -> str:
    """Strip markdown code fences from LLM output."""
    code = code.strip()
    if code.startswith("```python"):
        code = code[len("```python") :]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()

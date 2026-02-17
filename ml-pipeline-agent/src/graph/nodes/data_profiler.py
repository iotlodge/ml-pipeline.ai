"""Data Profiler Node — schema detection, distributions, correlations, quality assessment."""

from __future__ import annotations

import json
import time
from typing import Any

from src.llm.base import LLMProvider
from src.llm.prompts import DATA_PROFILE_ANALYSIS, SYSTEM_ML_ANALYST, SYSTEM_ML_ENGINEER
from src.sandbox.base import ExecutionSandbox
from src.state.schema import DataProfile, MLPhase, PhaseError, PipelineState
from src.utils.logging import get_logger

logger = get_logger(__name__)

PROFILE_CODE_TEMPLATE = """
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

# Load dataset
df = pd.read_{format}('{location}')

# Basic shape
shape = list(df.shape)
dtypes = df.dtypes.astype(str).to_dict()

# Missing values
missing_counts = df.isnull().sum().to_dict()
missing_pct = (df.isnull().sum() / len(df) * 100).round(2).to_dict()

# Numeric stats
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
numeric_stats = {{}}
if numeric_cols:
    desc = df[numeric_cols].describe().to_dict()
    numeric_stats = {{col: {{k: round(float(v), 4) for k, v in stats.items()}}
                     for col, stats in desc.items()}}

# Categorical stats (top 20 values per column)
cat_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
categorical_stats = {{}}
for col in cat_cols:
    vc = df[col].value_counts().head(20).to_dict()
    categorical_stats[col] = {{str(k): int(v) for k, v in vc.items()}}

# Top correlations
correlation_top = []
if len(numeric_cols) > 1:
    corr = df[numeric_cols].corr()
    # Get upper triangle pairs sorted by absolute correlation
    pairs = []
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            pairs.append({{
                'col_a': corr.columns[i],
                'col_b': corr.columns[j],
                'correlation': round(float(corr.iloc[i, j]), 4)
            }})
    correlation_top = sorted(pairs, key=lambda x: abs(x['correlation']), reverse=True)[:15]

# Infer target column heuristic
# Look for common target names
target_candidates = ['target', 'label', 'class', 'y', 'outcome', 'is_', 'has_']
target_column = None
for col in df.columns:
    col_lower = col.lower()
    if any(col_lower == tc or col_lower.startswith(tc) for tc in target_candidates):
        target_column = col
        break
# If still None, use last column as default heuristic
if target_column is None:
    target_column = df.columns[-1]

# Infer task type
task_type = 'unknown'
if target_column in df.columns:
    target_dtype = str(df[target_column].dtype)
    n_unique = df[target_column].nunique()
    if target_dtype in ['object', 'bool', 'category'] or n_unique <= 20:
        task_type = 'classification'
    else:
        task_type = 'regression'

result = {{
    'shape': shape,
    'dtypes': dtypes,
    'missing_counts': missing_counts,
    'missing_pct': missing_pct,
    'numeric_stats': numeric_stats,
    'categorical_stats': categorical_stats,
    'correlation_top': correlation_top,
    'target_column': target_column,
    'task_type': task_type,
}}

print(json.dumps(result, default=str))
"""


def data_profiler_node(llm: LLMProvider, sandbox: ExecutionSandbox):
    """Factory: returns the data profiler node function."""

    async def node(state: PipelineState) -> dict[str, Any]:
        logger.info("Starting data profiling", pipeline_id=state["pipeline_id"])
        start = time.monotonic()

        state_updates: dict[str, Any] = {
            "current_phase": MLPhase.DATA_PROFILING.value,
        }

        try:
            # 1. Execute profiling code in sandbox
            ds = state["data_source"]
            code = PROFILE_CODE_TEMPLATE.format(
                format=ds["format"],
                location=ds["location"],
            )

            result = await sandbox.execute(
                code,
                working_dir=state["working_dir"],
                timeout_sec=120,
            )

            if result.failed:
                logger.error("Profiling execution failed", error=result.error_message)
                state_updates["errors"] = state["errors"] + [
                    PhaseError(
                        phase="data_profiling",
                        error_type=result.error_type or "ExecutionError",
                        error_message=result.error_message or "Unknown error",
                        recoverable=False,
                    )
                ]
                return state_updates

            # 2. Parse profiling output
            profile_data = json.loads(result.stdout.strip().splitlines()[-1])

            # 3. LLM analysis of profile
            key_findings = await llm.invoke(
                DATA_PROFILE_ANALYSIS.format(
                    objectives=state["user_objectives"],
                    shape=profile_data["shape"],
                    dtypes=json.dumps(profile_data["dtypes"], indent=2),
                    missing_counts=json.dumps(profile_data["missing_counts"], indent=2),
                    numeric_stats=json.dumps(
                        {k: {sk: sv for sk, sv in v.items() if sk in ("mean", "std", "min", "max")}
                         for k, v in profile_data["numeric_stats"].items()},
                        indent=2,
                    ),
                    categorical_stats=json.dumps(
                        {k: dict(list(v.items())[:5]) for k, v in profile_data["categorical_stats"].items()},
                        indent=2,
                    ),
                ),
                system=SYSTEM_ML_ANALYST,
                temperature=0.5,
            )

            # 4. Build DataProfile
            data_profile = DataProfile(
                shape=profile_data["shape"],
                dtypes=profile_data["dtypes"],
                missing_counts=profile_data["missing_counts"],
                missing_pct=profile_data["missing_pct"],
                numeric_stats=profile_data["numeric_stats"],
                categorical_stats=profile_data["categorical_stats"],
                correlation_top=profile_data["correlation_top"],
                key_findings=key_findings,
                target_column=profile_data["target_column"],
                task_type=profile_data["task_type"],
            )

            elapsed = time.monotonic() - start
            state_updates["data_profile"] = data_profile
            state_updates["phase_timings"] = {**state["phase_timings"], "data_profiling": round(elapsed, 2)}

            logger.info(
                "Data profiling complete",
                pipeline_id=state["pipeline_id"],
                shape=profile_data["shape"],
                task_type=profile_data["task_type"],
                elapsed=f"{elapsed:.2f}s",
            )

        except Exception as e:
            logger.error("Data profiling error", error=str(e), pipeline_id=state["pipeline_id"])
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="data_profiling",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    recoverable=False,
                )
            ]

        return state_updates

    return node

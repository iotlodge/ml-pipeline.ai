"""Visualizer Node — generates EDA plots, interprets patterns via LLM."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from src.llm.base import LLMProvider
from src.llm.prompts import (
    SYSTEM_ML_ANALYST,
    SYSTEM_ML_ENGINEER,
    VISUALIZATION_CODE,
    VISUALIZATION_INTERPRETATION,
)
from src.sandbox.base import ExecutionSandbox
from src.state.schema import (
    MLPhase,
    PhaseError,
    PipelineState,
    PlotArtifact,
    VisualizationOutput,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

VIZ_WRAPPER = """
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import json
import os
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# NEURAL OBSERVATORY THEME — dark-friendly, seaborn-powered
# ============================================================
# Dark slate background with vibrant accent palette.
# Transparent figure facecolor so it composites on any UI bg.

_BG = '#1a1b2e'
_FG = '#e0e1f0'
_GRID = '#2a2b44'
_ACCENT_PALETTE = ['#7c3aed', '#06b6d4', '#f59e0b', '#ef4444', '#10b981', '#ec4899', '#3b82f6', '#8b5cf6']

sns.set_theme(
    style='darkgrid',
    context='notebook',
    palette=_ACCENT_PALETTE,
    rc={{
        'figure.facecolor': _BG,
        'axes.facecolor': '#12132a',
        'axes.edgecolor': _GRID,
        'axes.labelcolor': _FG,
        'axes.grid': True,
        'grid.color': _GRID,
        'grid.alpha': 0.4,
        'text.color': _FG,
        'xtick.color': _FG,
        'ytick.color': _FG,
        'legend.facecolor': _BG,
        'legend.edgecolor': _GRID,
        'legend.labelcolor': _FG,
        'figure.edgecolor': 'none',
        'savefig.facecolor': _BG,
        'savefig.edgecolor': 'none',
        'font.family': 'sans-serif',
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.titleweight': 'bold',
    }},
)

# ============================================================
# DATA AND PLOT DIR ARE ALREADY SET UP — DO NOT RE-LOAD
# `df` is your DataFrame. `plot_dir` is where to save plots.
# ============================================================

# Load engineered dataset if available, else raw
engineered_path = '{working_dir}/df_engineered.csv'
if os.path.exists(engineered_path):
    df = pd.read_csv(engineered_path)
else:
    df = pd.read_{format}('{location}')

plot_dir = '{working_dir}/plots'
os.makedirs(plot_dir, exist_ok=True)

print(f"Data loaded: {{df.shape}}, saving plots to: {{plot_dir}}")

# ---- Agent-generated code starts ----
# REMINDER: `df` is already loaded. `plot_dir` is already set.
# Save plots with: plt.savefig(f'{{plot_dir}}/plot_name.png', dpi=150, bbox_inches='tight')
# Call plt.close('all') after each save. Do NOT use plt.show().
{agent_code}
# ---- Agent-generated code ends ----

# Discover saved plots
import glob
plot_files = sorted(glob.glob(f'{{plot_dir}}/*.png'))
if not plot_files:
    plot_files = sorted(glob.glob('{working_dir}/*.png'))

print(json.dumps({{'plot_files': plot_files, 'plot_count': len(plot_files)}}))
"""


def visualizer_node(llm: LLMProvider, sandbox: ExecutionSandbox):
    """Factory: returns the visualization node function."""

    async def node(state: PipelineState) -> dict[str, Any]:
        logger.info("Starting visualization", pipeline_id=state["pipeline_id"])
        start = time.monotonic()

        state_updates: dict[str, Any] = {
            "current_phase": MLPhase.VISUALIZATION.value,
        }

        profile = state.get("data_profile")
        if not profile:
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="visualization",
                    error_type="MissingDependency",
                    error_message="Data profile not available",
                    recoverable=False,
                )
            ]
            return state_updates

        try:
            # 1. Generate visualization code via LLM
            agent_code = await llm.invoke(
                VISUALIZATION_CODE.format(
                    objectives=state["user_objectives"],
                    profile_summary=profile["key_findings"],
                    dtypes=json.dumps(profile["dtypes"], indent=2),
                    shape=profile["shape"],
                    key_findings=profile["key_findings"],
                ),
                system=SYSTEM_ML_ENGINEER,
                temperature=0.5,
            )
            agent_code = _clean_code_block(agent_code)
            agent_code = _sanitize_viz_code(agent_code)

            # Pre-flight syntax check — if invalid, use fallback before wasting sandbox time
            if not _check_syntax(agent_code):
                logger.warning("LLM viz code has syntax errors, using fallback template")
                agent_code = _build_fallback_viz_code(profile, profile.get("target_column"))

            # 2. Execute in sandbox
            ds = state["data_source"]
            full_code = VIZ_WRAPPER.format(
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
                logger.warning("Visualization code failed, trying fallback template", error=result.error_message)
                # Instead of asking LLM to fix (which may produce same syntax issues),
                # use deterministic fallback template
                agent_code = _build_fallback_viz_code(profile, profile.get("target_column"))

                full_code = VIZ_WRAPPER.format(
                    format=ds["format"],
                    location=ds["location"],
                    agent_code=agent_code,
                    working_dir=state["working_dir"],
                )
                result = await sandbox.execute(full_code, working_dir=state["working_dir"], timeout_sec=120)

                if result.failed:
                    logger.warning("Visualization failed after retry", error=result.error_message)
                    state_updates["errors"] = state["errors"] + [
                        PhaseError(
                            phase="visualization",
                            error_type=result.error_type or "ExecutionError",
                            error_message=result.error_message or "Unknown",
                            recoverable=True,
                        )
                    ]
                    # Continue pipeline — visualizations are helpful but not blocking
                    state_updates["visualizations"] = VisualizationOutput(
                        plots=[],
                        key_insights="Visualization generation failed; proceeding without.",
                        feature_suggestions=[],
                        modeling_concerns=[],
                    )
                    return state_updates

            # 3. Parse results
            stdout_lines = result.stdout.strip().splitlines()
            viz_result = {}
            for line in reversed(stdout_lines):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        viz_result = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

            plot_files = viz_result.get("plot_files", [])

            # 4. Build plot descriptions from stdout (before JSON line)
            desc_lines = [l for l in stdout_lines if not l.strip().startswith("{")]
            plot_descriptions = "\n".join(desc_lines) if desc_lines else "Plots generated."

            # 5. LLM interpretation (analysis, not code generation)
            interpretation = await llm.invoke(
                VISUALIZATION_INTERPRETATION.format(
                    objectives=state["user_objectives"],
                    plot_descriptions=plot_descriptions,
                ),
                system=SYSTEM_ML_ANALYST,
                temperature=0.5,
            )

            # 6. Build output
            plots = [
                PlotArtifact(
                    title=Path(f).stem,
                    plot_type="auto",
                    file_path=f,
                    description="",
                    interpretation="",
                )
                for f in plot_files
            ]

            viz_output = VisualizationOutput(
                plots=plots,
                key_insights=interpretation,
                feature_suggestions=[],
                modeling_concerns=[],
            )

            elapsed = time.monotonic() - start
            state_updates["visualizations"] = viz_output
            state_updates["phase_timings"] = {
                **state["phase_timings"],
                "visualization": round(elapsed, 2),
            }

            logger.info(
                "Visualization complete",
                pipeline_id=state["pipeline_id"],
                plots_generated=len(plots),
                elapsed=f"{elapsed:.2f}s",
            )

        except Exception as e:
            logger.error("Visualization error", error=str(e))
            state_updates["errors"] = state["errors"] + [
                PhaseError(
                    phase="visualization",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    recoverable=True,
                )
            ]
            # Non-blocking: provide empty viz so pipeline continues
            if "visualizations" not in state_updates:
                state_updates["visualizations"] = VisualizationOutput(
                    plots=[],
                    key_insights="Visualization generation failed; proceeding without.",
                    feature_suggestions=[],
                    modeling_concerns=[],
                )

        return state_updates

    return node


def _sanitize_viz_code(code: str) -> str:
    """Remove patterns the LLM might generate that conflict with the wrapper."""
    lines = code.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Remove any pd.read_csv / pd.read_* calls (wrapper already loads data)
        if re.match(r'.*pd\.read_(csv|parquet|json|excel|feather)\s*\(', stripped):
            cleaned.append(f"# REMOVED (data already loaded): {stripped}")
            continue
        # Remove plt.show() calls
        if re.match(r'.*plt\.show\s*\(', stripped):
            cleaned.append(f"# REMOVED (no display): {stripped}")
            continue
        # Remove os.makedirs (wrapper handles it)
        if re.match(r'.*os\.makedirs\s*\(', stripped):
            cleaned.append(f"# REMOVED (dirs already created): {stripped}")
            continue
        # Remove theme overrides (wrapper already sets Neural Observatory theme)
        if re.match(r'.*sns\.set_theme\s*\(', stripped) or re.match(r'.*sns\.set_style\s*\(', stripped):
            cleaned.append(f"# REMOVED (theme already set): {stripped}")
            continue
        if re.match(r'.*plt\.style\.use\s*\(', stripped):
            cleaned.append(f"# REMOVED (theme already set): {stripped}")
            continue
        if re.match(r'.*\.set_facecolor\s*\(', stripped):
            cleaned.append(f"# REMOVED (theme handles colors): {stripped}")
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _check_syntax(code: str) -> bool:
    """Check if code has valid Python syntax."""
    import ast
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _build_fallback_viz_code(profile: dict, target_column: str | None) -> str:
    """Generate deterministic EDA visualization code — seaborn dark theme."""
    target = target_column or "target"
    return f"""
# Fallback template-based visualization — seaborn dark theme
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:8]
cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()[:4]

# Plot 1: Target distribution
fig, ax = plt.subplots(figsize=(9, 6))
if '{target}' in df.columns:
    if df['{target}'].nunique() <= 20:
        sns.countplot(data=df, x='{target}', ax=ax, alpha=0.85, order=df['{target}'].value_counts().index[:15])
    else:
        sns.histplot(data=df, x='{target}', ax=ax, bins=30, alpha=0.8)
    ax.set_title('Target Distribution')
    ax.set_xlabel('{target}')
    ax.set_ylabel('Count')
plt.tight_layout()
plt.savefig(f'{{plot_dir}}/plot_01_target_dist.png', dpi=150, bbox_inches='tight')
plt.close('all')
print('Plot 1: Target variable distribution')

# Plot 2: Correlation heatmap
if len(numeric_cols) > 1:
    fig, ax = plt.subplots(figsize=(10, 8))
    corr = df[numeric_cols].corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r', ax=ax, vmin=-1, vmax=1, linewidths=0.5, annot_kws={{'size': 9}})
    ax.set_title('Feature Correlation Matrix')
    plt.tight_layout()
    plt.savefig(f'{{plot_dir}}/plot_02_correlation.png', dpi=150, bbox_inches='tight')
    plt.close('all')
    print('Plot 2: Correlation heatmap of numeric features')

# Plot 3: Numeric feature distributions
if numeric_cols:
    n_cols = min(len(numeric_cols), 6)
    n_rows = (n_cols + 2) // 3
    fig, axes = plt.subplots(n_rows, 3, figsize=(14, 4 * n_rows))
    axes = np.atleast_2d(axes).flatten()
    for i in range(n_cols):
        sns.histplot(data=df, x=numeric_cols[i], ax=axes[i], kde=True, alpha=0.7, bins=30)
        axes[i].set_title(numeric_cols[i])
    for i in range(n_cols, len(axes)):
        axes[i].set_visible(False)
    fig.suptitle('Numeric Feature Distributions', y=1.02)
    plt.tight_layout()
    plt.savefig(f'{{plot_dir}}/plot_03_distributions.png', dpi=150, bbox_inches='tight')
    plt.close('all')
    print('Plot 3: Distribution of numeric features')

# Plot 4: Top features vs target (violin/scatter)
if numeric_cols and '{target}' in df.columns and df['{target}'].nunique() <= 10:
    top_feats = numeric_cols[:3]
    fig, axes = plt.subplots(1, len(top_feats), figsize=(5 * len(top_feats), 6))
    if len(top_feats) == 1:
        axes = [axes]
    for ax, feat in zip(axes, top_feats):
        sns.violinplot(data=df, x='{target}', y=feat, ax=ax, inner='quartile', alpha=0.8)
        ax.set_title(f'{{feat}} by {target}')
    plt.tight_layout()
    plt.savefig(f'{{plot_dir}}/plot_04_feature_vs_target.png', dpi=150, bbox_inches='tight')
    plt.close('all')
    print('Plot 4: Top features vs target (violin)')
elif numeric_cols and len(numeric_cols) >= 2:
    fig, ax = plt.subplots(figsize=(9, 6))
    if '{target}' in df.columns and df['{target}'].nunique() <= 10:
        sns.scatterplot(data=df, x=numeric_cols[0], y=numeric_cols[1], hue='{target}', ax=ax, alpha=0.6, s=40)
    else:
        sns.scatterplot(data=df, x=numeric_cols[0], y=numeric_cols[1], ax=ax, alpha=0.5, s=30)
    ax.set_title(f'{{numeric_cols[0]}} vs {{numeric_cols[1]}}')
    plt.tight_layout()
    plt.savefig(f'{{plot_dir}}/plot_04_feature_scatter.png', dpi=150, bbox_inches='tight')
    plt.close('all')
    print('Plot 4: Feature scatter plot')
"""


def _clean_code_block(code: str) -> str:
    code = code.strip()
    if code.startswith("```python"):
        code = code[len("```python"):]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()

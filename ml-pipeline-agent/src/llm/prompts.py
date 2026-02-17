"""Prompt templates for each pipeline phase — separated from node logic."""

from __future__ import annotations

# ── System Prompts ────────────────────────────────────────────────────────────

SYSTEM_ML_ENGINEER = (
    "You are an expert ML engineer. You write clean, production-grade Python code "
    "using pandas, scikit-learn, xgboost, and lightgbm. You reason carefully about "
    "data quality, feature leakage, and model selection. You prefer simple, "
    "interpretable solutions unless complexity is justified by the data.\n\n"
    "CRITICAL RULES:\n"
    "- Return ONLY executable Python code — no markdown, no explanations, no ```python fences\n"
    "- NEVER import data or load files — data is ALREADY loaded into variables for you\n"
    "- NEVER create directories or manage file paths — the environment handles this\n"
    "- Use ONLY the pre-loaded variables described in the prompt\n"
    "- Keep ALL string literals on a SINGLE LINE — never break a string across lines\n"
    "- For long titles/labels, use short text — do NOT wrap strings across multiple lines\n"
    "- Use simple concatenation ('a' + 'b') if needed, never backslash continuation in strings"
)

SYSTEM_ML_ANALYST = (
    "You are an expert ML engineer and data scientist. You analyze data profiles, "
    "model results, and pipeline outputs. You provide clear, specific, actionable "
    "analysis in plain text. You are direct and avoid generic advice.\n\n"
    "CRITICAL RULES:\n"
    "- Return ONLY plain text analysis — never return code\n"
    "- Do NOT wrap your response in markdown code blocks\n"
    "- Be specific to the data provided — no generic advice"
)

SYSTEM_CRITIC = (
    "You are a senior ML reviewer. You evaluate ML pipeline decisions for correctness, "
    "methodology soundness, potential data leakage, overfitting risk, and alignment "
    "with the stated objectives. You are direct and specific in your feedback."
)

# ── Data Profiling ────────────────────────────────────────────────────────────

DATA_PROFILE_ANALYSIS = """Analyze this dataset profile and provide key findings.

**User Objective**: {objectives}

**Dataset Shape**: {shape}
**Column Types**: {dtypes}
**Missing Values**: {missing_counts}
**Numeric Summary**: {numeric_stats}
**Categorical Summary**: {categorical_stats}

Provide a concise analysis covering:
1. Data quality issues (nulls, anomalies, potential errors)
2. Feature candidates for the stated objective
3. Potential data leakage risks
4. Recommended preprocessing steps

Be specific to this dataset — no generic advice."""

# ── Feature Engineering ───────────────────────────────────────────────────────

FEATURE_ENGINEERING_CODE = """Generate Python code to engineer features for this ML task.

**User Objective**: {objectives}
**Data Profile Summary**: {profile_summary}
**Column Names & Types**: {dtypes}
**Current Shape**: {shape}

ALREADY AVAILABLE (do NOT re-create or re-load):
- `df` — the full DataFrame is already loaded in memory

Requirements:
- Use pandas DataFrame operations on the existing `df` variable
- Create meaningful derived features aligned with the objective
- Handle missing values appropriately
- Encode categoricals if needed (label encoding or one-hot)
- Do NOT include model training — only feature engineering
- Store the final engineered DataFrame as `df_engineered`
- Print the new column names and shape at the end

FORBIDDEN:
- Do NOT use pd.read_csv() or any file loading — df is already loaded
- Do NOT import os, pathlib, or do any file system operations
- Do NOT create directories

Return ONLY executable Python code, no explanations, no markdown fences."""

FEATURE_VALIDATION = """Review these engineered features for quality and leakage risk.

**User Objective**: {objectives}
**Original Columns**: {original_columns}
**New Features Created**: {new_features}
**Feature Code**:
```python
{feature_code}
```

Check for:
1. Target leakage — does any feature use information from the target?
2. Data leakage — does any feature use future information?
3. Redundant features — high correlation with existing columns?
4. Quality — are there NaN-generating operations?

Respond with JSON:
{{
    "leakage_risks": ["list of concerns or empty"],
    "quality_issues": ["list of issues or empty"],
    "recommendations": ["list of improvements"],
    "approved": true/false
}}"""

# ── Visualization ─────────────────────────────────────────────────────────────

VISUALIZATION_CODE = """Generate Python visualization code for exploratory data analysis.

**User Objective**: {objectives}
**Data Profile Summary**: {profile_summary}
**Column Names & Types**: {dtypes}
**Shape**: {shape}
**Key Findings from Profiling**: {key_findings}

ALREADY AVAILABLE (do NOT re-create or re-load):
- `df` — the full DataFrame is already loaded
- `plot_dir` — string path to save plots (already created)
- `matplotlib`, `seaborn`, `numpy`, `pandas` — already imported
- `plt` is matplotlib.pyplot, `sns` is seaborn
- A dark theme is already configured (dark slate background, light text, vibrant accent palette)
- `_ACCENT_PALETTE` list of 8 colors is available for custom use

STYLE REQUIREMENTS — USE SEABORN for all plots:
- Prefer sns.histplot, sns.kdeplot, sns.boxplot, sns.violinplot, sns.heatmap, sns.countplot, sns.scatterplot, sns.barplot
- Do NOT override the theme — no plt.style.use(), no sns.set_theme(), no manual facecolor/text color
- The theme handles all colors automatically; just create clean, readable charts
- Use figsize=(9, 6) for standard plots, (10, 8) for heatmaps
- Use alpha=0.8 for filled plots to keep them polished

Requirements:
- Create 3-5 informative plots targeting the objective
- Save each plot: plt.savefig(f'{{plot_dir}}/plot_01_name.png', dpi=150, bbox_inches='tight')
- Call plt.close('all') after each save
- Print a one-line description of each plot
- Keep all string literals (titles, labels) on a SINGLE LINE — no line breaks inside strings

FORBIDDEN:
- Do NOT use pd.read_csv() or any file loading
- Do NOT import os or create directories
- Do NOT use multi-line f-strings or string literals
- Do NOT use plt.show()
- Do NOT call sns.set_theme() or plt.style.use() — theme is already set
- Do NOT set fig.patch.set_facecolor() or ax.set_facecolor() — theme handles this

Return ONLY executable Python code, no markdown fences."""

VISUALIZATION_INTERPRETATION = """Interpret these EDA visualizations for the ML pipeline.

**User Objective**: {objectives}
**Plots Generated**:
{plot_descriptions}

Based on the visualizations, provide:
1. Key patterns discovered
2. Feature engineering suggestions from visual patterns
3. Potential modeling challenges (class imbalance, non-linearity, etc.)
4. Recommended model families based on data characteristics

Be specific and actionable."""

# ── Model Training ────────────────────────────────────────────────────────────

MODEL_SELECTION_CODE = """Generate Python code to train and evaluate ML models.

**User Objective**: {objectives}
**Task Type**: {task_type}
**Target Column**: {target_column}
**Feature Columns**: {feature_columns}
**Shape**: {shape}
**Key Insights**: {key_insights}

ALREADY AVAILABLE (do NOT re-create or re-load):
- `X_train`, `X_test` — feature DataFrames (already split, already numeric-encoded)
- `y_train`, `y_test` — target Series (already split)
- `pd`, `np`, `json`, `joblib` — already imported
- `sklearn`, `cross_val_score`, `train_test_split` — already imported
- Working directory for saving: use `best_model.joblib` (relative path, current dir is correct)

Requirements:
- Train at least 3 model candidates with reasonable default hyperparameters
- Use 5-fold cross-validation on the training set
- For classification: compute accuracy, f1_macro, precision, recall
- For regression: compute RMSE, MAE, R2
- Pick the best model by cross-validation score
- Run Optuna for hyperparameter tuning on the best candidate (15 trials max)
- Save the final best model: joblib.dump(best_model, 'best_model.joblib')
- Print a SINGLE JSON line at the end with this EXACT structure:
  {{"best_model": "ModelName", "candidates": [{{"name": "ModelName", "accuracy": 0.85, "precision": 0.82, "recall": 0.80, "f1": 0.81, "cv_mean": 0.83, "cv_std": 0.02, "train_score": 0.88}}], "best_hyperparams": {{}}, "feature_importance": {{}}, "train_score": 0.0, "test_score": 0.0}}
- Each candidate in "candidates" MUST include: name, accuracy, precision, recall, f1, cv_mean, cv_std, train_score
- For regression candidates: use r2 for accuracy, and set precision/recall/f1 to null

FORBIDDEN:
- Do NOT use pd.read_csv() or load any files — data is already in memory
- Do NOT do train_test_split — already done for you
- Do NOT import os, pathlib, or manage directories
- Do NOT create new directories
- Do NOT use multi-line strings

Return ONLY executable Python code, no markdown fences."""

# ── Evaluation ────────────────────────────────────────────────────────────────

EVALUATION_CODE = """Generate Python code for thorough model evaluation.

**User Objective**: {objectives}
**Task Type**: {task_type}
**Best Model**: {best_model_name}
**Training Metrics**: {training_metrics}

ALREADY AVAILABLE (do NOT re-create or re-load):
- `best_model` — the trained model, already loaded via joblib
- `X_test`, `y_test` — test data, already loaded as DataFrames
- `X_train`, `y_train` — training data, already loaded
- `pd`, `np`, `json`, `plt`, `matplotlib` — already imported
- `eval_dir` — string path for saving evaluation plots (already created)
- `working_dir` — string path to working directory

Requirements:
- Generate classification report or regression metrics
- Create confusion matrix plot (classification) or residual plot (regression)
- Save plots to: plt.savefig(f'{{eval_dir}}/eval_plot_name.png', dpi=100, bbox_inches='tight')
- Call plt.close('all') after each plot
- Compute train vs test score gap for overfitting check
- Print a SINGLE JSON line at the end:
  {{"cv_scores": [...], "cv_mean": 0.0, "cv_std": 0.0, "test_metrics": {{}}, "train_score": 0.0, "test_score": 0.0, "plot_paths": [...]}}

FORBIDDEN:
- Do NOT use joblib.load() — model is already loaded as `best_model`
- Do NOT use pd.read_csv() — data is already in memory
- Do NOT import os or manage directories
- Do NOT use plt.show()

Return ONLY executable Python code, no markdown fences."""

# ── Critic Review ─────────────────────────────────────────────────────────────

CRITIC_REVIEW = """Review the complete ML pipeline and decide whether to finalize or loop back.

**User Objective**: {objectives}

**Pipeline Summary**:
- Data Profile: {profile_summary}
- Features Engineered: {features_summary}
- Visualization Insights: {viz_insights}
- Model Trained: {model_summary}
- Evaluation Metrics: {eval_metrics}
- Errors Encountered: {errors}

**Loop History**: Iteration {loop_count}/{max_loops}
**Previous Critic Decisions**: {previous_decisions}

Evaluate:
1. Does the model adequately address the user's objective?
2. Are there signs of overfitting or data leakage?
3. Were feature engineering choices sound?
4. Is model performance acceptable, or could we do better?
5. Were there errors that need correction?

Respond with JSON:
{{
    "overall_assessment": "finalize" | "refine_features" | "retrain_model",
    "confidence": 0.0-1.0,
    "concerns": ["specific concern 1", "..."],
    "recommendations": ["specific action 1", "..."],
    "reasoning": "2-3 sentence explanation"
}}"""

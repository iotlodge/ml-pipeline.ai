"""AST-based code validation — reject dangerous patterns before execution."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool
    error: str | None = None
    warnings: list[str] | None = None


# Forbidden function calls
FORBIDDEN_CALLS = frozenset({
    "exec",
    "eval",
    "compile",
    "__import__",
    "breakpoint",
    "input",
})

# Forbidden module-level attribute access
FORBIDDEN_ATTRIBUTES = frozenset({
    "system",    # os.system
    "popen",     # os.popen
    "spawn",     # os.spawn*
    "execv",     # os.execv*
    "kill",      # os.kill
    "remove",    # os.remove (controlled via working_dir instead)
    "rmdir",     # os.rmdir
    "rmtree",    # shutil.rmtree
})

# Forbidden imports
FORBIDDEN_IMPORTS = frozenset({
    "subprocess",
    "shutil",
    "socket",
    "http",
    "urllib",
    "requests",
    "httpx",
    "ftplib",
    "smtplib",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
})

# Allowed imports (whitelist for ML work)
ALLOWED_IMPORTS = frozenset({
    "pandas",
    "numpy",
    "sklearn",
    "scikit-learn",
    "xgboost",
    "lightgbm",
    "optuna",
    "matplotlib",
    "seaborn",
    "scipy",
    "joblib",
    "json",
    "math",
    "statistics",
    "collections",
    "itertools",
    "functools",
    "datetime",
    "pathlib",
    "os",  # Allowed but with attribute restrictions
    "warnings",
    "typing",
    "dataclasses",
    "re",
    "io",
    "csv",
    "pickle",
})


def validate_code(code: str) -> ValidationResult:
    """Validate Python code via AST analysis.

    Returns ValidationResult with valid=True if safe to execute.
    """
    # 1. Parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(valid=False, error=f"SyntaxError: {e}")

    warnings: list[str] = []

    for node in ast.walk(tree):
        # 2. Check forbidden function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                return ValidationResult(
                    valid=False,
                    error=f"Forbidden function call: {node.func.id}()",
                )

        # 3. Check forbidden attribute access
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            return ValidationResult(
                valid=False,
                error=f"Forbidden attribute access: .{node.attr}",
            )

        # 4. Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in FORBIDDEN_IMPORTS:
                    return ValidationResult(
                        valid=False,
                        error=f"Forbidden import: {alias.name}",
                    )
                if root_module not in ALLOWED_IMPORTS:
                    warnings.append(f"Unrecognized import: {alias.name}")

        if isinstance(node, ast.ImportFrom) and node.module:
            root_module = node.module.split(".")[0]
            if root_module in FORBIDDEN_IMPORTS:
                return ValidationResult(
                    valid=False,
                    error=f"Forbidden import: {node.module}",
                )
            if root_module not in ALLOWED_IMPORTS:
                warnings.append(f"Unrecognized import: {node.module}")

        # 5. Check for dunder attribute access (except __name__, __init__)
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            safe_dunders = {"__name__", "__init__", "__class__", "__dict__", "__len__"}
            if node.attr not in safe_dunders:
                return ValidationResult(
                    valid=False,
                    error=f"Forbidden dunder access: .{node.attr}",
                )

    return ValidationResult(valid=True, warnings=warnings if warnings else None)

"""Sandbox protocol and execution result container."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable container for code execution results."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    output: Any = None  # Parsed return value if requested
    execution_time_sec: float = 0.0
    error_type: str | None = None
    error_message: str | None = None

    @property
    def failed(self) -> bool:
        return not self.success

    def summary(self) -> str:
        """One-line summary for logging."""
        status = "OK" if self.success else f"FAIL ({self.error_type})"
        return f"[{status}] {self.execution_time_sec:.2f}s | stdout={len(self.stdout)} chars"


@runtime_checkable
class ExecutionSandbox(Protocol):
    """Protocol for code execution environments.

    Implementations:
    - SubprocessSandbox: Fork a restricted Python subprocess (current)
    - DockerSandbox: Spin up isolated container per execution (future)
    - E2BSandbox: Cloud-hosted sandbox via E2B API (future)
    """

    async def execute(
        self,
        code: str,
        *,
        working_dir: str | None = None,
        timeout_sec: int = 60,
        env_vars: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute Python code in an isolated environment.

        Args:
            code: Python code string to execute.
            working_dir: Directory for file I/O within the sandbox.
            timeout_sec: Maximum execution time before kill.
            env_vars: Additional environment variables for the execution.

        Returns:
            ExecutionResult with stdout, stderr, and parsed output.
        """
        ...

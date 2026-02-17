"""Custom exception hierarchy for the ML pipeline."""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    def __init__(self, message: str, phase: str | None = None) -> None:
        self.phase = phase
        super().__init__(message)


class SandboxExecutionError(PipelineError):
    """Code execution failed in sandbox."""

    def __init__(self, message: str, code: str, stderr: str = "") -> None:
        self.code = code
        self.stderr = stderr
        super().__init__(message, phase="sandbox_execution")


class SandboxValidationError(PipelineError):
    """Code failed AST validation (forbidden patterns detected)."""

    def __init__(self, message: str, code: str) -> None:
        self.code = code
        super().__init__(message, phase="sandbox_validation")


class LLMProviderError(PipelineError):
    """LLM API call failed."""

    def __init__(self, message: str, provider: str) -> None:
        self.provider = provider
        super().__init__(message, phase="llm_invocation")


class DataLoadError(PipelineError):
    """Failed to load or parse input dataset."""

    def __init__(self, message: str, source: str) -> None:
        self.source = source
        super().__init__(message, phase="data_loading")


class MaxLoopsExceededError(PipelineError):
    """Critic review loop limit reached."""

    def __init__(self, loop_count: int, max_loops: int) -> None:
        self.loop_count = loop_count
        self.max_loops = max_loops
        super().__init__(
            f"Critic loop limit reached: {loop_count}/{max_loops}",
            phase="critic_review",
        )

"""LLM provider protocol — duck-typed interface for swappable providers."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


# ── Token usage tracking ─────────────────────────────────────────────────────


@dataclass
class TokenUsageSnapshot:
    """Immutable snapshot of token usage at a point in time."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0


@dataclass
class TokenAccumulator:
    """Thread-safe accumulator for LLM token usage across an entire pipeline run.

    Providers call ``record()`` after every API call.
    The executor reads ``snapshot()`` on each status poll.
    """
    _input_tokens: int = field(default=0, repr=False)
    _output_tokens: int = field(default=0, repr=False)
    _llm_calls: int = field(default=0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from a single LLM call (thread-safe)."""
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._llm_calls += 1

    def snapshot(self) -> TokenUsageSnapshot:
        """Return a consistent snapshot of accumulated usage."""
        with self._lock:
            return TokenUsageSnapshot(
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                total_tokens=self._input_tokens + self._output_tokens,
                llm_calls=self._llm_calls,
            )


# ── LLM Provider protocol ───────────────────────────────────────────────────


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers. Implement invoke() and astream() to plug in any model."""

    @property
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @property
    def token_usage(self) -> TokenAccumulator:
        """Return the token accumulator for this provider instance."""
        ...

    async def invoke(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Execute a single LLM call. Returns the text response."""
        ...

    async def invoke_with_structured_output(
        self,
        prompt: str,
        *,
        system: str = "",
        response_schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """LLM call expecting JSON conforming to response_schema."""
        ...

    async def astream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream LLM response token by token."""
        ...

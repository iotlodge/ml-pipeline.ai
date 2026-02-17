"""FastAPI dependency injection — provides configured instances to route handlers."""

from __future__ import annotations

from functools import lru_cache

from src.config.llm_providers import get_llm_provider
from src.config.settings import settings
from src.llm.base import LLMProvider
from src.pipeline.executor import PipelineExecutor
from src.sandbox.base import ExecutionSandbox
from src.sandbox.subprocess_sandbox import SubprocessSandbox


@lru_cache(maxsize=1)
def get_sandbox() -> ExecutionSandbox:
    """Singleton sandbox instance."""
    return SubprocessSandbox()


@lru_cache(maxsize=1)
def get_default_llm() -> LLMProvider:
    """Singleton default LLM provider."""
    return get_llm_provider(settings.LLM_PROVIDER)


@lru_cache(maxsize=1)
def get_executor() -> PipelineExecutor:
    """Singleton pipeline executor."""
    return PipelineExecutor(
        llm_provider=get_default_llm(),
        sandbox=get_sandbox(),
    )

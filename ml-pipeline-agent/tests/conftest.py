"""Shared pytest fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

import pytest


# ── Mock LLM Provider ─────────────────────────────────────────────────────────


class MockLLMProvider:
    """Deterministic LLM provider for testing — no API calls."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}
        self._call_log: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def invoke(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        self._call_log.append({"prompt": prompt[:200], "system": system[:100]})
        # Return matching response or default
        for key, response in self._responses.items():
            if key.lower() in prompt.lower():
                return response
        return '{"status": "ok"}'

    async def invoke_with_structured_output(
        self,
        prompt: str,
        *,
        system: str = "",
        response_schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        self._call_log.append({"prompt": prompt[:200], "structured": True})
        for key, response in self._responses.items():
            if key.lower() in prompt.lower():
                import json
                try:
                    return json.loads(response)
                except (json.JSONDecodeError, TypeError):
                    pass
        return {"overall_assessment": "finalize", "confidence": 0.8, "concerns": [], "recommendations": [], "reasoning": "Mock"}

    async def astream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        yield "mock stream response"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    """Provide a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def tmp_working_dir() -> str:
    """Provide a temporary working directory."""
    d = tempfile.mkdtemp(prefix="test_pipeline_")
    return d


@pytest.fixture
def sample_csv(tmp_working_dir: str) -> str:
    """Create a small sample CSV for testing."""
    csv_path = Path(tmp_working_dir) / "sample.csv"
    csv_path.write_text(
        "age,income,education,target\n"
        "25,50000,12,0\n"
        "35,75000,16,1\n"
        "45,60000,14,0\n"
        "30,80000,18,1\n"
        "55,90000,20,1\n"
        "22,35000,12,0\n"
        "40,70000,16,1\n"
        "33,55000,14,0\n"
        "28,65000,16,1\n"
        "50,85000,18,1\n",
        encoding="utf-8",
    )
    return str(csv_path)

"""Anthropic Claude provider implementation."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import anthropic

from src.config.settings import settings
from src.llm.base import TokenAccumulator
from src.utils.errors import LLMProviderError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider:
    """Claude implementation via the Anthropic SDK."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        if not self._api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY not configured", provider="anthropic")
        self._model = model or settings.LLM_MODEL_CLAUDE
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        self._token_usage = TokenAccumulator()

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def token_usage(self) -> TokenAccumulator:
        return self._token_usage

    async def invoke(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Single-shot Claude call."""
        try:
            messages = [{"role": "user", "content": prompt}]

            # If json_mode, nudge the system prompt
            effective_system = system
            if json_mode and "json" not in system.lower():
                effective_system = f"{system}\n\nRespond with valid JSON only."

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=effective_system or "You are a precise ML engineering assistant.",
                messages=messages,
            )

            # Record token usage
            if hasattr(response, "usage") and response.usage:
                self._token_usage.record(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

            return response.content[0].text

        except anthropic.APIError as e:
            logger.error("Anthropic API error", error=str(e), model=self._model)
            raise LLMProviderError(f"Anthropic API error: {e}", provider="anthropic") from e

    async def invoke_with_structured_output(
        self,
        prompt: str,
        *,
        system: str = "",
        response_schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Call Claude expecting JSON output matching schema."""
        schema_str = json.dumps(response_schema, indent=2)
        structured_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n```json\n{schema_str}\n```\n"
            f"Return ONLY the JSON object, no other text."
        )

        raw = await self.invoke(
            structured_prompt,
            system=system,
            temperature=temperature,
            json_mode=True,
        )

        # Extract JSON from response (handle markdown code blocks)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (``` markers)
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse structured output", raw=raw[:200], error=str(e))
            raise LLMProviderError(
                f"Failed to parse JSON from Claude: {e}", provider="anthropic"
            ) from e

    async def astream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream Claude response."""
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system or "You are a precise ML engineering assistant.",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
            # Record usage from the final message after stream completes
            final_message = await stream.get_final_message()
            if hasattr(final_message, "usage") and final_message.usage:
                self._token_usage.record(
                    input_tokens=final_message.usage.input_tokens,
                    output_tokens=final_message.usage.output_tokens,
                )

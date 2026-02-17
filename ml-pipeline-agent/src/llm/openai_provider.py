"""OpenAI GPT provider implementation."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import openai

from src.config.settings import settings
from src.llm.base import TokenAccumulator
from src.utils.errors import LLMProviderError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider:
    """GPT-4o implementation via the OpenAI SDK."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        if not self._api_key:
            raise LLMProviderError("OPENAI_API_KEY not configured", provider="openai")
        self._model = model or settings.LLM_MODEL_OPENAI
        self._client = openai.AsyncOpenAI(api_key=self._api_key)
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
        """Single-shot GPT call."""
        try:
            messages = [
                {"role": "system", "content": system or "You are a precise ML engineering assistant."},
                {"role": "user", "content": prompt},
            ]

            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self._client.chat.completions.create(**kwargs)

            # Record token usage
            if hasattr(response, "usage") and response.usage:
                self._token_usage.record(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                )

            content = response.choices[0].message.content
            return content or ""

        except openai.APIError as e:
            logger.error("OpenAI API error", error=str(e), model=self._model)
            raise LLMProviderError(f"OpenAI API error: {e}", provider="openai") from e

    async def invoke_with_structured_output(
        self,
        prompt: str,
        *,
        system: str = "",
        response_schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Call GPT expecting JSON output matching schema."""
        schema_str = json.dumps(response_schema, indent=2)
        structured_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n```json\n{schema_str}\n```"
        )

        raw = await self.invoke(
            structured_prompt,
            system=system,
            temperature=temperature,
            json_mode=True,
        )

        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse structured output", raw=raw[:200], error=str(e))
            raise LLMProviderError(
                f"Failed to parse JSON from GPT: {e}", provider="openai"
            ) from e

    async def astream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream GPT response."""
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system or "You are a precise ML engineering assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            # Stream chunks with content
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            # Final chunk carries usage stats (when stream_options.include_usage=True)
            if hasattr(chunk, "usage") and chunk.usage:
                self._token_usage.record(
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                )

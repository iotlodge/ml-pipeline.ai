"""LLM provider factory — single function to get the configured provider."""

from __future__ import annotations

from src.llm.base import LLMProvider


def get_llm_provider(provider_name: str) -> LLMProvider:
    """
    Factory function. Returns the configured LLM provider.

    Args:
        provider_name: "anthropic" or "openai"

    Returns:
        An LLMProvider-conformant instance.
    """
    if provider_name == "anthropic":
        from src.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    elif provider_name == "openai":
        from src.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name!r}. Must be 'anthropic' or 'openai'."
        )

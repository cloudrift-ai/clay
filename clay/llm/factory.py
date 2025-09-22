"""Factory for creating LLM providers."""

from typing import Optional
from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .cloudrift_provider import CloudriftProvider


def create_llm_provider(
    provider_type: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> LLMProvider:
    """Create an LLM provider based on type."""
    provider_type = provider_type.lower()

    if provider_type in ["openai", "gpt"]:
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4"
        )
    elif provider_type in ["anthropic", "claude"]:
        return AnthropicProvider(
            api_key=api_key,
            model=model or "claude-3-5-sonnet-20241022"
        )
    elif provider_type in ["cloudrift", "deepseek"]:
        return CloudriftProvider(
            api_key=api_key,
            model=model or "deepseek-ai/DeepSeek-V3"
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")


def get_default_provider() -> Optional[LLMProvider]:
    """Get the default LLM provider based on available API keys."""
    import os

    if os.getenv("CLOUDRIFT_API_KEY"):
        return CloudriftProvider()
    elif os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider()
    elif os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicProvider()

    return None
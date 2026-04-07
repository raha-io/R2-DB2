"""Shared LLM client factory for agent subgraphs."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from settings import get_settings


def get_llm() -> ChatOpenAI:
    """Create an OpenRouter-compatible LLM client from settings."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openrouter.model,
        openai_api_key=settings.openrouter.api_key,
        openai_api_base=settings.openrouter.base_url,
        temperature=settings.openrouter.temperature,
        max_tokens=settings.openrouter.max_tokens,
        timeout=settings.openrouter.timeout,
    )

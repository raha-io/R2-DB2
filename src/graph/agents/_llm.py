"""Shared LLM client factory for agent subgraphs."""

from __future__ import annotations

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from settings import get_settings


def message_text(message: BaseMessage) -> str:
    """Return the message content as a plain string.

    LangChain's ``BaseMessage.content`` is typed ``str | list[str | dict]`` to
    cover multimodal payloads. Our agent flows always produce text, so flatten
    list payloads by joining their string parts.
    """
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for chunk in content:
        if isinstance(chunk, str):
            parts.append(chunk)
        elif isinstance(chunk, dict):
            text = chunk.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def get_llm() -> ChatOpenAI:
    """Create an OpenRouter-compatible LLM client from settings."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openrouter.model,
        api_key=SecretStr(settings.openrouter.api_key),
        base_url=settings.openrouter.base_url,
        temperature=settings.openrouter.temperature,
        max_completion_tokens=settings.openrouter.max_tokens,
        timeout=settings.openrouter.timeout,
    )

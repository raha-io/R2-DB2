"""Pydantic models for OpenAI-compatible API facade."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    """Single message in the OpenAI chat format."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """POST /v1/chat/completions request body."""
    model: str = "r2-db2-analyst"
    messages: list[ChatMessageRequest]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    # conversation_id passed via extra field
    conversation_id: str | None = None


# ── Response Models (non-streaming) ─────────────────────────────

class ChatMessageResponse(BaseModel):
    """Assistant message in the response."""
    role: Literal["assistant"] = "assistant"
    content: str


class ChatChoice(BaseModel):
    """Single choice in chat completion response."""
    index: int = 0
    message: ChatMessageResponse
    finish_reason: Literal["stop", "length"] | None = "stop"


class UsageInfo(BaseModel):
    """Token usage info."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """POST /v1/chat/completions response body (non-streaming)."""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "r2-db2-analyst"
    choices: list[ChatChoice]
    usage: UsageInfo = Field(default_factory=UsageInfo)


# ── Streaming Response Models ───────────────────────────────────

class DeltaContent(BaseModel):
    """Delta content for streaming."""
    role: str | None = None
    content: str | None = None


class StreamChoice(BaseModel):
    """Single choice in streaming chunk."""
    index: int = 0
    delta: DeltaContent
    finish_reason: Literal["stop", "length"] | None = None


class ChatCompletionChunk(BaseModel):
    """Single SSE chunk for streaming response."""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "r2-db2-analyst"
    choices: list[StreamChoice]


# ── Models List ─────────────────────────────────────────────────

class ModelInfo(BaseModel):
    """Single model in /v1/models response."""
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "r2-db2"


class ModelsListResponse(BaseModel):
    """GET /v1/models response body."""
    object: Literal["list"] = "list"
    data: list[ModelInfo]

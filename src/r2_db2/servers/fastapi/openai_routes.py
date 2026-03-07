"""OpenAI-compatible API routes for Open WebUI integration."""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse

from ..base import ChatHandler, ChatRequest
from ..base.models import ChatStreamChunk
from .openai_models import (
    ChatChoice,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageResponse,
    DeltaContent,
    ModelInfo,
    ModelsListResponse,
    StreamChoice,
    UsageInfo,
)

logger = logging.getLogger(__name__)

R2_DB2_MODEL_ID = "r2-db2-analyst"


def register_openai_routes(app: FastAPI, agent) -> None:
    """Register OpenAI-compatible /v1 routes on the FastAPI app.
    
    Args:
        app: The FastAPI application instance.
        agent: The R2-DB2 agent instance.
    """
    router = APIRouter(prefix="/v1", tags=["openai-compat"])
    chat_handler = ChatHandler(agent)

    @router.get("/models")
    async def list_models():
        """GET /v1/models — return available models."""
        return ModelsListResponse(
            data=[
                ModelInfo(id=R2_DB2_MODEL_ID, owned_by="r2-db2"),
            ]
        )

    @router.post("/chat/completions")
    async def chat_completions(request: Request, body: ChatCompletionRequest):
        """POST /v1/chat/completions — OpenAI-compatible chat endpoint.
        
        Translates OpenAI messages to internal ChatRequest,
        calls the R2-DB2 agent, and returns OpenAI-formatted response.
        """
        # 1. Extract the last user message from OpenAI messages
        user_message = ""
        for msg in reversed(body.messages):
            if msg.role == "user" and msg.content:
                user_message = msg.content
                break

        if not user_message:
            # Return empty response if no user message
            return ChatCompletionResponse(
                model=body.model,
                choices=[
                    ChatChoice(
                        message=ChatMessageResponse(content="No user message found.")
                    )
                ],
            )

        # 2. Build internal ChatRequest
        chat_req = ChatRequest(
            message=user_message,
            conversation_id=body.conversation_id or str(uuid.uuid4()),
        )

        # 3. Branch: streaming vs non-streaming
        if body.stream:
            return StreamingResponse(
                _stream_response(chat_handler, chat_req, body.model),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return await _non_stream_response(chat_handler, chat_req, body.model)

    app.include_router(router)


async def _non_stream_response(
    chat_handler: ChatHandler,
    chat_req: ChatRequest,
    model: str,
) -> ChatCompletionResponse:
    """Collect all chunks and return a single ChatCompletionResponse."""
    parts: list[str] = []

    try:
        async for chunk in chat_handler.handle_stream(chat_req):
            if chunk.simple:
                # chunk.simple is a dict, extract text content
                if isinstance(chunk.simple, dict):
                    # Try to get text from the simple component data
                    text = chunk.simple.get("text", "")
                    if text:
                        parts.append(text)
                elif isinstance(chunk.simple, str):
                    parts.append(chunk.simple)
    except Exception as exc:
        logger.exception("Error during agent processing")
        parts.append(f"Error: {exc}")

    full_text = "\n".join(parts) if parts else "No response generated."

    return ChatCompletionResponse(
        model=model,
        choices=[
            ChatChoice(message=ChatMessageResponse(content=full_text))
        ],
        usage=UsageInfo(
            prompt_tokens=0,
            completion_tokens=len(full_text.split()),
            total_tokens=len(full_text.split()),
        ),
    )


async def _stream_response(
    chat_handler: ChatHandler,
    chat_req: ChatRequest,
    model: str,
) -> AsyncGenerator[str, None]:
    """Yield OpenAI-format SSE chunks from the agent stream."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # First chunk: send role
    first_chunk = ChatCompletionChunk(
        id=completion_id,
        model=model,
        choices=[
            StreamChoice(
                delta=DeltaContent(role="assistant", content=""),
            )
        ],
    )
    yield f"data: {first_chunk.model_dump_json()}\n\n"

    # Stream content chunks
    try:
        async for chunk in chat_handler.handle_stream(chat_req):
            if chunk.simple:
                # Extract text from simple component
                text = ""
                if isinstance(chunk.simple, dict):
                    text = chunk.simple.get("text", "")
                elif isinstance(chunk.simple, str):
                    text = chunk.simple
                
                if text:
                    content_chunk = ChatCompletionChunk(
                        id=completion_id,
                        model=model,
                        choices=[
                            StreamChoice(
                                delta=DeltaContent(content=text + "\n"),
                            )
                        ],
                    )
                    yield f"data: {content_chunk.model_dump_json()}\n\n"
    except Exception as exc:
        logger.exception("Error during streaming")
        error_chunk = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                StreamChoice(
                    delta=DeltaContent(content=f"\n\nError: {exc}"),
                )
            ],
        )
        yield f"data: {error_chunk.model_dump_json()}\n\n"

    # Final chunk: finish_reason
    done_chunk = ChatCompletionChunk(
        id=completion_id,
        model=model,
        choices=[
            StreamChoice(
                delta=DeltaContent(),
                finish_reason="stop",
            )
        ],
    )
    yield f"data: {done_chunk.model_dump_json()}\n\n"
    yield "data: [DONE]\n\n"

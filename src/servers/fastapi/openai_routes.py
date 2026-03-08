"""OpenAI-compatible API routes for Open WebUI integration."""
from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse

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


def register_openai_routes(app: FastAPI, graph) -> None:
    """Register OpenAI-compatible /v1 routes on the FastAPI app.

    Args:
        app: The FastAPI application instance.
        graph: The LangGraph application instance.
    """
    router = APIRouter(prefix="/v1", tags=["openai-compat"])

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

        Translates OpenAI messages to a graph invocation and returns
        OpenAI-formatted response.
        """
        # Extract ALL user messages from OpenAI messages and join them
        user_messages: list[str] = []
        for msg in body.messages:
            if msg.role == "user" and msg.content:
                user_messages.append(msg.content)

        user_message = "\n".join(user_messages)

        if not user_message:
            return ChatCompletionResponse(
                model=body.model,
                choices=[
                    ChatChoice(
                        message=ChatMessageResponse(content="No user message found.")
                    )
                ],
            )

        if graph is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable: graph is not configured.",
            )

        if body.stream:
            return StreamingResponse(
                _stream_graph_response(graph, user_message, body.model, body.conversation_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return await _non_stream_graph_response(
                graph, user_message, body.model, body.conversation_id
            )

    app.include_router(router)


async def _non_stream_graph_response(
    graph,
    user_message: str,
    model: str,
    conversation_id: str | None = None,
) -> ChatCompletionResponse:
    """Run the graph to completion and return a single ChatCompletionResponse."""
    conv_id = conversation_id or str(uuid.uuid4())
    thread_id = f"{conv_id}-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = _build_initial_state(conv_id, user_message)

    try:
        result = await graph.ainvoke(initial_state, config)
        messages = result.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else "No response generated."
    except Exception as exc:
        logger.exception("Error during graph processing")
        last_msg = f"Error: {exc}"

    return ChatCompletionResponse(
        model=model,
        choices=[
            ChatChoice(message=ChatMessageResponse(content=last_msg))
        ],
        usage=UsageInfo(
            prompt_tokens=0,
            completion_tokens=len(last_msg.split()),
            total_tokens=len(last_msg.split()),
        ),
    )


# Mapping from graph node names to user-friendly thinking messages
_NODE_THINKING_MAP: dict[str, str] = {
    "intent_classify": "🔍 Understanding your question...\n\n",
    "context_retrieve": "📚 Loading database schema...\n\n",
    "plan": "📋 Creating analysis plan...\n\n",
    "hitl_approval": "",
    "sql_generate": "⚙️ Writing SQL query...\n\n",
    "sql_validate": "🔎 Validating SQL...\n\n",
    "sql_execute": "🚀 Running query on ClickHouse...\n\n",
    "analysis_sandbox": "📊 Analyzing results...\n\n",
    "report_assemble": "📝 Building report...\n\n",
    "final_response": "",
}


async def _stream_graph_response(
    graph,
    user_message: str,
    model: str,
    conversation_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream OpenAI-format SSE chunks using the LangGraph with thinking indicators."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    conv_id = conversation_id or str(uuid.uuid4())
    thread_id = f"{conv_id}-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = _build_initial_state(conv_id, user_message)

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

    try:
        async for event in graph.astream(initial_state, config, stream_mode="updates"):
            for node_name, _node_output in event.items():
                thinking_msg = _NODE_THINKING_MAP.get(node_name, "")
                if thinking_msg:
                    thinking_chunk = ChatCompletionChunk(
                        id=completion_id,
                        model=model,
                        choices=[
                            StreamChoice(
                                delta=DeltaContent(content=thinking_msg),
                            )
                        ],
                    )
                    yield f"data: {thinking_chunk.model_dump_json()}\n\n"

        # Get final state and emit the actual response
        final_state = await graph.aget_state(config)
        values = dict(final_state.values) if final_state.values else {}

        messages = values.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else ""

        if last_msg:
            content_chunk = ChatCompletionChunk(
                id=completion_id,
                model=model,
                choices=[
                    StreamChoice(
                        delta=DeltaContent(content="\n---\n\n" + last_msg + "\n"),
                    )
                ],
            )
            yield f"data: {content_chunk.model_dump_json()}\n\n"

    except Exception as exc:
        logger.exception("Error during graph streaming")
        error_chunk = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                StreamChoice(
                    delta=DeltaContent(content=f"\n\n❌ Error: {exc}"),
                )
            ],
        )
        yield f"data: {error_chunk.model_dump_json()}\n\n"
    finally:
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


def _build_initial_state(conversation_id: str, user_message: str) -> dict[str, Any]:
    """Build the initial graph state dict for a new analysis."""
    return {
        "conversation_id": conversation_id,
        "user_id": "anonymous",
        "messages": [{"role": "user", "content": user_message}],
        "intent": None,
        "plan": None,
        "plan_approved": False,
        "schema_context": "",
        "historical_queries": [],
        "generated_sql": None,
        "sql_validation_errors": [],
        "sql_retry_count": 0,
        "graph_step_count": 0,
        "query_result": None,
        "execution_time_ms": None,
        "analysis_summary": None,
        "analysis_artifacts": [],
        "report": None,
        "total_llm_tokens": 0,
        "estimated_cost_usd": 0.0,
        "trace_id": str(uuid.uuid4()),
        "error": None,
        "error_node": None,
    }

"""OpenAI-compatible API routes for Open WebUI integration."""

from __future__ import annotations

import hashlib
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

# Maps a stable conversation key (client conversation_id, or a hash of the
# prior message history when none is provided) to a LangGraph thread_id so
# follow-up turns from OpenWebUI can resume an interrupted graph instead of
# starting fresh. The graph itself persists everything via its checkpointer;
# this dict only holds the lookup key.
_THREAD_BY_CONVERSATION: dict[str, str] = {}


def _conversation_key(
    body: ChatCompletionRequest, prior_user_messages: list[str]
) -> str:
    """Return a stable key identifying this conversation across turns.

    Prefers an explicit ``conversation_id`` from the client. Falls back to a
    hash of only the prior USER messages so OpenWebUI (which always resends
    the full history) can be matched turn-to-turn regardless of what the
    assistant content looks like (streaming thinking indicators, etc.).
    """
    if body.conversation_id:
        return body.conversation_id
    digest = hashlib.sha1("\n".join(prior_user_messages).encode("utf-8")).hexdigest()
    return f"uhash-{digest[:16]}"


def _split_user_messages(body: ChatCompletionRequest) -> tuple[str, list[str]]:
    """Return (last_user_message, prior_user_messages)."""
    user_messages: list[str] = []
    for msg in body.messages:
        if msg.role == "user" and msg.content:
            user_messages.append(msg.content)
    last_user = user_messages[-1] if user_messages else ""
    prior_user_messages = user_messages[:-1] if user_messages else []
    return last_user, prior_user_messages


def _extract_pending_interrupt(state: Any) -> dict[str, Any] | None:
    """Pull the first interrupt payload from a paused graph state."""
    interrupts = getattr(state, "interrupts", None) or []
    for itr in interrupts:
        value = getattr(itr, "value", None)
        if isinstance(value, dict):
            return value
    tasks = getattr(state, "tasks", None) or []
    for task in tasks:
        for itr in getattr(task, "interrupts", []) or []:
            value = getattr(itr, "value", None)
            if isinstance(value, dict):
                return value
    return None


def _format_clarification(payload: dict[str, Any]) -> str:
    """Render an intent-agent clarification interrupt as an assistant message."""
    question = (
        payload.get("question") or "I need a bit more detail to answer this accurately."
    )
    ambiguities = payload.get("ambiguities") or []
    if not ambiguities:
        return question
    bullets = "\n".join(f"- {item}" for item in ambiguities)
    return f"{question}\n\n{bullets}"


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

        Translates OpenAI messages to a graph invocation. If the underlying
        LangGraph paused for a clarification interrupt on a previous turn,
        this turn's user message is forwarded as the resume payload.
        """
        last_user, prior_messages = _split_user_messages(body)
        if not last_user:
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

        conversation_key = _conversation_key(body, prior_messages)

        if body.stream:
            return StreamingResponse(
                _stream_graph_response(
                    graph, last_user, body.model, conversation_key, prior_messages
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        return await _non_stream_graph_response(
            graph, last_user, body.model, conversation_key, prior_messages
        )

    app.include_router(router)


async def _resolve_invocation(
    graph, user_message: str, conversation_key: str
) -> tuple[dict[str, Any], Any]:
    """Pick resume vs fresh invocation and return ``(config, payload)``.

    ``payload`` is either an initial state dict (fresh run) or a
    ``langgraph.types.Command`` resuming a paused interrupt.
    """
    from langgraph.types import Command

    existing_thread = _THREAD_BY_CONVERSATION.get(conversation_key)
    # Guard against the SHA1("") collision: on the very first turn of a new
    # OpenWebUI chat, prior_user_messages is empty and every such request
    # would hash to the same key, incorrectly resuming an old paused thread.
    if existing_thread and not conversation_key.startswith("uhash-da39a3ee5e6b4b0d"):
        config = {"configurable": {"thread_id": existing_thread}}
        try:
            state = await graph.aget_state(config)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load thread %s, starting fresh: %s", existing_thread, exc
            )
            state = None
        if state and state.next and _extract_pending_interrupt(state):
            logger.info("Resuming paused thread %s with user reply", existing_thread)
            return config, Command(resume=user_message)

    thread_id = f"{conversation_key}-{uuid.uuid4().hex[:8]}"
    _THREAD_BY_CONVERSATION[conversation_key] = thread_id
    config = {"configurable": {"thread_id": thread_id}}
    return config, _build_initial_state(conversation_key, user_message)


async def _final_message_from_state(graph, config: dict[str, Any]) -> str:
    """Read the assistant message to send back, including clarification text."""
    state = await graph.aget_state(config)
    if state.next:
        payload = _extract_pending_interrupt(state)
        if payload and payload.get("type") == "clarification":
            return _format_clarification(payload)
    values = dict(state.values) if state.values else {}
    messages = values.get("messages", [])
    return messages[-1].get("content", "") if messages else ""


def _register_next_turn_key(
    thread_id: str,
    prior_user_messages: list[str],
    last_user: str,
) -> None:
    """Pre-register the thread under the hash key turn N+1 will compute.

    OpenWebUI always resends the full transcript. The ``_conversation_key``
    hash is derived from only the prior user messages. On turn N+1 the
    prior user messages will be ``prior_user_messages + [last_user]``, so
    we can predict that hash now and register the current thread under it.
    """
    next_prior = list(prior_user_messages) + [last_user]
    digest = hashlib.sha1("\n".join(next_prior).encode("utf-8")).hexdigest()
    next_key = f"uhash-{digest[:16]}"
    _THREAD_BY_CONVERSATION[next_key] = thread_id


async def _non_stream_graph_response(
    graph,
    user_message: str,
    model: str,
    conversation_key: str,
    prior_messages: list[str],
) -> ChatCompletionResponse:
    """Run the graph to completion and return a single ChatCompletionResponse."""
    try:
        config, payload = await _resolve_invocation(
            graph, user_message, conversation_key
        )
        await graph.ainvoke(payload, config)
        last_msg = (
            await _final_message_from_state(graph, config) or "No response generated."
        )
        thread_id = config["configurable"]["thread_id"]
        _register_next_turn_key(thread_id, prior_messages, user_message)
    except Exception as exc:
        logger.exception("Error during graph processing")
        last_msg = f"Error: {exc}"

    return ChatCompletionResponse(
        model=model,
        choices=[ChatChoice(message=ChatMessageResponse(content=last_msg))],
        usage=UsageInfo(
            prompt_tokens=0,
            completion_tokens=len(last_msg.split()),
            total_tokens=len(last_msg.split()),
        ),
    )


# Mapping from graph node names to user-friendly thinking messages.
# `sql_execute` is resolved via :func:`_thinking_for` so the message reflects
# the active SQL dialect (ClickHouse / PostgreSQL / MySQL).
_NODE_THINKING_MAP: dict[str, str] = {
    "intent_agent": "🔍 Understanding your question...\n\n",
    "context_retrieve": "📚 Loading database schema...\n\n",
    "plan": "📋 Creating analysis plan...\n\n",
    "hitl_approval": "",
    "sql_agent": "⚙️ Writing SQL query...\n\n",
    "sql_validate": "🔎 Validating SQL...\n\n",
    "analysis_agent": "📊 Analyzing results...\n\n",
    "report_assemble": "📝 Building report...\n\n",
    "final_response": "",
}


def _thinking_for(node_name: str) -> str:
    if node_name == "sql_execute":
        from integrations.sql import DIALECT_LABELS, get_adapter

        label = DIALECT_LABELS.get(get_adapter().dialect, "the database")
        return f"🚀 Running query on {label}...\n\n"
    return _NODE_THINKING_MAP.get(node_name, "")


async def _stream_graph_response(
    graph,
    user_message: str,
    model: str,
    conversation_key: str,
    prior_messages: list[str],
) -> AsyncGenerator[str, None]:
    """Stream OpenAI-format SSE chunks using the LangGraph with thinking indicators."""
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

    try:
        config, payload = await _resolve_invocation(
            graph, user_message, conversation_key
        )

        async for event in graph.astream(payload, config, stream_mode="updates"):
            for node_name, _node_output in event.items():
                thinking_msg = _thinking_for(node_name)
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

        last_msg = await _final_message_from_state(graph, config)
        thread_id = config["configurable"]["thread_id"]
        _register_next_turn_key(thread_id, prior_messages, user_message)

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
        "intent_spec": None,
        "intent_clarification_rounds": 0,
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

"""Application entrypoint for the R2-DB2 analytical agent."""

from __future__ import annotations

import logging
import uuid as _uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from r2-db2.config.settings import get_settings
from r2-db2.graph.builder import build_graph
from r2-db2.servers.fastapi.openai_models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatMessageResponse,
    ModelsListResponse,
    ModelInfo,
    UsageInfo,
)
from r2-db2.servers.fastapi.routes import register_chat_routes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    logger.info("Starting R2-DB2 analytical agent (env=%s)", settings.environment)

    if settings.clickhouse.seed_on_startup:
        logger.info("Seeding ClickHouse with fake data...")
        try:
            from r2-db2.integrations.clickhouse.seed import seed_clickhouse_sync

            seed_clickhouse_sync(settings.clickhouse)
            logger.info("ClickHouse seeding complete")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ClickHouse seeding failed (may not be available yet): %s",
                exc,
            )

    logger.info("Building analytical agent graph...")

    checkpointer = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpointer = AsyncPostgresSaver.from_conn_string(settings.postgres.dsn)
        await checkpointer.setup()
        logger.info("Using PostgreSQL checkpointer")
    except Exception as exc:  # noqa: BLE001
        logger.warning("PostgreSQL checkpointer unavailable, using MemorySaver: %s", exc)
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    graph = build_graph(
        checkpointer=checkpointer,
        hitl_enabled=settings.graph.hitl_enabled,
    )
    app.state.graph = graph
    app.state.settings = settings

    logger.info("R2-DB2 analytical agent ready")
    yield

    logger.info("Shutting down R2-DB2 analytical agent")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="R2-DB2 Analytical Agent",
        description=(
            "Natural language to SQL analytical agent powered by LangGraph and ClickHouse"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from r2-db2.servers.fastapi.graph_routes import router as graph_router

    app.include_router(graph_router, prefix="/api/v1", tags=["graph"])

    # Register OpenAI-compatible routes for Open WebUI integration
    openai_router = APIRouter(prefix="/v1", tags=["openai-compat"])

    @openai_router.get("/models")
    async def list_models():
        return ModelsListResponse(
            data=[ModelInfo(id="r2-db2-analyst", owned_by="r2-db2")]
        )

    @openai_router.post("/chat/completions")
    async def chat_completions(request: Request, body: ChatCompletionRequest):
        # Extract last user message
        user_message = ""
        for msg in reversed(body.messages):
            if msg.role == "user" and msg.content:
                user_message = msg.content
                break

        if not user_message:
            return ChatCompletionResponse(
                model=body.model,
                choices=[ChatChoice(message=ChatMessageResponse(content="No user message found."))],
            )

        conversation_id = body.conversation_id or str(_uuid.uuid4())
        thread_config = {"configurable": {"thread_id": conversation_id}}

        # Invoke the graph with dict-style messages matching graph_routes.py pattern
        result = await request.app.state.graph.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=thread_config,
        )

        # Extract response from graph result (messages are dicts, not LangChain objects)
        messages = result.get("messages", [])
        ai_messages = [m for m in messages if m.get("role") == "assistant"]
        if ai_messages:
            content = ai_messages[-1].get("content", "No response generated.")
        else:
            content = "No response generated."

        return ChatCompletionResponse(
            model=body.model,
            choices=[ChatChoice(message=ChatMessageResponse(content=content))],
            usage=UsageInfo(
                prompt_tokens=0,
                completion_tokens=len(content.split()),
                total_tokens=len(content.split()),
            ),
        )

    app.include_router(openai_router)

    try:
        from r2-db2.core import Agent
        from r2-db2.servers.base import ChatHandler

        agent: Agent | None = getattr(app.state, "agent", None)
        if agent is not None:
            register_chat_routes(app, ChatHandler(agent), {})
        else:
            logger.info("Chat routes not registered (no agent on app.state)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chat routes registration skipped: %s", exc)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()

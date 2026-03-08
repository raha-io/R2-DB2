"""Application entrypoint for the R2-DB2 analytical agent."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import get_settings
from graph.builder import build_graph
from servers.fastapi.openai_routes import register_openai_routes

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
            from integrations.clickhouse.seed import seed_clickhouse_sync

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
    
    # Register OpenAI-compatible routes with graph streaming
    register_openai_routes(app, graph=graph)
    logger.info("OpenAI-compatible routes registered (graph streaming enabled)")

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

    from servers.fastapi.graph_routes import router as graph_router

    app.include_router(graph_router, prefix="/api/v1", tags=["graph"])
    # NOTE: OpenAI-compatible routes (/v1/...) are registered in the lifespan
    # context manager AFTER the graph is created.

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()

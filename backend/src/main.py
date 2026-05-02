"""Application entrypoint for the R2-DB2 analytical agent."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from settings import ClickHouseDb, get_settings
from graph.builder import build_graph
from servers.fastapi.openai_routes import register_openai_routes


def _find_frontend_dist() -> Path | None:
    """Locate the built frontend assets.

    Two layouts are supported: the container (``/app/src/main.py`` with
    ``/app/frontend/dist`` as a sibling) and local dev (``backend/src/main.py``
    with ``frontend/dist`` at the repo root, two levels up).
    """
    here = Path(__file__).resolve()
    for candidate in (
        here.parent.parent / "frontend" / "dist",
        here.parent.parent.parent / "frontend" / "dist",
    ):
        if candidate.is_dir():
            return candidate
    return None


FRONTEND_DIST = _find_frontend_dist()

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

    db = settings.database
    if isinstance(db, ClickHouseDb):
        if db.seed_on_startup:
            logger.info("Seeding ClickHouse with fake data...")
            try:
                from integrations.clickhouse.seed import seed_clickhouse_sync

                seed_clickhouse_sync(db)
                logger.info("ClickHouse seeding complete")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ClickHouse seeding failed (may not be available yet): %s",
                    exc,
                )
    else:
        logger.info("Skipping seed: dialect=%s has no seeder", db.type)

    logger.info("Building analytical agent graph...")

    async with AsyncExitStack() as stack:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            checkpointer = await stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(settings.postgres.dsn)
            )
            await checkpointer.setup()
            logger.info("Using PostgreSQL checkpointer")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PostgreSQL checkpointer unavailable, using MemorySaver: %s", exc
            )
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

        # Mount the static frontend last so explicit API routes win the match.
        if FRONTEND_DIST is not None:
            app.mount(
                "/",
                StaticFiles(directory=FRONTEND_DIST, html=True),
                name="frontend",
            )
            logger.info("Frontend mounted from %s", FRONTEND_DIST)
        else:
            logger.warning(
                "Frontend bundle not found — UI will not be served. "
                "Run `pnpm --dir frontend build` to produce frontend/dist.",
            )

        logger.info("R2-DB2 analytical agent ready")
        yield

        logger.info("Shutting down R2-DB2 analytical agent")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="R2-DB2 Analytical Agent",
        description=(
            "Natural language to SQL analytical agent powered by LangGraph"
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

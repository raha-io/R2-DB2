"""Application entrypoint for the R2-DB2 analytical agent."""

from __future__ import annotations

import logging
import uuid as _uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

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
from r2-db2.servers.fastapi.openai_routes import register_openai_routes

logger = logging.getLogger(__name__)


async def _create_r2_db2_agent(settings: Any) -> Any:
    """Create a R2-DB2 Agent instance for OpenAI-compatible streaming.
    
    This creates a minimal Agent that uses the OpenRouter LLM service
    and ClickHouse SQL runner for the OpenAI-compatible endpoint.
    """
    from r2-db2.core.agent import Agent, AgentConfig
    from r2-db2.core.user.resolver import UserResolver, RequestContext, User
    from r2-db2.integrations.clickhouse.sql_runner import ClickHouseSqlRunner
    from r2-db2.integrations.clickhouse.schema_catalog import get_schema_context
    from r2-db2.capabilities.agent_memory import AgentMemory
    from r2-db2.core.storage import MemoryConversationStore
    from r2-db2.core.registry import ToolRegistry
    from r2-db2.core.tool import Tool
    from r2-db2.core.tool.models import ToolContext, ToolResult
    from r2-db2.core.llm import LlmRequest, LlmResponse
    from r2-db2.core.llm.base import LlmService
    from typing import Type
    
    # Create a simple SQL runner tool
    class SimpleSqlTool(Tool):
        """Simple SQL execution tool for OpenAI-compatible endpoint."""
        
        def __init__(self, sql_runner: Any):
            self.sql_runner = sql_runner
        
        @property
        def name(self) -> str:
            return "execute_sql"
        
        @property
        def access_groups(self) -> list[str]:
            return ["sql_execute"]
        
        def get_args_schema(self) -> Type:
            from pydantic import BaseModel, Field
            
            class SqlArgs(BaseModel):
                sql: str = Field(description="SQL query to execute")
            
            return SqlArgs
        
        async def execute(self, context: ToolContext, args: Any) -> ToolResult:
            try:
                result = await self.sql_runner.execute(args.sql)
                return ToolResult(
                    success=True,
                    result_for_llm=f"Query executed successfully. {len(result.get('rows', []))} rows returned.",
                    ui_component=None
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    result_for_llm=f"Error executing query: {e}",
                    error=str(e),
                    ui_component=None
                )
    
    # Create LLM service using OpenRouter
    class OpenRouterLlmService(LlmService):
        """LLM service using OpenRouter API."""
        
        def __init__(self, settings: Any):
            self.settings = settings
            self.model = settings.openrouter.model
        
        async def send_request(self, request: LlmRequest) -> LlmResponse:
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(
                model=self.model,
                openai_api_key=self.settings.openrouter.api_key,
                openai_api_base=self.settings.openrouter.base_url,
                temperature=request.temperature or 0.0,
                max_tokens=request.max_tokens or 4096,
                timeout=self.settings.openrouter.timeout,
            )
            
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages or []
            ]
            
            if request.system_prompt:
                messages.insert(0, {"role": "system", "content": request.system_prompt})
            
            response = await llm.ainvoke(messages)
            
            return LlmResponse(
                content=response.content if hasattr(response, 'content') else str(response),
                tool_calls=None
            )
        
        async def stream_request(self, request: LlmRequest):
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(
                model=self.model,
                openai_api_key=self.settings.openrouter.api_key,
                openai_api_base=self.settings.openrouter.base_url,
                temperature=request.temperature or 0.0,
                max_tokens=request.max_tokens or 4096,
                timeout=self.settings.openrouter.timeout,
                streaming=True,
            )
            
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages or []
            ]
            
            if request.system_prompt:
                messages.insert(0, {"role": "system", "content": request.system_prompt})
            
            async for chunk in await llm.astream(messages):
                yield type('LlmStreamChunk', (), {
                    'content': chunk.content if hasattr(chunk, 'content') else str(chunk),
                    'tool_calls': None
                })()
    
    # Create user resolver
    class SimpleUserResolver(UserResolver):
        """Simple user resolver for development."""
        
        async def resolve_user(self, request_context: RequestContext) -> User:
            return User(
                id="default-user",
                email="default@example.com",
                group_memberships=["sql_execute"]
            )
    
    # Create SQL runner
    sql_runner = ClickHouseSqlRunner(
        host=settings.clickhouse.host,
        port=settings.clickhouse.port,
        database=settings.clickhouse.database,
        user=settings.clickhouse.user,
        password=settings.clickhouse.password,
    )
    
    # Create tool registry
    tool_registry = ToolRegistry()
    tool_registry.register(SimpleSqlTool(sql_runner))
    
    # Create LLM service
    llm_service = OpenRouterLlmService(settings)
    
    # Create agent memory
    agent_memory = AgentMemory()
    
    # Create agent
    agent = Agent(
        llm_service=llm_service,
        tool_registry=tool_registry,
        user_resolver=SimpleUserResolver(),
        agent_memory=agent_memory,
        conversation_store=MemoryConversationStore(),
        config=AgentConfig(
            stream_responses=True,
            max_tool_iterations=3,
        ),
    )
    
    return agent


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
    
    # Create R2-DB2 Agent for OpenAI-compatible streaming
    logger.info("Creating R2-DB2 Agent for OpenAI-compatible streaming...")
    try:
        agent = await _create_r2_db2_agent(settings)
        app.state.agent = agent
        # Register OpenAI-compatible routes NOW that the agent is available
        register_openai_routes(app, agent)
        logger.info("OpenAI-compatible routes registered with streaming support")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to create R2-DB2 Agent (OpenAI routes not registered): %s", exc)

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
    # NOTE: OpenAI-compatible routes (/v1/...) are registered in the lifespan
    # context manager AFTER the R2-DB2 Agent is created. They cannot be registered
    # here because app.state.agent is not yet available at create_app() time.

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()

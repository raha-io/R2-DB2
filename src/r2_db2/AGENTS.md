# AGENTS.md (src/r2-db2 scope)

This file applies to everything under [`src/r2-db2/`](src/r2-db2/).

## Single Agent Runtime
- The **sole runtime orchestrator** is the LangGraph graph in [`src/r2-db2/graph/`](src/r2-db2/graph/).
- [`src/r2-db2/main.py`](src/r2-db2/main.py:1) builds the graph at startup via [`build_graph()`](src/r2-db2/graph/builder.py:80) and registers it on all route handlers.
- There is **no secondary agent, no fallback workflow, and no legacy agent in the runtime path**.
- The legacy `Agent` class in [`src/r2-db2/core/agent/`](src/r2-db2/core/agent/) and `WorkflowHandler` in [`src/r2-db2/core/workflow/`](src/r2-db2/core/workflow/) are retained as library code only — they are **not instantiated or used at runtime**.

## Runtime Architecture Boundaries
- **Orchestration**: [`src/r2-db2/graph/`](src/r2-db2/graph/) — LangGraph DAG builder, nodes, and state.
- **Contracts**: [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/) — domain interfaces (sql_runner, agent_memory, file_system).
- **Implementations**: [`src/r2-db2/integrations/`](src/r2-db2/integrations/) — concrete backends (clickhouse, qdrant, local, plotly, postgres).
- **Servers**: [`src/r2-db2/servers/`](src/r2-db2/servers/) — thin FastAPI route adapters (graph routes + OpenAI-compatible routes).
- **Config**: [`src/r2-db2/config/`](src/r2-db2/config/) — settings and configuration.
- **Core services**: [`src/r2-db2/core/`](src/r2-db2/core/) — report service, audit, validation, registry, and legacy library code.

## State & Node Conventions
- Node functions must return explicit state updates; avoid hidden mutation.
- Keep state schema changes synchronized with [`src/r2-db2/graph/state.py`](src/r2-db2/graph/state.py:1) and architecture docs.
- Use bounded retries for recoverable SQL/sandbox failures.
- Global step guard (max 10 steps) prevents infinite loops.

## API/Server Expectations
- Graph-native routes at `/api/v1/analyze` via [`src/r2-db2/servers/fastapi/graph_routes.py`](src/r2-db2/servers/fastapi/graph_routes.py:1).
- OpenAI-compatible routes at `/v1/chat/completions` via [`src/r2-db2/servers/fastapi/openai_routes.py`](src/r2-db2/servers/fastapi/openai_routes.py:1).
- Both route sets exclusively use the LangGraph graph — no agent fallback.
- FastAPI routes should delegate to the graph and avoid business logic in route handlers.
- Keep request/response models explicit and version-safe.

## Tooling & Integrations
- Preserve host/sandbox isolation assumptions for code-execution paths.
- Ensure observability emits correlated identifiers (`trace_id`, conversation/user context).

## Change Discipline
- Any change to graph routing, node contracts, or state fields must be mirrored in [`docs/final-architecture.md`](docs/final-architecture.md:1).
- Any change to capability contracts should include implementation updates and tests.
- Do not introduce alternative agent/workflow runtime paths.

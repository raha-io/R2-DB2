# Agent Rules Standard (AGENTS.md)
# ClickHouse Analytical Agent (R2-DB2-based)

Token-efficient guide for architecture, code, and operations.

Keep this file aligned with [`docs/final-architecture.md`](docs/final-architecture.md:1). If tech, roadmap, or architecture changes, update both this file and the architecture doc.

## AGENTS.md Scope & Inheritance
- This root file applies to the entire repository unless a deeper `AGENTS.md` exists in a subdirectory.
- Deeper `AGENTS.md` files narrow or extend instructions for that subtree only.
- When conflicts occur, use the most specific (deepest) `AGENTS.md` that applies to the file being edited.

## Project Summary
Single-agent analytical system that turns natural language questions into audited, reproducible reports backed by ClickHouse. A single LangGraph DAG orchestrates the entire pipeline — there is no secondary agent or fallback workflow. Deterministic orchestration, strict host/sandbox isolation, and audited execution.

## Single Agent Architecture
- **One agent**: The LangGraph graph in [`src/r2-db2/graph/`](src/r2-db2/graph/) is the sole runtime orchestrator.
- **No legacy agent**: The legacy core `Agent` class in [`src/r2-db2/core/agent/`](src/r2-db2/core/agent/) is retained as library code but is **not instantiated or used at runtime**.
- **No fallback**: API routes (OpenAI-compatible and graph-native) exclusively use the LangGraph graph. There is no agent fallback path.
- **Entry points**: [`src/r2-db2/main.py`](src/r2-db2/main.py:1) builds the graph at startup and registers it on all route handlers.

## Repository Layout
- [`src/r2-db2/graph/`](src/r2-db2/graph/): **LangGraph DAG** — builder, nodes, state. This is the runtime orchestrator.
- [`src/r2-db2/core/`](src/r2-db2/core/): registry, validation, audit, recovery, observability, report service, and legacy agent/workflow (library code, not runtime).
- [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/): domain interfaces (sql_runner, agent_memory, file_system).
- [`src/r2-db2/integrations/`](src/r2-db2/integrations/): concrete backends (clickhouse, qdrant, local, plotly, postgres).
- [`src/r2-db2/servers/`](src/r2-db2/servers/): FastAPI route adapters (graph routes + OpenAI-compatible routes).
- [`src/r2-db2/config/`](src/r2-db2/config/): settings and configuration.
- [`docs/`](docs/): primary architecture: [`docs/final-architecture.md`](docs/final-architecture.md:1).

## Working Norms
- Keep changes minimal, local, and reversible.
- Preserve clean separation between interfaces (`capabilities`) and implementations (`integrations`).
- Prefer protocol-driven design and dependency inversion over concrete coupling.
- Keep orchestration deterministic; avoid hidden side effects across graph nodes.
- Update docs and tests whenever behavior or contracts change.
- All runtime orchestration goes through the LangGraph graph — do not introduce alternative agent paths.

## Skills (Project)
- architecture-patterns: backend architecture patterns and separation of concerns.
- async-python-patterns: asyncio + non-blocking IO patterns.
- auth-implementation-patterns: JWT/RBAC, secure auth flows.
- fastapi-templates: production FastAPI patterns.
- api-design-principles: consistent, stable API design.
- .kilocode/skills-code:
  - env-config
  - langchain-builder
  - langgraph-builder
  - mcp-builder
  - mcp-integration
  - skill-creator
  - uv-package-manager

## Code Style (Python)
- Type hints everywhere; prefer `TypedDict` for state and Protocols for interfaces.
- Format with Black; lint with Ruff.
- Keep functions small; separate pure logic from IO.
- Graph nodes must return explicit state updates (no hidden side effects).

## Final Architecture (Token-Efficient)
- Orchestrator: Single LangGraph DAG with HITL gates and bounded retries.
- Data: external ClickHouse for analytics (dev mode: local Docker-based ClickHouse).
- Schema/Data Catalog: Postgres + Redis for schema metadata and caching.
- Semantic Retrieval: Qdrant via external API for schema + historical query pairs.
- Sandbox: E2B + smolagents CodeAgent; no credentials inside sandbox.
- Outputs: PDF + Plotly HTML + CSV/Parquet + JSON summary.
- Observability/Audit: Langfuse traces/metrics + structured logs.
- Frontend: Open WebUI optional; API-first backend.
- API Surface: Graph-native routes (`/api/v1/analyze`) + OpenAI-compatible routes (`/v1/chat/completions`), both backed by the same LangGraph graph.

## Execution Graph (Reference)
- Nodes: `intent_classify`, `context_retrieve`, `plan`, `hitl_approval`, `sql_generate`, `sql_validate`, `sql_execute`, `analysis_sandbox`, `report_assemble`, `final_response`.
- Routing: reject plan → `final_response`; off_topic/clarification → `final_response`; otherwise sequential; bounded retries on SQL validation/execution errors.
- Global step guard prevents infinite loops (max 10 steps).
- Graph built in [`build_graph()`](src/r2-db2/graph/builder.py:80) and compiled with checkpointer.

## State Design
```python
class AnalyticalAgentState(TypedDict, total=False):
    conversation_id: str
    user_id: str
    messages: Annotated[list[dict[str, Any]], operator.add]
    intent: Literal["new_analysis", "follow_up", "clarification", "off_topic"] | None
    plan: dict[str, Any] | None
    plan_approved: bool
    schema_context: str
    historical_queries: list[dict[str, Any]]
    generated_sql: str | None
    sql_validation_errors: list[str]
    sql_retry_count: int
    graph_step_count: int
    query_result: dict[str, Any] | None
    execution_time_ms: int | None
    analysis_summary: str | None
    analysis_artifacts: Annotated[list[dict[str, Any]], operator.add]
    output_formats: list[str]
    output_files: list[dict[str, str]]
    report: dict[str, Any] | None
    plotly_figures: list[dict[str, Any]]
    report_output: dict[str, Any] | None
    total_llm_tokens: int
    estimated_cost_usd: float
    trace_id: str
    error: str | None
    error_node: str | None
```

## Interfaces (Pattern)
```python
from typing import Protocol, Any

class SQLRunner(Protocol):
    async def validate(self, sql: str) -> list[str]: ...
    async def explain(self, sql: str) -> dict[str, Any]: ...
    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...
```

## Security
- No secrets in prompts or sandbox; ClickHouse creds stay on host.
- Reject DDL/DML; allow read-only SQL only.
- Enforce table allowlists and LIMIT guards.
- Tenant isolation + RBAC; redact PII unless authorized.

## Observability & Audit
- Use Langfuse for tracing/metrics; emit per-node spans with shared `trace_id`.
- Structured logs include `user_id`, `conversation_id`, plan_id, SQL hash.
- Record all LLM calls, SQL executions, tool calls, approvals.

## Error Handling
- Bounded retries: SQL regen on validation errors; single retry for sandbox failures.
- Global step guard (max 10 steps) prevents infinite loops in the graph.
- Route unrecoverable errors to HITL or structured failure response via `final_response` node.

## Caching & Outputs
- Cache SQL results and schema retrievals with TTL.
- Default outputs: PDF + Plotly HTML + CSV/Parquet + JSON summary.
- Report assembly via [`ReportOutputService`](src/r2-db2/core/report/service.py:1).

## Testing
- Use pytest for unit tests on graph nodes, SQL validation, and report assembly.
- Add regression tests for SQL generation and evaluation datasets.
- Maintain coverage for critical paths (planning → execution → reporting).

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_report_output.py -v

# Run with coverage
uv run pytest tests/ --cov=r2-db2 --cov-report=term-missing
```

The `pythonpath = ["src"]` setting in `pyproject.toml` ensures the `r2-db2` package is importable during tests without manual `PYTHONPATH` configuration.

## Contribution Guidance
- Keep this file and [`docs/final-architecture.md`](docs/final-architecture.md:1) in sync.
- Update docs whenever node contracts, state schema, tech stack, or roadmap changes.
- Do not introduce alternative agent/workflow runtime paths — all orchestration goes through the LangGraph graph.

## Subfolder Agent Guides
- [`docs/AGENTS.md`](docs/AGENTS.md): Documentation authoring and architecture-doc sync rules.
- [`src/AGENTS.md`](src/AGENTS.md): Source-wide implementation and quality guardrails.
- [`src/r2-db2/AGENTS.md`](src/r2-db2/AGENTS.md): Runtime architecture boundaries and module-level conventions.
- [`tests/AGENTS.md`](tests/AGENTS.md): Test style and coverage expectations.
- [`scripts/AGENTS.md`](scripts/AGENTS.md): Script safety and reproducibility rules.

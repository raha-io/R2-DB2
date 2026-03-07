# Agent Rules Standard (AGENTS.md)
# ClickHouse Analytical Agent (R2-DB2-based)

Token-efficient guide for architecture, code, and operations.

Keep this file aligned with [`docs/final-architecture.md`](docs/final-architecture.md:1). If tech, roadmap, or architecture changes, update both this file and the architecture doc.

## AGENTS.md Scope & Inheritance
- This root file applies to the entire repository unless a deeper `AGENTS.md` exists in a subdirectory.
- Deeper `AGENTS.md` files narrow or extend instructions for that subtree only.
- When conflicts occur, use the most specific (deepest) `AGENTS.md` that applies to the file being edited.

## Project Summary
Multi-agent analytical system that turns natural language questions into audited, reproducible reports backed by ClickHouse. Deterministic orchestration (LangGraph), strict host/sandbox isolation, and audited execution.

## Repository Layout
- [`src/r2-db2/core/`](src/r2-db2/core/): orchestration, registry, workflow, agent, validation, audit, recovery, observability.
- [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/): domain interfaces (sql_runner, agent_memory, file_system).
- [`src/r2-db2/integrations/`](src/r2-db2/integrations/): concrete backends (clickhouse, qdrant, local, plotly, postgres).
- [`src/r2-db2/servers/`](src/r2-db2/servers/): FastAPI/CLI adapters + chat handler.
- [`docs/`](docs/): primary architecture: [`docs/final-architecture.md`](docs/final-architecture.md:1).

## Working Norms
- Keep changes minimal, local, and reversible.
- Preserve clean separation between interfaces (`capabilities`) and implementations (`integrations`).
- Prefer protocol-driven design and dependency inversion over concrete coupling.
- Keep orchestration deterministic; avoid hidden side effects across workflow nodes.
- Update docs and tests whenever behavior or contracts change.

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
- Workflow nodes must return explicit state updates (no hidden side effects).

## Final Architecture (Token-Efficient)
- Orchestrator: LangGraph DAG with HITL gates and bounded retries.
- Data: external ClickHouse for analytics (dev mode: local Docker-based ClickHouse).
- Schema/Data Catalog: Postgres + Redis for schema metadata and caching.
- Semantic Retrieval: Qdrant via external API for schema + historical query pairs.
- Sandbox: E2B + smolagents CodeAgent; no credentials inside sandbox.
- Outputs: PDF + Plotly HTML + CSV/Parquet + JSON summary.
- Observability/Audit: Langfuse traces/metrics + structured logs.
- Frontend: Open WebUI optional; API-first backend.

## Execution Graph (Reference)
- Nodes: `intent_classify`, `context_retrieve`, `plan`, `hitl_approval`, `sql_generate`, `sql_execute`, `analysis_sandbox`, `report_assemble`, `memory_update`, `final_response`.
- Routing: reject plan → `final_response`; otherwise sequential; bounded retries on SQL/sandbox errors.

## State Design (Example)
```python
from typing import TypedDict, Any, Literal

class AnalyticalAgentState(TypedDict):
    conversation_id: str
    user_id: str
    messages: list[dict[str, Any]]
    intent: Literal["new_analysis", "follow_up", "clarification", "off_topic"] | None
    plan: dict[str, Any] | None
    plan_approved: bool
    schema_context: list[dict[str, Any]]
    historical_queries: list[dict[str, Any]]
    generated_sql: str | None
    sql_validation_errors: list[str]
    sql_retry_count: int
    query_result: dict[str, Any] | None
    execution_time_ms: int | None
    analysis_artifacts: list[dict[str, Any]]
    sandbox_id: str | None
    followup_candidates: list[dict[str, Any]]
    approved_followups: list[dict[str, Any]]
    report: dict[str, Any] | None
    output_formats: list[Literal["pdf", "plotly_html", "csv", "parquet", "json"]]
    total_llm_tokens: int
    estimated_cost_usd: float
    trace_id: str
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
- Route unrecoverable errors to HITL or structured failure response.

## Caching & Outputs
- Cache SQL results and schema retrievals with TTL.
- Default outputs: PDF + Plotly HTML + CSV/Parquet + JSON summary.

## Testing
- Use pytest for unit tests on workflow nodes, SQL validation, and report assembly.
- Add regression tests for SQL generation and evaluation datasets.
- Maintain coverage for critical paths (planning → execution → reporting).

## Contribution Guidance
- Keep this file and [`docs/final-architecture.md`](docs/final-architecture.md:1) in sync.
- Update docs whenever node contracts, state schema, tech stack, or roadmap changes.

## Subfolder Agent Guides
- [`docs/AGENTS.md`](docs/AGENTS.md): Documentation authoring and architecture-doc sync rules.
- [`src/AGENTS.md`](src/AGENTS.md): Source-wide implementation and quality guardrails.
- [`src/r2-db2/AGENTS.md`](src/r2-db2/AGENTS.md): Runtime architecture boundaries and module-level conventions.
- [`tests/AGENTS.md`](tests/AGENTS.md): Test style and coverage expectations.
- [`scripts/AGENTS.md`](scripts/AGENTS.md): Script safety and reproducibility rules.

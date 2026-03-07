# AGENTS.md (src/r2-db2 scope)

This file applies to everything under [`src/r2-db2/`](src/r2-db2/).

## Runtime Architecture Boundaries
- Keep orchestration logic inside [`src/r2-db2/graph/`](src/r2-db2/graph/) and workflow abstractions under [`src/r2-db2/core/workflow/`](src/r2-db2/core/workflow/).
- Keep contracts in [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/) and concrete implementations in [`src/r2-db2/integrations/`](src/r2-db2/integrations/).
- Keep server adapters under [`src/r2-db2/servers/`](src/r2-db2/servers/) thin and transport-focused.

## State & Node Conventions
- Node functions must return explicit state updates; avoid hidden mutation.
- Keep state schema changes synchronized with [`src/r2-db2/graph/state.py`](src/r2-db2/graph/state.py:1) and architecture docs.
- Use bounded retries for recoverable SQL/sandbox failures.

## Tooling & Integrations
- Tools in [`src/r2-db2/tools/`](src/r2-db2/tools/) should expose narrow, auditable operations.
- Preserve host/sandbox isolation assumptions for code-execution paths.
- Ensure observability emits correlated identifiers (`trace_id`, conversation/user context).

## API/Server Expectations
- FastAPI routes should delegate to core services and avoid business logic in route handlers.
- Keep request/response models explicit and version-safe.

## Change Discipline
- Any change to graph routing, node contracts, or state fields must be mirrored in [`docs/final-architecture.md`](docs/final-architecture.md:1).
- Any change to capability contracts should include implementation updates and tests.

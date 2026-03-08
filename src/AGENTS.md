# AGENTS.md (src scope)

This file applies to everything under [`src/`](src/).

## Purpose
- Maintain clear architecture boundaries and production-grade implementation quality.
- Keep source behavior aligned with architecture in [`docs/final-architecture.md`](docs/final-architecture.md:1).

## Single Agent Runtime
- The **only** runtime orchestrator is the LangGraph graph in [`src/r2-db2/graph/`](src/r2-db2/graph/).
- [`src/r2-db2/main.py`](src/r2-db2/main.py:1) builds the graph at startup and registers it on all route handlers.
- Do not introduce alternative agent or workflow runtime paths.
- The legacy `Agent` class in [`src/r2-db2/core/agent/`](src/r2-db2/core/agent/) is retained as library code but is **not instantiated at runtime**.

## Implementation Guardrails
- Use capability interfaces under [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/) as dependency boundaries.
- Keep concrete providers in [`src/r2-db2/integrations/`](src/r2-db2/integrations/) replaceable via configuration.
- Avoid cross-layer coupling (e.g., integrations directly shaping graph state).
- Keep graph node behavior deterministic and explicit.

## Python Quality Standards
- Use type hints consistently; prefer `TypedDict`/`Protocol` where applicable.
- Keep pure logic separate from IO-heavy operations.
- Raise explicit domain errors over generic exceptions.
- Preserve async correctness; avoid blocking calls inside async paths.

## Security & Safety
- Enforce read-only SQL validation and table/operation guardrails.
- Never pass secrets into sandbox execution paths.
- Keep tenant context and request context propagation explicit.

## Required Updates When Changing Behavior
- Update tests under [`tests/`](tests/) for behavior changes.
- Update docs when node contracts, state fields, or interfaces change.
- Keep all AGENTS.md files in sync with architectural changes.

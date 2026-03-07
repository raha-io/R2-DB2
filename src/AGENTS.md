# AGENTS.md (src scope)

This file applies to everything under [`src/`](src/).

## Purpose
- Maintain clear architecture boundaries and production-grade implementation quality.
- Keep source behavior aligned with architecture in [`docs/final-architecture.md`](docs/final-architecture.md:1).

## Implementation Guardrails
- Use capability interfaces under [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/) as dependency boundaries.
- Keep concrete providers in [`src/r2-db2/integrations/`](src/r2-db2/integrations/) replaceable via configuration.
- Avoid cross-layer coupling (for example, integrations directly shaping workflow state).
- Keep workflow behavior deterministic and explicit.

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

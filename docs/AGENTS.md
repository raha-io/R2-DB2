# AGENTS.md (docs scope)

This file applies to everything under [`docs/`](docs/).

## Purpose
- Keep documentation concise, technically accurate, and synchronized with implementation.
- Treat [`docs/final-architecture.md`](docs/final-architecture.md:1) as the canonical architecture reference.

## Single Agent Principle
- The system uses a **single LangGraph DAG** as its sole runtime orchestrator.
- Documentation must reflect this: there is no secondary agent, no fallback workflow, and no legacy agent in the runtime path.
- The legacy core `Agent` class in [`src/r2-db2/core/agent/`](src/r2-db2/core/agent/) exists as library code only — do not document it as an active runtime component.

## Documentation Rules
- When architecture changes, update [`docs/final-architecture.md`](docs/final-architecture.md:1) and any dependent docs in the same change.
- Keep terminology consistent with runtime modules in [`src/r2-db2/`](src/r2-db2/).
- Prefer explicit node/contract names (e.g., `intent_classify`, `sql_generate`, `report_assemble`) over vague descriptions.
- Preserve security guarantees (host-only credentials, sandbox isolation, read-only SQL posture) in all relevant docs.

## Style
- Optimize for token efficiency: short sections, concrete bullets, minimal narrative repetition.
- Use stable section headings so other docs can reference them reliably.
- Link to concrete files/functions when describing behavior.

## Required Sync Checks
- If execution flow changes, verify DAG and node descriptions remain aligned with [`src/r2-db2/graph/builder.py`](src/r2-db2/graph/builder.py:1) and [`src/r2-db2/graph/nodes.py`](src/r2-db2/graph/nodes.py:1).
- If state schema changes, update references to [`src/r2-db2/graph/state.py`](src/r2-db2/graph/state.py:1).
- If interfaces change, keep docs aligned with capability contracts under [`src/r2-db2/capabilities/`](src/r2-db2/capabilities/).
- If API surface changes, verify route descriptions match [`src/r2-db2/servers/fastapi/graph_routes.py`](src/r2-db2/servers/fastapi/graph_routes.py:1) and [`src/r2-db2/servers/fastapi/openai_routes.py`](src/r2-db2/servers/fastapi/openai_routes.py:1).

# AGENTS.md (tests scope)

This file applies to everything under [`tests/`](tests/).

## Test Expectations
- Use `pytest` conventions and readable, behavior-focused test names.
- Prefer deterministic tests with minimal external dependencies.
- Cover critical paths for planning → SQL generation/validation → execution → report assembly.

## High-Value Test Selection
- Purpose: run minimal, high-signal tests first.
- Prioritized commands:
  1. `uv run pytest tests/test_servers_fastapi.py -q`
  2. `uv run pytest tests/test_tools.py -q`
  3. `uv run pytest tests/test_integrations_plotly.py -q`
  4. `uv run pytest tests/test_integrations_postgres.py -q`
  5. `uv run pytest tests/test_integrations_qdrant.py -q`
- Quick gate (all five in one run):
  - `uv run pytest tests/test_servers_fastapi.py tests/test_tools.py tests/test_integrations_plotly.py tests/test_integrations_postgres.py tests/test_integrations_qdrant.py -q`
- If touching only one subsystem, run only its important suite.
- Run broader suites only when changing shared core contracts.

## Style & Structure
- Keep fixtures small, composable, and local when possible.
- Avoid over-mocking core domain behavior; mock boundaries (network, storage, external services) instead.
- Assert on contract-level outcomes, not internal implementation details.

## Regression Discipline
- Add regression tests for bug fixes and contract changes.
- When state schema or workflow routing changes, update/add tests to reflect the new behavior.
- Keep sample data compact and representative.

## Quality Gate
- Ensure new tests fail before fixes and pass after fixes.
- Keep test runtime practical for local development and CI.

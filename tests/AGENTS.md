# AGENTS.md (tests scope)

This file applies to everything under [`tests/`](tests/).

## Test Expectations
- Use `pytest` conventions and readable, behavior-focused test names.
- Prefer deterministic tests with minimal external dependencies.
- Cover critical paths for planning → SQL generation/validation → execution → report assembly.

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

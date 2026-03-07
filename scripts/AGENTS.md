# AGENTS.md (scripts scope)

This file applies to everything under [`scripts/`](scripts/).

## Script Safety
- Scripts must be explicit, idempotent where feasible, and safe by default.
- Prefer dry-run options or clear preflight validation before destructive operations.
- Emit actionable logs for each major step.

## Reproducibility
- Keep scripts deterministic and environment-aware.
- Read configuration from environment/settings consistently.
- Document required env vars and assumptions at the top of each script.

## Boundaries
- Do not bypass domain/service interfaces when a reusable core path already exists.
- Keep one-off operational logic isolated from runtime application modules.

## Operational Hygiene
- Use clear exit codes and structured error messages.
- Validate inputs early and fail fast with remediation guidance.
- When scripts affect architecture behavior, update [`docs/final-architecture.md`](docs/final-architecture.md:1) and relevant runbooks.

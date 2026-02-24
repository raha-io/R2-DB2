# R2-DB2 — ClickHouse Analytical Agent

Multi-agent analytical system that turns natural language questions into audited, reproducible reports backed by ClickHouse. Uses LangGraph for deterministic orchestration and OpenRouter for LLM access.

## Architecture Overview

```
User Question → POST /api/v1/analyze
    ↓
intent_classify → context_retrieve → plan → hitl_approval (auto-approve by default)
    ↓
sql_generate → sql_validate ──→ sql_execute → analysis_sandbox → report_assemble → final_response
    ↑         ↓ (errors)
    └─────────┘ (retry up to 3×)
```

## Tech Stack

| Component | Details |
|---|---|
| Language | Python 3.12 |
| API | FastAPI |
| Orchestration | LangGraph |
| LLM | LangChain + OpenRouter |
| Analytics DB | ClickHouse |
| Checkpointer | PostgreSQL |
| Cache | Redis |
| Vector DB | Qdrant |
| Infra | Docker Compose |
| Package Manager | uv |

## Prerequisites

- Docker & Docker Compose v2
- An OpenRouter API key (get one at `https://openrouter.ai/keys`)

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd r2-db2

# 2. Configure environment
cp .env.example .env
# Edit .env and set your OpenRouter API key:
#   OPENROUTER__API_KEY=sk-or-v1-your-key-here

# 3. Start all services
docker compose up --build

# 4. Wait for services to be healthy (ClickHouse seeding takes ~30s)
# The app will be available at http://localhost:8000

# 5. Verify it's running
curl http://localhost:8000/health
```

## API Usage

### `POST /api/v1/analyze`
Submit a natural language question.

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What were total sales by month for the last year?"
  }'
```

```json
{
  "thread_id": "thread_123",
  "status": "running",
  "message": "Plan created and execution started."
}
```

### `POST /api/v1/approve`
Approve or reject a plan (only when HITL is enabled).

```bash
curl -X POST http://localhost:8000/api/v1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_123",
    "approved": true,
    "notes": "Looks good"
  }'
```

```json
{
  "thread_id": "thread_123",
  "approved": true,
  "status": "resumed"
}
```

### `GET /api/v1/threads/{thread_id}/state`
Get the current thread state.

```bash
curl http://localhost:8000/api/v1/threads/thread_123/state
```

```json
{
  "thread_id": "thread_123",
  "intent": "new_analysis",
  "plan_approved": true,
  "sql_retry_count": 0,
  "status": "running"
}
```

### `GET /health`
Health check.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok"
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Runtime environment |
| `DEBUG` | `true` | Enable debug logging |
| `OPENROUTER__API_KEY` | *(required)* | Your OpenRouter API key |
| `OPENROUTER__BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |
| `OPENROUTER__DEFAULT_MODEL` | `openai/gpt-4o` | Default LLM model |
| `CLICKHOUSE__HOST` | `clickhouse` | ClickHouse hostname |
| `CLICKHOUSE__PORT` | `8123` | ClickHouse HTTP port |
| `CLICKHOUSE__DATABASE` | `analytics` | ClickHouse database name |
| `CLICKHOUSE__USER` | `default` | ClickHouse user |
| `CLICKHOUSE__PASSWORD` | *(empty)* | ClickHouse password |
| `POSTGRES__HOST` | `postgres` | PostgreSQL hostname |
| `POSTGRES__PORT` | `5432` | PostgreSQL port |
| `POSTGRES__USER` | `r2-db2` | PostgreSQL user |
| `POSTGRES__PASSWORD` | `r2_db2_secret` | PostgreSQL password |
| `POSTGRES__DATABASE` | `r2-db2` | PostgreSQL database |
| `REDIS__HOST` | `redis` | Redis hostname |
| `REDIS__PORT` | `6379` | Redis port |
| `QDRANT__HOST` | `qdrant` | Qdrant hostname |
| `QDRANT__PORT` | `6333` | Qdrant port |
| `SERVER__HOST` | `0.0.0.0` | Server bind address |
| `SERVER__PORT` | `8000` | Server port |
| `GRAPH__HITL_ENABLED` | `false` | Enable Human-in-the-Loop approval |
| `LANGFUSE__PUBLIC_KEY` | *(empty)* | Langfuse public key |
| `LANGFUSE__SECRET_KEY` | *(empty)* | Langfuse secret key |
| `LANGFUSE__HOST` | *(empty)* | Langfuse host URL |

## Docker Services

| Service | Image | Port | Purpose |
|---|---|---|---|
| `app` | Built from Dockerfile | 8000 | FastAPI application |
| `clickhouse` | clickhouse/clickhouse-server:24.3-alpine | 8123, 9000 | Analytics database |
| `clickhouse-init` | Built from Dockerfile | — | One-shot data seeder |
| `postgres` | postgres:16-alpine | 5432 | LangGraph checkpointer |
| `redis` | redis:7-alpine | 6379 | Caching layer |
| `qdrant` | qdrant/qdrant:v1.9.7 | 6333, 6334 | Vector search |

## Enabling Human-in-the-Loop (HITL)

HITL is disabled by default. To enable:

```bash
# In .env
GRAPH__HITL_ENABLED=true
```

When enabled, the graph pauses before the approval node. Use `POST /api/v1/approve` to resume.

## Development (without Docker)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Start dependencies (ClickHouse, Postgres, Redis, Qdrant) via Docker
docker compose up clickhouse postgres redis qdrant -d

# Update .env for local development
# Change hostnames from service names to localhost:
#   CLICKHOUSE__HOST=localhost
#   POSTGRES__HOST=localhost
#   REDIS__HOST=localhost
#   QDRANT__HOST=localhost

# Seed ClickHouse
uv run python -c "from r2-db2.integrations.clickhouse.seed import seed_clickhouse_sync; seed_clickhouse_sync('localhost', 8123, 'analytics')"

# Run the app
uv run uvicorn r2-db2.main:app --reload --host 0.0.0.0 --port 8000
```

## Project Structure

```
src/r2-db2/
├── config/          # Pydantic Settings (env-based configuration)
├── graph/           # LangGraph orchestration (state, nodes, builder)
├── integrations/
│   ├── clickhouse/  # ClickHouse connector, seeder, schema catalog
│   ├── postgres/    # PostgreSQL connector
│   ├── qdrant/      # Vector search
│   └── local/       # Local file-based implementations
├── servers/
│   └── fastapi/     # FastAPI app, routes, graph API routes
├── core/            # Core abstractions (agent, workflow, tools, etc.)
├── tools/           # Agent tools (SQL, Python, visualization)
└── main.py          # ASGI entrypoint with lifespan
```

Key paths:
- [`src/r2-db2/`](src/r2-db2/:1)
- [`src/r2-db2/config/`](src/r2-db2/config/:1)
- [`src/r2-db2/graph/`](src/r2-db2/graph/:1)
- [`src/r2-db2/integrations/`](src/r2-db2/integrations/:1)
- [`src/r2-db2/servers/`](src/r2-db2/servers/:1)
- [`src/r2-db2/core/`](src/r2-db2/core/:1)
- [`src/r2-db2/tools/`](src/r2-db2/tools/:1)
- [`src/r2-db2/main.py`](src/r2-db2/main.py:1)

## License

See [`LICENSE`](LICENSE:1) file for details.

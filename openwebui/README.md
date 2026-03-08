# Open WebUI Extensions for R2-DB2 Analytics

## Architecture

The R2-DB2 backend runs a single LangGraph DAG that orchestrates the entire analytical pipeline. These Open WebUI extensions connect to it via two API surfaces:

- **Graph-native API** (primary, default): `POST /api/v1/analyze`, `POST /api/v1/analyze/stream`, `POST /api/v1/approve`
- **OpenAI-compatible API** (fallback): `POST /v1/chat/completions`, `GET /v1/models`

Both are backed by the same LangGraph graph — there is no legacy agent or fallback workflow.

## Files

| File | Type | Version | Description |
|------|------|---------|-------------|
| `pipe_r2_db2_analyst.py` | Pipe Function | 0.2.0 | Custom model routing to R2-DB2 backend (graph-native + OpenAI-compatible) |
| `tool_download_report.py` | Tool | 0.2.0 | List and download report artifacts (PDF, CSV, Parquet, HTML, JSON) |
| `tool_execute_sql.py` | Tool | 0.2.0 | Execute read-only SQL queries via the graph-native API |

## Setup

### 1. Verify Backend is Running

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "environment": "..."}

curl http://localhost:8000/v1/models
# Expected: JSON with model info
```

### 2. Upload R2-DB2 Analyst Pipe

1. Go to **Admin Panel → Functions**
2. Click "+" or "Import"
3. Copy-paste the contents of `pipe_r2_db2_analyst.py`
4. Save the function
5. Click the gear icon → Set Valves:
   - `R2_DB2_API_BASE_URL`: `http://app:8000` (Docker) or `http://localhost:8000` (local)
   - `R2_DB2_API_KEY`: Your API key (default: `sk-r2-db2-dev-key`)
   - `R2_DB2_MODEL_ID`: `r2-db2-analyst`
   - `USE_GRAPH_API`: `True` (recommended) — uses graph-native endpoints
6. Enable the function (toggle on)

### 3. Upload Tools (Optional)

1. Go to **Admin Panel → Tools**
2. Import `tool_download_report.py` — for listing/downloading PDF, CSV, Parquet reports
3. Import `tool_execute_sql.py` — for running read-only SQL queries

Set tool valves:
- `R2_DB2_API_BASE_URL`: same as pipe valve
- `R2_DB2_API_KEY`: same as pipe valve

### 4. Using the Agent

1. Start a new chat
2. Select **"R2-DB2 Analytics Agent"** from the model dropdown
3. Ask data questions like "Show me monthly revenue trends"
4. The agent will:
   - Classify your intent
   - Retrieve schema context
   - Generate and validate SQL
   - Execute the query
   - Generate charts and reports
5. Download reports (PDF, CSV) via the provided links

## API Endpoints Used

| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/api/v1/analyze` | POST | Pipe, SQL Tool | Submit analysis question |
| `/api/v1/analyze/stream` | POST | Pipe (streaming) | Stream analysis progress |
| `/api/v1/approve` | POST | Pipe (HITL) | Approve/reject analysis plan |
| `/api/v1/reports/{id}` | GET | Report Tool | List report artifacts |
| `/api/v1/reports/{id}/{file}` | GET | Report Tool | Download report file |
| `/v1/chat/completions` | POST | Pipe (fallback) | OpenAI-compatible chat |
| `/v1/models` | GET | — | List available models |
| `/health` | GET | — | Health check |

## Troubleshooting

1. **No response**: Check backend logs with `docker compose logs r2-db2-backend`
2. **Connection refused**: Verify `R2_DB2_API_BASE_URL` matches your deployment (Docker service name vs localhost)
3. **Empty results**: The backend may need schema context loaded — check ClickHouse connection
4. **Timeout**: Increase `REQUEST_TIMEOUT` valve (default: 300s for pipe, 120s for SQL tool)

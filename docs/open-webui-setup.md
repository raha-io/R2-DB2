# Open WebUI Integration Setup Guide

This document describes how to set up Open WebUI as the frontend for the R2-DB2 Analytics Agent.

## Architecture Overview

Open WebUI supports **dual-mode operation**:

```
┌─────────────────────┐       ┌─────────────────────┐
│   Open WebUI        │       │   R2-DB2 Backend      │
│   (port 3000)       │──────▶│   (port 8000)        │
│                     │       │                      │
│  - General Chat     │  HTTP │  - /v1/models        │
│  - R2-DB2 Analyst    │◀──────│  - /v1/chat/complete │
│    (Pipe Function)  │       │  - /reports/{id}     │
│  - Tools            │       │  - /api/r2-db2/v2/*   │
│    (Download/SQL)   │       │                      │
└─────────────────────┘       └─────────────────────┘
         ▲
         │
    ┌────┴────┐
    │ OpenRouter │
    │ (or other │
    │  LLM API) │
    └───────────┘
```

### Modes Explained

| Mode | Purpose | Configuration |
|------|---------|---------------|
| **General Chat** | GPT-4, Claude, and other LLMs via OpenRouter | Admin Panel → Settings → Connections |
| **R2-DB2 Analyst** | Data analysis agent via Pipe function | Admin Panel → Functions (upload `pipe_r2_db2_analyst.py`) |
| **Tools** | Report download + SQL execution | Admin Panel → Tools (upload tool files) |

## Prerequisites

- Docker and Docker Compose installed
- Admin account created in Open WebUI
- `docker-compose.dev.yml` running with all services

## Quick Start

### 1. Start all services

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 2. Verify services are running

```bash
# Check R2-DB2 backend health
curl http://localhost:8000/health

# Check Open WebUI (should redirect to login)
curl -I http://localhost:3000

# Check OpenAI-compatible models endpoint
curl http://localhost:8000/v1/models
```

Expected `/v1/models` response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "r2-db2-analyst",
      "object": "model",
      "owned_by": "r2-db2"
    }
  ]
}
```

### 3. Configure OpenRouter (General Models)

1. Open `http://localhost:3000` in your browser
2. Log in with your admin account
3. Go to **Admin Panel → Settings → Connections**
4. Under "OpenAI API", set:
   - Base URL: `https://openrouter.ai/api/v1`
   - API Key: Your OpenRouter API key
5. Click Save

### 4. Upload R2-DB2 Analyst Pipe

1. Go to **Admin Panel → Functions**
2. Click "+" or "Import"
3. Copy-paste the contents of `openwebui/pipe_r2_db2_analyst.py`
4. Save the function
5. Click the gear icon → Set Valves:
   - `R2_DB2_API_BASE_URL`: `http://app:8000/v1` (default)
   - `R2_DB2_MODEL_ID`: `r2-db2-analyst`
6. Enable the function (toggle on)

### 5. Upload Tools (Optional)

1. Go to **Admin Panel → Tools**
2. Import `openwebui/tool_download_report.py` — for downloading PDF/CSV/Parquet reports
3. Import `openwebui/tool_execute_sql.py` — for running read-only SQL queries

### 6. Start chatting

1. Start a new chat
2. Select "R2-DB2 Analyst" from the model dropdown (alongside GPT-4, Claude, etc.)
3. Ask data questions like:
   - "What tables are available in the database?"
   - "Show me total revenue by month for 2024"
   - "Compare sales across regions"

## Integration Methods

Open WebUI connects to R2-DB2 via **two complementary methods**:

### Method A: Direct OpenAI-Compatible Connection (Auto-configured)

The `docker-compose.dev.yml` already configures Open WebUI to connect to the R2-DB2 backend via environment variables:

```yaml
environment:
  - OPENAI_API_BASE_URLS=http://app:8000/v1
  - OPENAI_API_KEYS=sk-r2-db2-dev-key
  - DEFAULT_MODELS=r2-db2-analyst
```

This means the `r2-db2-analyst` model appears automatically in the model picker.

### Method B: Pipe Function (Enhanced Experience)

For richer integration with status indicators and better error handling, upload the Pipe function:

1. Go to **Workspace** → **Functions** in the admin panel
2. Click **+ Create a Function**
3. Set the type to **Pipe**
4. Copy-paste the content of `openwebui/pipe_r2_db2_analyst.py`
5. Save and **Enable** the function
6. Configure **Valves** (click ⚙️ gear icon):
   - `R2_DB2_API_BASE_URL`: `http://app:8000/v1` (default)
   - `R2_DB2_API_KEY`: `sk-r2-db2-dev-key` (default)

### Method C: Tools (Add-on capabilities)

Upload these tools for additional functionality:

#### Download Report Tool
1. Go to **Workspace** → **Tools**
2. Click **+ Create a Tool**
3. Copy-paste `openwebui/tool_download_report.py`
4. Save and enable
5. Attach the tool to your chat via the **+** button

#### Execute SQL Tool
1. Go to **Workspace** → **Tools**
2. Click **+ Create a Tool**
3. Copy-paste `openwebui/tool_execute_sql.py`
4. Save and enable
5. Attach the tool to your chat via the **+** button

## Features Available Through Open WebUI

| Feature | How it works |
|---------|-------------|
| **Natural language queries** | Type questions in the chat, agent generates SQL and analysis |
| **Result tables** | Query results appear as markdown tables in chat |
| **Charts** | Plotly charts are referenced in the response with view links |
| **Report downloads** | Use the Download Report tool or click links in responses |
| **SQL execution** | Use the Execute SQL tool to run custom queries |
| **Conversation history** | Open WebUI stores chat history automatically |
| **Follow-up questions** | Continue chatting to refine analysis |

## Docker Compose Environment Variables

Key environment variables set on the `openwebui` service:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ENABLE_OLLAMA_API` | `false` | Disable Ollama (not used) |
| `OPENAI_API_BASE_URLS` | `http://app:8000/v1` | R2-DB2 backend API URL |
| `OPENAI_API_KEYS` | `sk-r2-db2-dev-key` | API key for R2-DB2 backend |
| `DEFAULT_MODELS` | `r2-db2-analyst` | Default model for new chats |
| `ENABLE_API_KEYS` | `true` | Allow programmatic access |
| `ENABLE_SIGNUP` | `false` | Disable public registration |
| `WEBUI_NAME` | `R2-DB2 Analytics` | Custom UI title |

## Troubleshooting

### Model not showing in Open WebUI
1. Check that the R2-DB2 backend is healthy: `curl http://localhost:8000/health`
2. Check the models endpoint: `curl http://localhost:8000/v1/models`
3. In Open WebUI Admin → Settings → Connections, verify the OpenAI base URL is `http://app:8000/v1`

### "Error connecting to R2-DB2 backend"
1. Ensure both containers are on the same Docker network
2. Check container logs: `docker compose -f docker-compose.dev.yml logs app`
3. Verify the R2-DB2 backend is running on port 8000

### Chat returns empty or error responses
1. Check R2-DB2 backend logs for errors
2. Verify ClickHouse is seeded and accessible
3. Try the internal API directly: `curl -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"r2-db2-analyst","messages":[{"role":"user","content":"Hello"}]}'`

### OpenRouter not working
1. Verify your OpenRouter API key is correct
2. Check that the base URL is `https://openrouter.ai/api/v1`
3. Ensure the connection is enabled in Admin Panel → Settings → Connections

## Testing from Open WebUI

### Prerequisites Checklist

Before testing, ensure:

1. R2-DB2 backend is running (check: `curl http://localhost:8000/v1/models`)
2. Open WebUI is running (default: http://localhost:3000)
3. Pipe is installed in Open WebUI (Admin → Functions → pipe_r2_db2_analyst.py)
4. Pipe valve `R2_DB2_API_BASE_URL` is set to `http://r2-db2-backend:8000` (or your backend URL, WITHOUT `/v1` suffix)

### Test Scenarios

#### Test 1: Basic Question (human-readable answer)

**Prompt:**
```
How many customers do we have?
```

**Expected:** A text answer like "You have 1,234 customers in the database." with possibly a SQL query shown.

**What to check:** You should see actual text content, not just a thinking spinner.

---

#### Test 2: Data Table Response

**Prompt:**
```
Show me the top 10 customers by revenue
```

**Expected:** A markdown table with customer names and revenue figures.

**What to check:** Table renders properly in the chat.

---

#### Test 3: Chart Generation

**Prompt:**
```
Create a bar chart of monthly sales for the last 12 months
```

**Expected:** A chart description or link, plus a text summary of the data.

**What to check:** Chart reference appears in the response.

---

#### Test 4: Report Generation (download link)

**Prompt:**
```
Generate a full report on customer acquisition trends
```

**Expected:** A text summary plus download links for PDF/CSV/HTML artifacts.

**What to check:** Download links are clickable (📥 icons).

---

#### Test 5: Clarification Question

**Prompt:**
```
Show me the data
```

**Expected:** The agent should ask a clarifying question like "Could you specify which data you'd like to see?"

**What to check:** Agent asks for more details instead of guessing.

---

#### Test 6: SQL Execution Tool (if installed)

**Prompt:**
```
Execute this SQL: SELECT count(*) FROM customers
```

**Expected:** Query result with row count.

**What to check:** The execute_sql tool runs and returns results.

### Debugging Tips

- **If you see only a thinking spinner with no response:**
  1. Check backend logs: `docker compose logs r2-db2-backend`
  2. Test the API directly: 
     ```bash
     curl -X POST http://localhost:8000/v1/chat/completions \
       -H "Content-Type: application/json" \
       -d '{"model":"r2-db2-analyst","messages":[{"role":"user","content":"How many customers?"}]}'
     ```
  3. Verify pipe valve URL does NOT end with `/v1` (the pipe adds this automatically)

- **If you see "⚠️ No response received from the analytics backend":**
  1. Backend may be unreachable - check network/docker networking
  2. Check if backend URL is correct in pipe valves

- **If you see "❌ Backend connection error":**
  1. Backend is down or URL is wrong
  2. Check: `curl http://localhost:8000/health` or `curl http://localhost:8000/v1/models`

## File Reference

| File | Purpose |
|------|---------|
| `src/r2-db2/servers/fastapi/openai_models.py` | Pydantic models for OpenAI-compatible API |
| `src/r2-db2/servers/fastapi/openai_routes.py` | OpenAI-compatible route handlers |
| `src/r2-db2/servers/fastapi/app.py` | FastAPI app (registers OpenAI routes) |
| `docker-compose.dev.yml` | Docker services including Open WebUI config |
| `openwebui/pipe_r2_db2_analyst.py` | Pipe function for enhanced Open WebUI integration |
| `openwebui/tool_download_report.py` | Tool for downloading reports |
| `openwebui/tool_execute_sql.py` | Tool for executing SQL queries |

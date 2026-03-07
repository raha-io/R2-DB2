# Open WebUI Extensions for R2-DB2 Analytics

## Architecture
- **General Chat Models**: Open WebUI connects to OpenRouter (or any OpenAI-compatible API) for GPT-4, Claude, etc.
- **R2-DB2 Analyst Model**: A Pipe function that appears as an additional model in the selector. Routes to the R2-DB2 backend API independently.
- **Tools**: Report download and SQL execution tools that work with the R2-DB2 Analyst.

## Setup Steps

### 1. Configure OpenRouter (General Models)
1. Log in as admin at `http://localhost:3000`
2. Go to **Admin Panel → Settings → Connections**
3. Under "OpenAI API", set:
   - Base URL: `https://openrouter.ai/api/v1`
   - API Key: Your OpenRouter API key
4. Click Save

### 2. Upload R2-DB2 Analyst Pipe
1. Go to **Admin Panel → Functions**
2. Click "+" or "Import"
3. Copy-paste the contents of `pipe_r2_db2_analyst.py`
4. Save the function
5. Click the gear icon on the function → Set Valves:
   - `R2_DB2_API_BASE_URL`: `http://app:8000/v1` (default, works inside Docker)
   - `R2_DB2_MODEL_ID`: `r2-db2-analyst`
6. Enable the function (toggle on)

### 3. Upload Tools (Optional)
1. Go to **Admin Panel → Tools**
2. Import `tool_download_report.py` — for downloading PDF/CSV/Parquet reports
3. Import `tool_execute_sql.py` — for running read-only SQL queries

### 4. Using the Agent
1. Start a new chat
2. Select "R2-DB2 Analyst" from the model dropdown (alongside GPT-4, Claude, etc.)
3. Ask data questions like "Show me monthly revenue trends"
4. The agent will generate SQL, execute it, and show charts/tables
5. Ask follow-up questions to refine the analysis

## Files
| File | Type | Description |
|------|------|-------------|
| `pipe_r2_db2_analyst.py` | Pipe Function | Custom model routing to R2-DB2 backend |
| `tool_download_report.py` | Tool | List and download report artifacts |
| `tool_execute_sql.py` | Tool | Execute read-only SQL via R2-DB2 |

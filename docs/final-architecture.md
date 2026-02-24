# Final Technical Architecture: ClickHouse Analytical Agent

## Section 1: Executive Summary
The ClickHouse Analytical Agent is a production-grade system for generating audited, repeatable analytical reports and interactive insights over ClickHouse for data teams and business stakeholders, built on a deterministic LangGraph state machine with pluggable components and strict security isolation between query execution and sandboxed analysis; this architecture prioritizes predictable execution, durable state, and controlled tool use while enabling swappable infrastructure (LLM providers, vector store, sandbox, and storage) through interface-based design.

## Section 2: Revised Technology Stack
| Layer | Component | Technology | Rationale |
|---|---|---|---|
| Frontend | Chat UI | FastAPI + WebSocket + React | Full control over HITL workflows, streaming, interactive charts |
| Orchestration | State Machine | LangGraph | DAG execution, persistence, HITL interrupts, durable execution |
| LLM Gateway | Multi-Provider | LiteLLM | Provider fallback, cost tracking, model routing |
| Schema Intelligence | Vector Store | Qdrant | Semantic schema search, historical query pairs, few-shot examples |
| Data Warehouse | Analytical DB | ClickHouse | Columnar storage, high-speed aggregations |
| Code Sandbox | Ephemeral Execution | E2B | Isolated microVMs for data science code |
| Observability | Tracing | OpenTelemetry + Grafana | Distributed tracing, metrics, alerting |
| Storage | State & Artifacts | PostgreSQL + S3 | Conversation history, generated reports, checkpoints |
| Cache | Query Results | Redis | TTL-based caching of query results and schema metadata |

## Section 3: System Architecture Diagram
```
User → FastAPI → LangGraph State Machine → [Planner → HITL → Context → SQL Gen → SQL Exec → Analysis → Report]
                                              ↕           ↕         ↕          ↕
                                           LiteLLM     Qdrant   ClickHouse    E2B
                                              ↕
                                        OpenTelemetry → Grafana
```

## Section 4: LangGraph Execution Graph (Revised)
**Node 1: Intent Classification**
- **Input (from state):** `messages`, `conversation_id`, `user_id`
- **Output (to state):** `intent`
- **Error handling:** On classification failure, default to `clarification` and append a system message requesting additional context; log and proceed with safe path.
- **Uses LLM:** Yes (lightweight, low-cost model).

**Node 2: Planning**
- **Input (from state):** `messages`, `intent`, `schema_context` (retrieved), `historical_queries`
- **Output (to state):** `plan`, `estimated_cost_usd`, `total_llm_tokens`
- **Error handling:** If structured JSON parse fails, retry once with schema-constrained decoding; on repeat failure route to HITL with a draft plan.
- **Uses LLM:** Yes (structured output).

**Node 3: Human Approval (HITL)**
- **Input (from state):** `plan`, `estimated_cost_usd`, `intent`
- **Output (to state):** `plan_approved` (true/false) and optionally a modified `plan`
- **Error handling:** If user rejects, terminate with a structured response and store rejection reason in memory; if timeout, suspend via checkpointer and resume on user action.
- **Uses LLM:** No (UI-driven).

**Node 4: SQL Generation**
- **Input (from state):** `plan`, `schema_context`, `historical_queries`, `messages`
- **Output (to state):** `generated_sql`, `sql_validation_errors`
- **Error handling:** Validate SQL; if errors, regenerate with explicit error feedback; increment `sql_retry_count`.
- **Uses LLM:** Yes (SQL generation + repair).

**Node 5: SQL Execution**
- **Input (from state):** `generated_sql`, `sql_retry_count`
- **Output (to state):** `query_results`, `execution_time_ms`
- **Error handling:** On execution failure, capture error, route back to SQL Generation with error context; max 3 attempts, then surface to HITL.
- **Uses LLM:** No (execution is deterministic).

**Node 6: Data Analysis (Sandboxed)**
- **Input (from state):** `query_results` (path to `.parquet`), `plan`
- **Output (to state):** `analysis_artifacts`, `sandbox_id`
- **Error handling:** If sandbox fails or times out, retry once; on failure return partial results and mark artifacts as degraded.
- **Uses LLM:** Optional (for narrative scaffolding); code execution is deterministic in E2B.

**Node 7: Report Assembly**
- **Input (from state):** `analysis_artifacts`, `plan`, `messages`
- **Output (to state):** `report`, `output_format`
- **Error handling:** If chart rendering fails, fallback to tabular summaries and text; preserve artifacts for download.
- **Uses LLM:** Yes (summary synthesis and formatting).

**Node 8: Memory Update**
- **Input (from state):** `messages`, `plan`, `generated_sql`, `query_results`, `report`
- **Output (to state):** persisted memory records and updated `historical_queries`
- **Error handling:** Memory write failure should not block response; log and continue.
- **Uses LLM:** No (store structured records).

## Section 5: State Design
```python
class AnalyticalAgentState(TypedDict):
    # Conversation
    messages: list[BaseMessage]
    conversation_id: str
    user_id: str

    # Intent
    intent: Literal["new_analysis", "follow_up", "clarification", "off_topic"] | None

    # Planning
    plan: AnalysisPlan | None  # Structured JSON plan
    plan_approved: bool

    # Schema Context
    schema_context: list[SchemaDocument]  # From Qdrant
    historical_queries: list[QueryPair]  # Similar past queries

    # SQL
    generated_sql: str | None
    sql_validation_errors: list[str]
    sql_retry_count: int

    # Execution
    query_results: QueryResult | None  # Metadata + path to .parquet
    execution_time_ms: int | None

    # Analysis
    analysis_artifacts: list[Artifact]  # Charts, tables, insights
    sandbox_id: str | None

    # Output
    report: Report | None
    output_format: Literal["interactive", "pdf", "csv", "all"]

    # Metadata
    total_llm_tokens: int
    estimated_cost_usd: float
    trace_id: str
```

- **Conversation fields** provide the durable multi-turn context used by planning, generation, and report synthesis while tying the request to a stable `conversation_id` and `user_id` for persistence and audit.
- **Intent fields** determine routing across the graph (e.g., clarification vs. new analysis) and ensure predictable control flow.
- **Planning fields** capture the structured plan and its approval status to enforce HITL gating before any execution.
- **Schema context fields** hold semantically retrieved schema documents and similar historical queries to ground SQL generation and reduce hallucinations.
- **SQL fields** capture the latest generated SQL, validation errors, and retry budget to implement bounded correction loops.
- **Execution fields** store the results artifact and timing metadata needed for observability and report generation.
- **Analysis fields** capture sandbox-produced artifacts and the sandbox session for lifecycle management.
- **Output fields** store the assembled report and target formats to drive streaming and downloads.
- **Metadata fields** track per-request cost and observability correlation via `trace_id`.

## Section 6: Component Interface Design
```python
class LLMProvider(Protocol):
    async def generate(self, messages, tools, model) -> LLMResponse: ...
    async def generate_structured(self, messages, schema, model) -> dict: ...

class SchemaStore(Protocol):
    async def search_schemas(self, query, top_k) -> list[SchemaDocument]: ...
    async def get_table_schema(self, table_name) -> TableSchema: ...
    async def index_schema(self, schema) -> None: ...

class SQLRunner(Protocol):
    async def execute(self, sql, params) -> QueryResult: ...
    async def validate(self, sql) -> list[str]: ...
    async def explain(self, sql) -> QueryPlan: ...

class CodeSandbox(Protocol):
    async def create(self, timeout_seconds) -> SandboxSession: ...
    async def execute_code(self, session, code, files) -> ExecutionResult: ...
    async def destroy(self, session) -> None: ...

class ConversationMemory(Protocol):
    async def get_history(self, conversation_id) -> list[BaseMessage]: ...
    async def save_turn(self, conversation_id, messages) -> None: ...
    async def get_similar_queries(self, query, top_k) -> list[QueryPair]: ...
```

These interfaces provide a registry-friendly abstraction layer so concrete implementations (e.g., LiteLLM vs. direct provider SDKs, Qdrant vs. a SQL-backed schema index, ClickHouse vs. another analytical backend, or E2B vs. a self-hosted sandbox) can be swapped by configuration without rewriting orchestration logic. The design mirrors the R2-DB2 registry pattern, enabling environment-specific deployments, mock-based testing, and future migrations while keeping the LangGraph node logic stable.

## Section 7: Security Architecture
### 7.1 Credential Isolation
ClickHouse credentials, LLM API keys, and Qdrant tokens reside only in the host environment and are never injected into the E2B sandbox. The sandbox receives data exclusively as materialized `.parquet` files produced by the SQL execution node, ensuring untrusted code cannot access live database connections. This enforces a strict data boundary between query execution and analysis.

### 7.2 SQL Injection Prevention
All LLM-generated SQL passes through a validation layer before execution. The validator rejects DDL (CREATE, DROP, ALTER, TRUNCATE) and DML (INSERT, UPDATE, DELETE), enforces read-only SELECT statements only, applies row-limit guards (for example, appending or validating `LIMIT 10000`), and checks every referenced table/schema against a whitelist of allowed objects. Invalid queries are returned to the SQL generation node with explicit error feedback for correction.

### 7.3 Sandbox Security
E2B sandboxes run as ephemeral microVMs with no network access to internal infrastructure and no access to credentials or secrets. Each sandbox has a hard timeout of 5 minutes and a 2GB memory limit to constrain resource usage. Sandboxes are destroyed immediately after artifact extraction to eliminate persistence risk.

### 7.4 User Authentication & Authorization
Requests are authenticated with JWTs and authorized via role-based access control with roles such as viewer, analyst, and admin. Per-user query quotas are enforced at the API layer to prevent abuse and bound cost. Authorization rules also gate which schemas and tables can be queried per user or role.

### 7.5 Data Classification
ClickHouse columns can be tagged as PII or sensitive, and these tags are enforced in context retrieval and prompt assembly. Sensitive fields are automatically redacted from LLM context and report outputs unless the requesting user has explicit privileges. This prevents leakage of regulated data through prompts, logs, or model outputs.

## Section 8: Observability & Monitoring
### 8.1 OpenTelemetry Integration
Every LangGraph node emits OpenTelemetry spans with a shared trace context. The trace structure for an analytical request is:
```
trace: analytical_request
├── span: intent_classification (llm_call)
├── span: planning (llm_call)
├── span: human_approval (interrupt)
├── span: sql_generation (llm_call)
├── span: sql_execution (clickhouse_query)
├── span: data_analysis (e2b_sandbox)
├── span: report_assembly
└── span: memory_update
```
This makes latency and error attribution visible across LLM calls, ClickHouse queries, and sandbox execution.

### 8.2 Key Metrics
- `agent.request.duration_ms` — End-to-end request time
- `agent.llm.tokens_used` — Per-call and per-request token usage
- `agent.llm.cost_usd` — Per-call cost
- `agent.sql.execution_time_ms` — ClickHouse query time
- `agent.sql.retry_count` — SQL correction attempts
- `agent.sandbox.duration_ms` — E2B execution time
- `agent.hitl.wait_time_ms` — Time waiting for human approval

### 8.3 Alerting Rules
- SQL retry count > 3 → alert (LLM struggling with schema)
- Request duration > 120s → alert (potential hang)
- LLM cost per request > $2 → alert (cost anomaly)
- Sandbox timeout → alert (code execution issue)

### 8.4 Structured Logging
All services emit JSON logs that include `trace_id`, `user_id`, and `conversation_id` so that logs can be correlated with traces. Each node logs inputs, outputs, latency, and error details to support auditability and rapid debugging. Logs are forwarded to a centralized aggregator alongside OpenTelemetry traces.

## Section 9: Evaluation Framework
### 9.1 SQL Accuracy Evaluation
Generated SQL is compared against a golden dataset of question→SQL pairs. Metrics include exact string match, execution match (same results), and partial match for structurally similar queries. This detects regressions when prompts or models change.

### 9.2 Report Quality Evaluation
Reports are scored by an LLM-as-judge rubric on relevance, accuracy, completeness, and clarity. Each dimension is rated on a 1–5 scale and aggregated into a composite quality score. Low-scoring reports trigger prompt review or sample-based human review.

### 9.3 End-to-End Evaluation Pipeline
```
Golden Dataset → Agent → Generated Output → Evaluators → Score Report
```
The pipeline runs batch evaluations and produces a versioned score report tied to prompt and model versions.

### 9.4 Continuous Evaluation
The evaluation suite runs on every prompt change, model change, or schema change. Scores are tracked over time to identify drift, and thresholds are enforced to block releases that regress beyond tolerance. Results are stored for trend analysis.

### 9.5 User Feedback Loop
Users can thumbs up/down generated reports. Feedback is added to the evaluation dataset and stored in Qdrant so successful query pairs become few-shot examples for future prompts. Negative feedback drives targeted test cases and prompt fixes.

## Section 10: Error Handling Strategy
### 10.1 Error Taxonomy
| Error Type | Example | Strategy | Max Retries |
|---|---|---|---|
| Transient | Network timeout, rate limit | Exponential backoff | 3 |
| LLM-Recoverable | Invalid SQL syntax | Feed error back to LLM | 3 |
| Schema | Table not found | Re-fetch schema from Qdrant, retry | 1 |
| Sandbox | Code execution error | Feed error + traceback to LLM | 2 |
| User-Fixable | Ambiguous request | `interrupt()` asking for clarification | N/A |
| Fatal | ClickHouse down | Graceful error message, alert ops | 0 |

### 10.2 Transient Errors
Transient failures are retried with exponential backoff to avoid thundering herds. Each retry is logged with the same trace context for visibility. After the final retry, the error is surfaced with a clear message and a request ID.

### 10.3 LLM-Recoverable Errors
Invalid SQL syntax or malformed outputs are fed back to the LLM with the exact error message and a corrected schema context. The SQL generation node increments `sql_retry_count` and regenerates within the retry budget. If retries are exhausted, the request is routed to HITL with the failing SQL and error details.

### 10.4 Schema Errors
If a table or column is not found, the system re-fetches schema context from Qdrant and optionally from ClickHouse metadata. The SQL generation node retries once with updated schema context. Persistent schema errors result in a user-facing explanation and a request for clarification.

### 10.5 Sandbox Errors
Sandbox execution errors capture the traceback and the executed code, which are fed back to the LLM to attempt a repair. The sandbox is re-created for each retry to avoid contaminated state. If a second attempt fails, the system returns partial results and marks the analysis as degraded.

### 10.6 User-Fixable Errors
Ambiguous requests or missing filters trigger a HITL `interrupt()` to ask the user for clarification. The request is paused with durable state so it can resume exactly where it stopped. The clarified input is appended to the conversation and re-enters the planning node.

### 10.7 Fatal Errors
Fatal errors such as ClickHouse outages terminate the pipeline immediately with a structured error response and a request ID. An alert is sent to operations for investigation. No retries are attempted to avoid cascading failures.

## Section 11: Deployment Architecture
### 11.1 Container Structure
```
docker-compose:
  - api-server (FastAPI + LangGraph)
  - worker (async task processing)
  - redis (cache + message broker)
  - postgres (state + conversations)
  - qdrant (vector store)
  - grafana + otel-collector (observability)
```

### 11.2 Scaling Strategy
The API server scales horizontally behind a load balancer, while workers scale based on queue depth and task latency. ClickHouse and Qdrant run as external managed services to decouple core scaling from infrastructure ops. Redis and Postgres are deployed in highly available configurations.

### 11.3 Environment Configuration
All secrets are injected via environment variables or Vault, never hardcoded in code or images. Per-environment configuration (dev/staging/prod) is stored in config files with explicit overrides for endpoints, quotas, and model routing. Configuration changes are versioned and auditable.

## Section 12: Implementation Roadmap
### 12.1 Phase Summary
| Phase | Duration | Deliverables |
|---|---|---|
| Phase 1: Foundation | 3 weeks | LangGraph core graph, ClickHouse integration, FastAPI endpoint, LiteLLM setup |
| Phase 2: Intelligence | 2 weeks | Qdrant schema indexing, few-shot retrieval, conversation memory, multi-turn context |
| Phase 3: Analysis | 2 weeks | E2B sandbox integration, analysis node, Plotly chart generation, report assembly |
| Phase 4: Production | 2 weeks | HITL approval flow, OpenTelemetry tracing, error recovery, evaluation framework |
| Phase 5: Polish | 1 week | React frontend, streaming output, PDF/CSV export, cost tracking, documentation |

### 12.2 Phase 1: Foundation
- LangGraph graph with intent → plan → SQL gen → SQL exec nodes
- ClickHouse SQL runner integration and `.parquet` materialization
- FastAPI endpoint with request/response schema
- LiteLLM configuration with base model routing

### 12.3 Phase 2: Intelligence
- Qdrant schema indexing and retrieval pipeline
- Few-shot query retrieval based on historical pairs
- Conversation memory store with retrieval hooks
- Multi-turn context injection into planning and SQL generation

### 12.4 Phase 3: Analysis
- E2B sandbox integration with timeout and memory limits
- Data analysis node producing charts and tables
- Plotly chart generation and artifact packaging
- Report assembly pipeline for narrative + visuals

### 12.5 Phase 4: Production
- HITL approval flow with durable checkpointer
- OpenTelemetry tracing and metrics emission
- Unified error recovery taxonomy and routing
- Evaluation framework with golden dataset and reports

### 12.6 Phase 5: Polish
- React frontend with progress and artifact display
- Streaming output and partial result updates
- PDF/CSV export and download management
- Cost tracking, audit trail, and documentation

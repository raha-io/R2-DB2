# Final Architecture v2 — ClickHouse Analytical Agent

## Part 1: Product Features

### Section 1: Product Vision
The ClickHouse Analytical Agent is a multi-agent analytical system for data scientists that turns natural language questions into audited, reproducible analytical reports backed by ClickHouse. It is designed to handle real analytical workflows: iterative exploration, anomaly detection, hypothesis testing, and visualization, not just one-shot SQL answers. The system prioritizes deterministic execution, strict security boundaries, and operational observability so that every result can be trusted and traced.

The product is built around a feature-first philosophy: define what the system must do, then implement an architecture that delivers those features with clear agent boundaries. The architecture uses LangGraph for deterministic orchestration, ClickHouse for analytical execution, Qdrant for semantic schema retrieval and historical query pairs, and a sandboxed smolagents `CodeAgent` for analysis and visualization. It adopts proven R2-DB2 patterns—registry, middleware, audit, evaluation, observability, recovery, and lifecycle—without requiring the R2-DB2 library itself, following the structure in [`src/r2-db2/core/registry.py`](src/r2-db2/core/registry.py) and related core interfaces.

The system is also production-oriented: it supports multi-tenant isolation, caching, error recovery, and continuous evaluation. It integrates optionally with Open WebUI as a frontend but remains a backend-first system with clean APIs and portable components.

### Section 2: Feature Catalog

#### Data Querying
| Feature | Description | Priority |
|---|---|---|
| Intent-to-SQL Planning | Produce a structured analysis plan with required tables, metrics, and filters before any execution. | P0 |
| Schema Retrieval | Retrieve relevant schema and column context via Qdrant; fallback to ClickHouse `system.columns` if needed. | P0 |
| SQL Generation & Validation | Generate read-only SQL, validate against allowlist, enforce limits and safe operations. | P0 |
| SQL Execution | Execute validated SQL in ClickHouse and materialize results to `.parquet`. | P0 |
| Multi-Query Expansion | Propose follow-up queries (drill-downs, comparisons, anomaly slices) based on results. | P0 |
| Cost Estimation | Estimate query cost and surface it during approval. | P1 |
| Schema Change Detection | Detect schema drift and re-index Qdrant; invalidate caches. | P1 |

#### Analysis & Insights
| Feature | Description | Priority |
|---|---|---|
| Sandboxed Code Execution | Run analysis in an ephemeral sandbox using smolagents `CodeAgent`. | P0 |
| Statistical Summaries | Compute aggregates, distributions, correlations, and trends. | P0 |
| Anomaly Detection | Detect outliers and unexpected shifts using programmatic analysis. | P0 |
| Hypothesis Testing | Support t-tests, chi-square, and regression-style checks. | P1 |
| Programmatic Tool Calling | CodeAgent can call host tools from within code (e.g., `query_database`) for multi-step analysis without extra LLM tokens. | P0 |
| Artifact Packaging | Produce charts, tables, and structured insight artifacts. | P0 |

#### Reporting
| Feature | Description | Priority |
|---|---|---|
| Analytical Report Assembly | Combine narrative, charts, and statistical summaries into a full report. | P0 |
| Output Formats | PDF, interactive Plotly HTML, CSV/Parquet, JSON summary (default: all). | P0 |
| Partial Results Streaming | Stream intermediate findings to frontend during execution. | P1 |
| Report Versioning | Store report metadata with schema snapshot and prompt versions. | P1 |

#### Conversation
| Feature | Description | Priority |
|---|---|---|
| Multi-Turn Context | Persist conversation state across turns and sessions. | P0 |
| Follow-Up Resolution | Allow follow-up questions to reuse previous results and `.parquet` artifacts. | P0 |
| HITL Approval | Human approval gate before expensive queries or sandbox execution. | P0 |

#### Security
| Feature | Description | Priority |
|---|---|---|
| Credential Isolation | Keep ClickHouse credentials on host; sandbox receives no secrets. | P0 |
| SQL Injection Prevention | Enforce read-only SQL, table allowlists, and LIMIT guards. | P0 |
| Sandbox Isolation | Ephemeral sandbox with no network access to internal services. | P0 |
| Tenant Isolation | Per-tenant access controls and quotas. | P1 |

#### Operations
| Feature | Description | Priority |
|---|---|---|
| Observability | OpenTelemetry traces, metrics, and structured logs. | P0 |
| Audit Trail | Record all LLM calls, SQL executions, tool calls, and approvals. | P0 |
| Evaluation Framework | Continuous evaluation of SQL accuracy and report quality. | P0 |
| Error Recovery | Error taxonomy with retries and escalation paths. | P0 |
| Caching | Query cache, schema cache, and artifact reuse. | P1 |
| Multi-Model Routing | LiteLLM routing with fallback providers. | P1 |

---

## Part 2: Architecture

### Section 3: Technology Stack
| Component | Technology | Rationale |
|---|---|---|
| Orchestration | LangGraph | Deterministic DAG, HITL interrupts, checkpointing, streaming. See [docs.langchain.com](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph). |
| LLM Routing | LiteLLM | Unified API, fallback routing, cost tracking. |
| Schema Retrieval | Qdrant | Semantic retrieval of schemas + historical query pairs. |
| Data Warehouse | ClickHouse | Columnar analytics with high-performance aggregation. |
| Sandbox | E2B (via smolagents CodeAgent) | Ephemeral isolated execution for untrusted analysis code. See [huggingface.co](https://huggingface.co/docs/smolagents/en/index). |
| Code Agent | smolagents `CodeAgent` | Rich Python control flow and tool execution inside sandbox. |
| Visualization | Plotly | Interactive charts and report artifacts. |
| State & Metadata | PostgreSQL | LangGraph checkpoints, conversation state, audit, eval results. |
| Cache | Redis | Query cache and schema cache with TTL. |
| Observability | OpenTelemetry + Grafana/Tempo | Distributed tracing and metrics. |
| Frontend | Open WebUI (optional) | Preferred chat UI; backend works independently. |

### Section 4: System Architecture Diagram (Text-Based)
```
User / API Client
   │
   ▼
API Gateway / Server (FastAPI)
   │
   ▼
LangGraph Orchestrator
   │
   ├─► Context Retrieval (Qdrant + schema cache)
   │
   ├─► Plan + HITL Approval
   │
   ├─► SQL Generation + Validation
   │
   ├─► SQL Execution (ClickHouse) ──► .parquet artifact
   │
   ├─► Analysis (Sandbox) — smolagents CodeAgent in E2B
   │        └─► Programmatic tool calls to host (query_database)
   │
   ├─► Report Assembly + Output Packaging
   │
   └─► Memory Update + Audit + Observability

External Services:
  - LiteLLM (model routing)
  - Qdrant (schema + query pairs)
  - ClickHouse (analytics)
  - E2B (sandbox)
  - Postgres/Redis (state + cache)
  - OpenTelemetry (traces/metrics)
```

### Section 5: Agent Roles
| Agent/Node | Responsibility | Input | Output | Uses LLM | Runs in Sandbox |
|---|---|---|---|---|---|
| Intent Classifier | Classify request type (new analysis, follow-up, clarification) | Messages, memory | Intent label | Yes | No |
| Context Retriever | Retrieve schema + historical query pairs | Intent, user query | Schema context, few-shot pairs | Optional | No |
| Planner | Produce structured plan and cost estimate | Query + schema context | Analysis plan | Yes | No |
| HITL Gate | User approval/edits | Plan + cost | Approved plan or rejection | No | No |
| SQL Generator | Generate SQL from plan | Plan + schema context | SQL + validation errors | Yes | No |
| SQL Executor | Run SQL, materialize `.parquet` | SQL | QueryResult + artifact path | No | No |
| CodeAgent (Analysis) | Statistical analysis, charts, anomaly detection | `.parquet`, plan, parameters | Analysis artifacts + insight JSON | Yes | **Yes** |
| Report Assembler | Narrative + charts + export packaging | Artifacts + plan | Report + output formats | Yes | No |
| Memory Updater | Persist conversation and query pairs | Messages + outputs | Memory records | No | No |
| Audit/Observability | Record events + metrics | All node inputs/outputs | Logs + traces | No | No |

### Section 6: Execution Graph (LangGraph DAG)
**Nodes**
1. `intent_classify`
2. `context_retrieve`
3. `plan`
4. `hitl_approval`
5. `sql_generate`
6. `sql_execute`
7. `analysis_sandbox`
8. `report_assemble`
9. `memory_update`
10. `final_response`

**Edges**
- `START → intent_classify → context_retrieve → plan → hitl_approval`
- If `plan_approved == false`: `hitl_approval → final_response` (rejected)
- If `plan_approved == true`: `hitl_approval → sql_generate → sql_execute → analysis_sandbox → report_assemble → memory_update → final_response`

**Conditional Routing**
- If `intent == clarification`: route `intent_classify → hitl_approval` (clarifying questions only).
- If `sql_execute` fails: route to `sql_generate` with error context (bounded retry).
- If `analysis_sandbox` fails: retry once, then mark degraded and continue to `report_assemble`.

**Multi-Query Expansion Loop**
- After `analysis_sandbox`, generate `followup_candidates`.
- If `followup_candidates` present: route to `hitl_approval` with proposed queries.
- On approval, loop back to `sql_generate` with selected follow-up query + cached context.
- On rejection, continue to `report_assemble`.

### Section 7: State Design (TypedDict)
```python
from typing import TypedDict, Literal, Any

class AnalyticalAgentState(TypedDict):
    # Conversation
    conversation_id: str
    user_id: str
    messages: list[dict[str, Any]]

    # Intent + Planning
    intent: Literal["new_analysis", "follow_up", "clarification", "off_topic"] | None
    plan: dict[str, Any] | None
    plan_approved: bool

    # Context
    schema_context: list[dict[str, Any]]
    historical_queries: list[dict[str, Any]]

    # SQL
    generated_sql: str | None
    sql_validation_errors: list[str]
    sql_retry_count: int

    # Execution
    query_result: dict[str, Any] | None  # includes parquet_path
    execution_time_ms: int | None

    # Analysis
    analysis_artifacts: list[dict[str, Any]]
    sandbox_id: str | None

    # Multi-query expansion
    followup_candidates: list[dict[str, Any]]
    approved_followups: list[dict[str, Any]]

    # Output
    report: dict[str, Any] | None
    output_formats: list[Literal["pdf", "plotly_html", "csv", "parquet", "json"]]

    # Metadata
    total_llm_tokens: int
    estimated_cost_usd: float
    trace_id: str
```
**Field notes**
- `schema_context` and `historical_queries` follow the retrieval patterns used in [`src/r2-db2/integrations/qdrant/agent_memory.py`](src/r2-db2/integrations/qdrant/agent_memory.py).
- `sql_validation_errors` and `sql_retry_count` enable bounded recovery as in [`src/r2-db2/core/recovery/base.py`](src/r2-db2/core/recovery/base.py).
- `analysis_artifacts` mirror artifact packaging in [`src/r2-db2/integrations/plotly/chart_generator.py`](src/r2-db2/integrations/plotly/chart_generator.py).
- `trace_id` is required for OpenTelemetry correlation, following [`src/r2-db2/core/observability/base.py`](src/r2-db2/core/observability/base.py).

### Section 8: CodeAgent & Sandbox Design
**Purpose**: Provide a secure environment for Python-based analysis (statistics, anomaly detection, Plotly visualization) without exposing database credentials.

**Agent**: smolagents `CodeAgent` runs **only** inside the sandbox. It is not the orchestrator and does not control the LangGraph DAG. The host launches the agent with an explicit tool set and returns structured artifacts.

**Programmatic Tool Calling Pattern**
- The CodeAgent generates Python code that calls host-side tools via an RPC bridge.
- Example tools exposed to the sandbox:
  - `query_database(sql: str) -> DataFrameSummary`
  - `load_parquet(path: str) -> DataFrame`
  - `save_artifact(obj, name: str, format: str) -> ArtifactRef`
  - `emit_metric(name: str, value: float, labels: dict)`
- This pattern reduces LLM token usage and latency for multi-step workflows because code can loop, branch, and reuse tools without repeated LLM calls.

**Sandbox Security**
- No credentials in sandbox; all secrets remain on host.
- Network access restricted to the tool bridge; no direct ClickHouse access.
- Ephemeral lifecycle: created per run, destroyed on completion.
- Resource limits: 5–10 min timeout, 2–4 GB RAM, disk quota.

**Artifacts**
- Charts saved as Plotly HTML and PNG snapshots.
- Tables saved as CSV/Parquet.
- Summary JSON emitted with key metrics and findings.

### Section 9: Multi-Query Expansion
1. The analysis node proposes follow-up queries based on detected anomalies or summary deltas.
2. The system presents these in the HITL step with estimated cost and expected insight value.
3. Approved follow-ups are executed via the SQL generation path; rejected ones are logged for context but not executed.
4. Results are merged into the final report with provenance linking to the follow-up query ID.
5. The loop is bounded by a max-followup count and budget to avoid runaway execution.

### Section 10: Component Interfaces (Python Protocols)
```python
from typing import Protocol, Any, Iterable

class LLMRouter(Protocol):
    async def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, model: str) -> dict[str, Any]: ...
    async def generate_structured(self, messages: list[dict[str, Any]], schema: dict[str, Any], model: str) -> dict[str, Any]: ...

class SQLRunner(Protocol):
    async def validate(self, sql: str) -> list[str]: ...
    async def explain(self, sql: str) -> dict[str, Any]: ...
    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...

class SchemaStore(Protocol):
    async def search(self, query: str, top_k: int) -> list[dict[str, Any]]: ...
    async def get_table(self, table_name: str) -> dict[str, Any]: ...
    async def index_schema(self, docs: Iterable[dict[str, Any]]) -> None: ...

class CodeSandbox(Protocol):
    async def create(self, timeout_seconds: int, memory_mb: int) -> str: ...
    async def run_code(self, sandbox_id: str, code: str, files: list[str]) -> dict[str, Any]: ...
    async def destroy(self, sandbox_id: str) -> None: ...

class ConversationMemory(Protocol):
    async def load_history(self, conversation_id: str) -> list[dict[str, Any]]: ...
    async def save_turn(self, conversation_id: str, messages: list[dict[str, Any]]) -> None: ...
    async def get_similar_queries(self, query: str, top_k: int) -> list[dict[str, Any]]: ...
```
These interfaces follow the registry pattern in [`src/r2-db2/core/registry.py`](src/r2-db2/core/registry.py) so that components can be swapped by configuration without code changes.

---

## Part 3: Production Concerns

### Section 11: Security Architecture
- **Credential Isolation**: ClickHouse credentials remain on host. Sandbox never receives secrets.
- **SQL Injection Prevention**: Validate generated SQL against allowlist and read-only rules; enforce LIMIT guards; disallow DDL/DML.
- **Sandbox Security**: Ephemeral microVM, no inbound network, constrained filesystem, strict time/memory limits.
- **Authentication & Authorization**: JWT + RBAC; tenant-based access control for schema and query permissions.
- **Data Classification**: Tag columns as PII/sensitive; redact or mask unless authorized.

### Section 12: Observability & Monitoring
- **Tracing**: OpenTelemetry spans per node with shared `trace_id`.
- **Metrics**: LLM tokens, cost, ClickHouse latency, sandbox runtime, HITL wait time.
- **Structured Logging**: JSON logs with user_id, conversation_id, plan_id, and SQL hash.
- **Dashboards**: Grafana/Tempo dashboards for latency percentiles and error rates.

### Section 13: Evaluation Framework
- **SQL Accuracy**: Golden dataset and evaluators mirroring [`src/r2-db2/core/evaluation/`](src/r2-db2/core/evaluation/).
- **Report Quality**: LLM-as-judge rubric with human review sampling.
- **End-to-End Testing**: Run full pipeline per release to detect regressions.
- **Continuous Eval**: Trigger on schema or prompt changes; store scores with prompt versions.

### Section 14: Error Handling Strategy
| Error Type | Example | Handling | Retry Budget |
|---|---|---|---|
| Transient | Network timeouts | Exponential backoff | 3 |
| LLM-Recoverable | Invalid SQL syntax | Retry with error context | 2 |
| Schema | Table not found | Re-fetch schema, retry | 1 |
| Sandbox | Code exception | Retry with traceback | 1 |
| User-Fixable | Ambiguous request | HITL clarification | N/A |
| Fatal | ClickHouse down | Fail fast + alert | 0 |

### Section 15: Caching Strategy
- **Query Cache**: SQL hash → result artifact, TTL-based.
- **Schema Cache**: Qdrant results cached per tenant; invalidated on schema change detection.
- **Artifact Reuse**: Reuse `.parquet` and analysis artifacts for follow-up queries to avoid re-execution.

### Section 16: Output Formats
Default output includes **PDF + Plotly HTML + CSV/Parquet + JSON summary**. Reports are stored with versioned metadata and linked to the source plan and SQL for auditability.

---

## Part 4: Deployment & Roadmap

### Section 17: Deployment Architecture
- **Containers**: API server, LangGraph worker, Redis cache, Postgres state, Qdrant, OpenTelemetry collector.
- **Scaling**: API nodes scale horizontally; worker pool scales by queue depth.
- **Config**: All secrets via environment or Vault; multi-tenant configs loaded at runtime.

### Section 18: Implementation Roadmap
| Phase | Duration | Deliverables |
|---|---|---|
| Phase 1: Foundation | 3 weeks | LangGraph DAG, ClickHouse SQL runner, LiteLLM routing, basic API. |
| Phase 2: Context & Memory | 2 weeks | Qdrant schema indexing, conversation memory, few-shot retrieval. |
| Phase 3: Analysis | 2 weeks | E2B sandbox + smolagents CodeAgent, Plotly artifacts. |
| Phase 4: Production | 2 weeks | Observability, audit, error recovery, evaluation framework. |
| Phase 5: UX & Outputs | 1 week | Output packaging, streaming updates, Open WebUI integration. |

### Section 19: Open WebUI Integration
Open WebUI integrates through an OpenAI-compatible API facade. It provides chat UX, conversation history, and multi-model routing, but the backend remains independent. If Open WebUI is not deployed, the system still supports HTTP API clients and custom frontends with identical capability.

---

## References
- LangGraph design guidance: [docs.langchain.com](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
- smolagents CodeAgent + sandboxing: [huggingface.co](https://huggingface.co/docs/smolagents/en/index)

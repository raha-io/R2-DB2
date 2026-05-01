"""State definition for the analytical agent graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class AnalyticalAgentState(TypedDict, total=False):
    """State flowing through the analytical agent graph.

    Fields with Annotated[list, operator.add] use append-only reducers.
    All other fields use last-write-wins semantics.
    """

    # Conversation context
    conversation_id: str
    user_id: str
    messages: Annotated[list[dict[str, Any]], operator.add]

    # Intent classification
    intent: Literal["new_analysis", "follow_up", "clarification", "off_topic"] | None
    intent_spec: dict[str, Any] | None
    intent_clarification_rounds: int

    # Planning
    plan: dict[str, Any] | None
    plan_approved: bool

    # Schema & retrieval context
    schema_context: str
    historical_queries: list[dict[str, Any]]

    # SQL generation & execution
    generated_sql: str | None
    sql_validation_errors: list[str]
    sql_retry_count: int
    graph_step_count: int  # Global step counter to prevent infinite loops
    sql_review_pass: bool
    sql_review_attempts: int
    query_result: dict[str, Any] | None
    execution_time_ms: int | None

    # Analysis
    analysis_summary: str | None
    analysis_artifacts: Annotated[list[dict[str, Any]], operator.add]

    # Report output
    output_formats: list[str]
    output_files: list[dict[str, str]]
    report: dict[str, Any] | None
    plotly_figures: list[dict[str, Any]]
    report_output: dict[str, Any] | None

    # Observability
    total_llm_tokens: int
    estimated_cost_usd: float
    trace_id: str

    # Error handling
    error: str | None
    error_node: str | None

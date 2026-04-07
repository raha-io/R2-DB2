"""SQL writing agent — drafts a ClickHouse query and self-reviews it once.

The parent graph still owns ``sql_validate``/``sql_execute`` and the global
retry loop. This agent only owns the *generation* phase, with one internal
self-review pass to catch obvious table/granularity mistakes before paying
the cost of a full validate/execute round-trip.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from graph.agents._llm import get_llm
from graph.state import AnalyticalAgentState

logger = logging.getLogger(__name__)

MAX_GRAPH_STEPS = 10
SELF_REVIEW_BUDGET = 1


def _strip_code_fence(sql: str) -> str:
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return sql.strip()


def draft(state: AnalyticalAgentState) -> dict[str, Any]:
    """Generate a SQL draft from the plan, intent spec, and schema context."""
    step_count = state.get("graph_step_count", 0) + 1
    if step_count > MAX_GRAPH_STEPS:
        logger.error("Graph step limit reached (%d). Aborting SQL generation.", step_count)
        return {
            "generated_sql": None,
            "sql_validation_errors": ["Maximum graph step limit reached. Aborting."],
            "sql_retry_count": MAX_GRAPH_STEPS,
            "graph_step_count": step_count,
            "sql_review_attempts": 0,
        }

    llm = get_llm()
    plan_data = state.get("plan", {})
    intent_spec = state.get("intent_spec") or {}
    schema_context = state.get("schema_context", "")
    messages = state.get("messages", [])
    last_message = messages[-1].get("content", "") if messages else ""

    validation_errors = state.get("sql_validation_errors", [])
    error_context = ""
    if validation_errors:
        error_context = (
            "\n\nPrevious SQL had these validation errors. Fix them:\n"
            + "\n".join(f"- {error}" for error in validation_errors)
        )

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a ClickHouse SQL expert. Generate a SQL query to answer the user's question.\n\n"
                    "RULES:\n"
                    "- Use only SELECT statements (no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE)\n"
                    "- Always include a LIMIT clause (max 10000)\n"
                    "- Use only tables from the schema below\n"
                    "- Use ClickHouse-specific syntax and functions\n"
                    "- Honor the intent spec's metric, dimensions, time range, and granularity exactly\n"
                    "- Respond with ONLY the SQL query, no explanation\n\n"
                    f"{schema_context}"
                    f"{error_context}"
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {last_message}\n\n"
                    f"Intent spec: {json.dumps(intent_spec)}\n\n"
                    f"Plan: {json.dumps(plan_data)}"
                )
            ),
        ]
    )

    sql = _strip_code_fence(response.content)
    logger.info("Drafted SQL: %s", sql[:200])
    return {
        "generated_sql": sql,
        "sql_validation_errors": [],
        "graph_step_count": step_count,
        "sql_review_attempts": state.get("sql_review_attempts", 0),
    }


def self_review(state: AnalyticalAgentState) -> dict[str, Any]:
    """Lightweight LLM self-review of the drafted SQL.

    Returns ``sql_review_pass: True`` when the draft passes, otherwise
    seeds ``sql_validation_errors`` with the review feedback so the next
    ``draft`` call sees them. Limited to ``SELF_REVIEW_BUDGET`` attempts
    per agent invocation.
    """
    sql = state.get("generated_sql", "") or ""
    if not sql:
        return {"sql_review_pass": True}

    attempts = state.get("sql_review_attempts", 0)
    if attempts >= SELF_REVIEW_BUDGET:
        return {"sql_review_pass": True}

    intent_spec = state.get("intent_spec") or {}
    if not (intent_spec.get("entities") or intent_spec.get("granularity")):
        # Nothing concrete to check against; skip the review.
        return {"sql_review_pass": True}

    llm = get_llm()
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a SQL reviewer. Given an intent spec and a SQL draft, decide whether the "
                    "draft uses ONLY the entities the spec lists and matches the requested granularity. "
                    "Respond with ONLY valid JSON:\n"
                    '{"ok": bool, "issues": [string]}\n'
                    "Be strict but only flag concrete issues — do not invent style nitpicks."
                )
            ),
            HumanMessage(
                content=(
                    f"Intent spec: {json.dumps(intent_spec)}\n\n"
                    f"SQL draft:\n{sql}"
                )
            ),
        ]
    )

    try:
        verdict = json.loads(response.content)
    except json.JSONDecodeError:
        return {
            "sql_review_pass": True,
            "sql_review_attempts": attempts + 1,
        }

    if verdict.get("ok"):
        return {
            "sql_review_pass": True,
            "sql_review_attempts": attempts + 1,
        }

    issues = verdict.get("issues") or ["Self-review failed"]
    logger.info("SQL self-review found issues: %s", issues)
    return {
        "sql_review_pass": False,
        "sql_review_attempts": attempts + 1,
        "sql_validation_errors": list(issues),
    }


def _route_after_review(state: AnalyticalAgentState) -> str:
    if state.get("sql_review_pass", True):
        return "exit"
    return "draft"


def build_sql_agent() -> Any:
    """Compile the SQL writing subgraph."""
    builder = StateGraph(AnalyticalAgentState)

    builder.add_node("draft", draft)
    builder.add_node("self_review", self_review)

    builder.add_edge(START, "draft")
    builder.add_edge("draft", "self_review")
    builder.add_conditional_edges(
        "self_review",
        _route_after_review,
        {"draft": "draft", "exit": END},
    )

    return builder.compile()

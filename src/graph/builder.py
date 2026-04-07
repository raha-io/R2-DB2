"""Build and compile the analytical agent LangGraph."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph import nodes
from graph.agents import build_analysis_agent, build_intent_agent, build_sql_agent
from graph.state import AnalyticalAgentState

logger = logging.getLogger(__name__)

MAX_SQL_RETRIES = 3
MAX_GRAPH_STEPS = 10


def _compile_graph(builder: StateGraph, checkpointer: Any, hitl_enabled: bool) -> Any:
    if hitl_enabled:
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_before=["hitl_approval"],
        )

    return builder.compile(checkpointer=checkpointer)


def _route_after_intent(state: AnalyticalAgentState) -> str:
    """Route based on classified intent."""
    intent = state.get("intent")
    if intent in ("off_topic", "clarification"):
        return "final_response"
    return "context_retrieve"


def _route_after_hitl(state: AnalyticalAgentState) -> str:
    """Route based on HITL approval decision."""
    if state.get("plan_approved"):
        return "sql_agent"
    return "final_response"


def _route_after_sql_validate(state: AnalyticalAgentState) -> str:
    """Route based on SQL validation result."""
    errors = state.get("sql_validation_errors", [])
    retry_count = state.get("sql_retry_count", 0)
    step_count = state.get("graph_step_count", 0)

    # Global step guard — prevent infinite loops regardless of validation result
    if step_count >= MAX_GRAPH_STEPS:
        logger.error("Global step limit reached (%d). Routing to final_response.", step_count)
        return "final_response"

    if not errors:
        return "sql_execute"
    if retry_count < MAX_SQL_RETRIES:
        return "sql_agent"
    return "final_response"


def _route_after_sql_execute(state: AnalyticalAgentState) -> str:
    """Route based on SQL execution result."""
    step_count = state.get("graph_step_count", 0)

    # Global step guard
    if step_count >= MAX_GRAPH_STEPS:
        logger.error("Global step limit reached (%d). Routing to final_response.", step_count)
        return "final_response"

    if state.get("error") and state.get("error_node") == "sql_execute":
        retry_count = state.get("sql_retry_count", 0)
        if retry_count < MAX_SQL_RETRIES:
            return "sql_agent"
        return "final_response"
    return "analysis_agent"


def build_graph(checkpointer: Any | None = None, hitl_enabled: bool = False) -> Any:
    """Build and compile the analytical agent graph.

    Args:
        checkpointer: LangGraph checkpointer for state persistence.
            If None, uses MemorySaver (in-memory, dev only).
        hitl_enabled: Whether to enable human-in-the-loop approval interrupts.

    Returns:
        Compiled LangGraph graph.
    """
    builder = StateGraph(AnalyticalAgentState)

    intent_agent = build_intent_agent()
    sql_agent = build_sql_agent()
    analysis_agent = build_analysis_agent()

    builder.add_node("intent_agent", intent_agent)
    builder.add_node("context_retrieve", nodes.context_retrieve)
    builder.add_node("plan", nodes.plan)
    builder.add_node("hitl_approval", nodes.hitl_approval)
    builder.add_node("sql_agent", sql_agent)
    builder.add_node("sql_validate", nodes.sql_validate)
    builder.add_node("sql_execute", nodes.sql_execute)
    builder.add_node("analysis_agent", analysis_agent)
    builder.add_node("report_assemble", nodes.report_assemble)
    builder.add_node("final_response", nodes.final_response)

    builder.add_edge(START, "intent_agent")

    builder.add_conditional_edges(
        "intent_agent",
        _route_after_intent,
        {
            "context_retrieve": "context_retrieve",
            "final_response": "final_response",
        },
    )

    builder.add_edge("context_retrieve", "plan")
    builder.add_edge("plan", "hitl_approval")

    builder.add_conditional_edges(
        "hitl_approval",
        _route_after_hitl,
        {
            "sql_agent": "sql_agent",
            "final_response": "final_response",
        },
    )

    builder.add_edge("sql_agent", "sql_validate")

    builder.add_conditional_edges(
        "sql_validate",
        _route_after_sql_validate,
        {
            "sql_execute": "sql_execute",
            "sql_agent": "sql_agent",
            "final_response": "final_response",
        },
    )

    builder.add_conditional_edges(
        "sql_execute",
        _route_after_sql_execute,
        {
            "analysis_agent": "analysis_agent",
            "sql_agent": "sql_agent",
            "final_response": "final_response",
        },
    )

    builder.add_edge("analysis_agent", "report_assemble")
    builder.add_edge("report_assemble", "final_response")

    builder.add_edge("final_response", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = _compile_graph(builder, checkpointer, hitl_enabled)

    logger.info("Analytical agent graph compiled successfully")
    return graph

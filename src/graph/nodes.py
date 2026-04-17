"""Graph nodes for the analytical agent workflow.

Intent classification, SQL generation, and result analysis live in dedicated
agent subgraphs under ``graph.agents``. The nodes here are the "glue" steps
of the parent graph: schema retrieval, planning, HITL, validation, execution,
report assembly, and final response shaping.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from settings import get_settings
from report import OutputFormat, ReportOutputService
from graph.agents._json import parse_json_object
from graph.agents._llm import get_llm as _get_llm
from graph.state import AnalyticalAgentState
from integrations.clickhouse.schema_catalog import (
    extract_keywords,
    get_schema_context,
    render_focused_schema,
)

logger = logging.getLogger(__name__)


def context_retrieve(state: AnalyticalAgentState) -> dict[str, Any]:
    """Retrieve schema context and historical queries for the LLM.

    Uses the intent spec + last user message to rank tables so the SQL agent
    sees the most relevant ones in full and only a name index for the rest.
    Falls back to the full-schema dump when no keywords are available.
    """
    spec = state.get("intent_spec") or {}
    messages = state.get("messages", [])
    user_texts = [
        msg.get("content", "") or ""
        for msg in messages
        if msg.get("role") == "user"
    ]

    keywords = extract_keywords(
        *user_texts,
        spec.get("metric"),
        spec.get("entities"),
        spec.get("dimensions"),
        spec.get("filters"),
    )

    if keywords:
        schema_context = render_focused_schema(keywords)
        logger.info(
            "Focused schema context built (keywords=%s)",
            sorted(keywords),
        )
    else:
        schema_context = get_schema_context()

    return {
        "schema_context": schema_context,
        "historical_queries": [],
    }


def plan(state: AnalyticalAgentState) -> dict[str, Any]:
    """Generate an analysis plan based on the user's question and schema context."""
    llm = _get_llm()
    messages = state.get("messages", [])
    last_message = messages[-1].get("content", "") if messages else ""
    schema_context = state.get("schema_context", "")

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a data analysis planner. Given a user's question and the available database schema, "
                    "create a structured analysis plan.\n\n"
                    f"{schema_context}\n\n"
                    "Respond in JSON format with these fields:\n"
                    "- goal: string describing the analysis goal\n"
                    "- steps: list of analysis steps, each with 'description' and 'sql_needed' (bool)\n"
                    "- tables_needed: list of table names that will be queried\n"
                    "- estimated_complexity: 'simple', 'moderate', or 'complex'\n"
                    "Respond with ONLY valid JSON."
                )
            ),
            HumanMessage(content=last_message),
        ]
    )

    plan_data = parse_json_object(response.content)
    if plan_data is None:
        logger.warning(
            "Plan extraction returned non-JSON (first 200 chars): %r",
            (response.content or "")[:200],
        )
        plan_data = {
            "goal": last_message,
            "steps": [{"description": "Execute analysis query", "sql_needed": True}],
            "tables_needed": [],
            "estimated_complexity": "simple",
        }

    logger.info("Generated plan: %s", plan_data.get("goal", "unknown"))
    return {"plan": plan_data, "plan_approved": False}


def hitl_approval(state: AnalyticalAgentState) -> dict[str, Any]:
    """Human-in-the-loop approval gate. Interrupts execution for approval."""
    settings = get_settings()
    if not settings.graph.hitl_enabled:
        logger.info("HITL disabled; auto-approving plan")
        return {"plan_approved": True}

    plan_data = state.get("plan", {})

    decision = interrupt(
        {
            "question": "Do you approve this analysis plan?",
            "plan": plan_data,
            "instructions": "Resume with True to approve, False to reject.",
        }
    )

    if decision:
        logger.info("Plan approved by user")
        return {"plan_approved": True}

    logger.info("Plan rejected by user")
    return {
        "plan_approved": False,
        "error": "Plan rejected by user",
    }


def sql_validate(state: AnalyticalAgentState) -> dict[str, Any]:
    """Validate the generated SQL for safety and correctness."""
    sql = state.get("generated_sql", "")
    errors: list[str] = []

    if not sql:
        errors.append("No SQL generated")
        return {"sql_validation_errors": errors}

    # Detect non-SQL output (e.g., LLM returned JSON instead of SQL)
    stripped = sql.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        errors.append("LLM returned JSON instead of SQL. Expected a SELECT query.")
        logger.warning("Non-SQL output detected: %s", stripped[:100])
        retry_count = state.get("sql_retry_count", 0)
        return {
            "sql_validation_errors": errors,
            "sql_retry_count": retry_count + 1,
        }

    if not stripped.upper().startswith("SELECT"):
        errors.append(f"Query must start with SELECT. Got: {stripped[:50]}")
        retry_count = state.get("sql_retry_count", 0)
        return {
            "sql_validation_errors": errors,
            "sql_retry_count": retry_count + 1,
        }

    sql_upper = sql.upper().strip()

    forbidden = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
    ]
    for keyword in forbidden:
        if sql_upper.startswith(keyword) or f" {keyword} " in sql_upper:
            errors.append(f"Forbidden SQL keyword: {keyword}")

    if "LIMIT" not in sql_upper:
        errors.append("Query must include a LIMIT clause")

    if errors:
        logger.warning("SQL validation errors: %s", errors)
        retry_count = state.get("sql_retry_count", 0)
        return {
            "sql_validation_errors": errors,
            "sql_retry_count": retry_count + 1,
        }

    logger.info("SQL validation passed")
    return {"sql_validation_errors": []}


def sql_execute(state: AnalyticalAgentState) -> dict[str, Any]:
    """Execute the validated SQL against ClickHouse."""
    import clickhouse_connect

    settings = get_settings()
    sql = state.get("generated_sql", "")

    if not sql:
        return {"error": "No SQL to execute", "error_node": "sql_execute"}

    try:
        start = time.monotonic()
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            database=settings.clickhouse.database,
            username=settings.clickhouse.user,
            password=settings.clickhouse.password,
            secure=settings.clickhouse.secure,
        )
        result = client.query(sql)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        columns = result.column_names
        rows = [dict(zip(columns, row)) for row in result.result_rows]

        query_result = {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "sql": sql,
        }

        logger.info("SQL executed: %d rows in %dms", len(rows), elapsed_ms)
        return {
            "query_result": query_result,
            "execution_time_ms": elapsed_ms,
            "error": None,
        }
    except Exception as exc:
        logger.error("SQL execution failed: %s", exc)
        return {
            "error": f"SQL execution failed: {exc}",
            "error_node": "sql_execute",
        }


async def report_assemble(state: AnalyticalAgentState) -> dict[str, Any]:
    """Assemble the final report from all artifacts."""
    report_id = str(uuid.uuid4())
    report = {
        "id": report_id,
        "conversation_id": state.get("conversation_id", ""),
        "question": state.get("messages", [{}])[-1].get("content", "")
        if state.get("messages")
        else "",
        "plan": state.get("plan"),
        "sql": state.get("generated_sql"),
        "execution_time_ms": state.get("execution_time_ms"),
        "row_count": state.get("query_result", {}).get("row_count", 0),
        "analysis_summary": state.get("analysis_summary"),
        "artifacts": state.get("analysis_artifacts", []),
        "query_result_preview": {
            "columns": state.get("query_result", {}).get("columns", []),
            "rows": state.get("query_result", {}).get("rows", [])[:20],
        },
    }

    settings = get_settings()
    output_dir = settings.report.output_dir if settings.report else "./reports"
    service = ReportOutputService(base_output_dir=output_dir)
    output_format_names = settings.report.default_formats if settings.report else []
    output_formats: list[OutputFormat] = []
    for fmt in output_format_names:
        try:
            output_formats.append(OutputFormat(fmt))
        except ValueError:
            logger.warning("Unsupported output format: %s", fmt)

    if not output_formats:
        output_formats = list(OutputFormat)

    report_output_dict = None
    try:
        report_output = await service.generate_report(
            report_id=report_id,
            query_result=state.get("query_result"),
            analysis_text=state.get("analysis_summary", "") or "",
            plotly_figures=state.get("plotly_figures", []),
            output_formats=output_formats,
            metadata={
                "query": state.get("generated_sql", ""),
                "conversation_id": state.get("conversation_id", ""),
            },
        )
        report_output_dict = report_output.to_dict()
        report["report_output"] = report_output_dict
        report["artifacts"].extend(report_output_dict.get("artifacts", []))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Report output generation failed: %s", exc)

    logger.info("Report assembled: %s", report_id)
    return {"report": report, "report_output": report_output_dict}


def final_response(state: AnalyticalAgentState) -> dict[str, Any]:
    """Format and return the final response message."""
    error = state.get("error")
    intent = state.get("intent")

    if error:
        response_content = f"I encountered an error: {error}"
    elif intent == "off_topic":
        response_content = (
            "I'm an analytical assistant focused on data analysis. "
            "Please ask me a question about your data and I'll help you analyze it."
        )
    elif intent == "clarification":
        response_content = "Could you please provide more details about what you'd like to analyze?"
    elif state.get("report"):
        report = state["report"]
        response_content = (
            "## Analysis Complete\n\n"
            f"{report.get('analysis_summary', 'Analysis completed.')}\n\n"
            "**SQL Used:**\n```sql\n"
            f"{report.get('sql', 'N/A')}\n"
            "```\n\n"
            f"**Rows returned:** {report.get('row_count', 0)}\n"
            f"**Execution time:** {report.get('execution_time_ms', 0)}ms"
        )
    else:
        response_content = "Analysis completed but no report was generated."

    return {
        "messages": [{"role": "assistant", "content": response_content}],
    }

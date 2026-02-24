"""Graph nodes for the analytical agent workflow."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from r2-db2.config.settings import get_settings
from r2-db2.graph.state import AnalyticalAgentState
from r2-db2.integrations.clickhouse.schema_catalog import get_schema_context

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    """Create OpenRouter-compatible LLM client."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openrouter.model,
        openai_api_key=settings.openrouter.api_key,
        openai_api_base=settings.openrouter.base_url,
        temperature=settings.openrouter.temperature,
        max_tokens=settings.openrouter.max_tokens,
        timeout=settings.openrouter.timeout,
    )


def intent_classify(state: AnalyticalAgentState) -> dict[str, Any]:
    """Classify the user's intent from their message."""
    llm = _get_llm()
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "off_topic", "error": "No messages provided"}

    last_message = messages[-1].get("content", "") if messages else ""

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are an intent classifier. Classify the user's message into exactly one of these categories:\n"
                    "- new_analysis: User wants a new data analysis, report, or query\n"
                    "- follow_up: User is asking a follow-up question about a previous analysis\n"
                    "- clarification: User is asking for clarification about something\n"
                    "- off_topic: Message is not related to data analysis\n\n"
                    "Respond with ONLY the category name, nothing else."
                )
            ),
            HumanMessage(content=last_message),
        ]
    )

    intent = response.content.strip().lower()
    valid_intents = {"new_analysis", "follow_up", "clarification", "off_topic"}
    if intent not in valid_intents:
        intent = "new_analysis"

    logger.info("Classified intent: %s", intent)
    return {"intent": intent}


def context_retrieve(state: AnalyticalAgentState) -> dict[str, Any]:
    """Retrieve schema context and historical queries for the LLM."""
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

    try:
        plan_data = json.loads(response.content)
    except json.JSONDecodeError:
        plan_data = {
            "goal": last_message,
            "steps": [{"description": "Execute analysis query", "sql_needed": True}],
            "tables_needed": ["analytics.orders"],
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


def sql_generate(state: AnalyticalAgentState) -> dict[str, Any]:
    """Generate SQL query from the approved plan."""
    llm = _get_llm()
    plan_data = state.get("plan", {})
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
                    "- Respond with ONLY the SQL query, no explanation\n\n"
                    f"{schema_context}"
                    f"{error_context}"
                )
            ),
            HumanMessage(content=f"Question: {last_message}\n\nPlan: {json.dumps(plan_data)}"),
        ]
    )

    sql = response.content.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    logger.info("Generated SQL: %s", sql[:200])
    return {"generated_sql": sql, "sql_validation_errors": []}


def sql_validate(state: AnalyticalAgentState) -> dict[str, Any]:
    """Validate the generated SQL for safety and correctness."""
    sql = state.get("generated_sql", "")
    errors: list[str] = []

    if not sql:
        errors.append("No SQL generated")
        return {"sql_validation_errors": errors}

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


def analysis_sandbox(state: AnalyticalAgentState) -> dict[str, Any]:
    """Analyze query results and generate insights."""
    llm = _get_llm()
    query_result = state.get("query_result", {})
    plan_data = state.get("plan", {})
    messages = state.get("messages", [])
    last_message = messages[-1].get("content", "") if messages else ""

    rows = query_result.get("rows", [])
    sample_rows = rows[:50]

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a data analyst. Analyze the query results and provide insights.\n\n"
                    "Respond in JSON format with:\n"
                    "- summary: A clear, concise summary of findings (2-3 paragraphs)\n"
                    "- key_metrics: list of {name, value, trend} objects for important metrics\n"
                    "- insights: list of insight strings\n"
                    "- recommendations: list of actionable recommendations\n"
                    "Respond with ONLY valid JSON."
                )
            ),
            HumanMessage(
                content=(
                    f"Original question: {last_message}\n\n"
                    f"Plan: {json.dumps(plan_data)}\n\n"
                    f"Query returned {query_result.get('row_count', 0)} rows.\n"
                    f"Columns: {query_result.get('columns', [])}\n"
                    f"Sample data:\n{json.dumps(sample_rows, indent=2, default=str)}"
                )
            ),
        ]
    )

    try:
        analysis = json.loads(response.content)
    except json.JSONDecodeError:
        analysis = {
            "summary": response.content,
            "key_metrics": [],
            "insights": [],
            "recommendations": [],
        }

    return {
        "analysis_summary": analysis.get("summary", ""),
        "analysis_artifacts": [
            {
                "type": "analysis",
                "content": analysis,
            }
        ],
    }


def report_assemble(state: AnalyticalAgentState) -> dict[str, Any]:
    """Assemble the final report from all artifacts."""
    report = {
        "id": str(uuid.uuid4()),
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

    logger.info("Report assembled: %s", report["id"])
    return {"report": report}


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

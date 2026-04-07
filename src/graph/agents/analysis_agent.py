"""Analysis agent — summarizes query results and renders charts.

Splits the old monolithic ``analysis_sandbox`` into a ``summarize`` step
(LLM-driven insights) and a ``chart`` step (Plotly rendering). Splitting
gives each step its own error scope.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from graph.agents._llm import get_llm
from graph.state import AnalyticalAgentState
from integrations.plotly.chart_generator import PlotlyChartGenerator

logger = logging.getLogger(__name__)


def summarize(state: AnalyticalAgentState) -> dict[str, Any]:
    """Run an LLM analysis pass over the query results."""
    llm = get_llm()
    query_result = state.get("query_result", {}) or {}
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


def chart(state: AnalyticalAgentState) -> dict[str, Any]:
    """Render Plotly figures for the query results, if any."""
    query_result = state.get("query_result", {}) or {}
    rows = query_result.get("rows", [])

    if not rows:
        return {"plotly_figures": []}

    try:
        import pandas as pd

        df = pd.DataFrame(rows)
        if df.empty:
            return {"plotly_figures": []}

        generator = PlotlyChartGenerator()
        chart_title = state.get("analysis_summary") or "Analysis Chart"
        figure = generator.generate_chart(df, chart_title)
        return {"plotly_figures": [figure]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Plotly chart generation failed: %s", exc)
        return {"plotly_figures": []}


def build_analysis_agent() -> Any:
    """Compile the analysis subgraph."""
    builder = StateGraph(AnalyticalAgentState)

    builder.add_node("summarize", summarize)
    builder.add_node("chart", chart)

    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", "chart")
    builder.add_edge("chart", END)

    return builder.compile()

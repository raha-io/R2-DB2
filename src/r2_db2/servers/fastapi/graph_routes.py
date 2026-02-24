"""FastAPI routes for the LangGraph analytical agent."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    """Request to start a new analysis."""

    question: str = Field(..., description="Natural language question to analyze")
    conversation_id: str | None = Field(
        None, description="Conversation ID for follow-ups"
    )
    user_id: str = Field(default="anonymous", description="User identifier")


class AnalyzeResponse(BaseModel):
    """Response from the analysis graph."""

    conversation_id: str
    thread_id: str
    status: str
    intent: str | None = None
    plan: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    response: str | None = None
    error: str | None = None


class ApproveRequest(BaseModel):
    """Request to approve or reject a plan."""

    thread_id: str = Field(..., description="Thread ID from the analyze response")
    approved: bool = Field(..., description="Whether to approve the plan")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, req: Request) -> AnalyzeResponse:
    """Submit a natural language question for analysis."""
    graph = req.app.state.graph

    conversation_id = request.conversation_id or str(uuid.uuid4())
    thread_id = f"{conversation_id}-{uuid.uuid4().hex[:8]}"

    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "conversation_id": conversation_id,
        "user_id": request.user_id,
        "messages": [{"role": "user", "content": request.question}],
        "intent": None,
        "plan": None,
        "plan_approved": False,
        "schema_context": "",
        "historical_queries": [],
        "generated_sql": None,
        "sql_validation_errors": [],
        "sql_retry_count": 0,
        "query_result": None,
        "execution_time_ms": None,
        "analysis_summary": None,
        "analysis_artifacts": [],
        "report": None,
        "total_llm_tokens": 0,
        "estimated_cost_usd": 0.0,
        "trace_id": str(uuid.uuid4()),
        "error": None,
        "error_node": None,
    }

    try:
        result = await graph.ainvoke(initial_state, config)
        state = await graph.aget_state(config)

        if state.next:
            return AnalyzeResponse(
                conversation_id=conversation_id,
                thread_id=thread_id,
                status="awaiting_approval",
                intent=result.get("intent"),
                plan=result.get("plan"),
                response="Analysis plan generated. Please approve or reject.",
            )

        messages = result.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else ""
        return AnalyzeResponse(
            conversation_id=conversation_id,
            thread_id=thread_id,
            status="completed",
            intent=result.get("intent"),
            report=result.get("report"),
            response=last_msg,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/approve", response_model=AnalyzeResponse)
async def approve(request: ApproveRequest, req: Request) -> AnalyzeResponse:
    """Approve or reject an analysis plan, resuming the graph execution."""
    from langgraph.types import Command

    graph = req.app.state.graph
    config = {"configurable": {"thread_id": request.thread_id}}

    try:
        state = await graph.aget_state(config)
        if not state.next:
            raise HTTPException(status_code=400, detail="No pending approval for this thread")

        result = await graph.ainvoke(
            Command(resume=request.approved),
            config,
        )

        messages = result.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else ""

        return AnalyzeResponse(
            conversation_id=result.get("conversation_id", ""),
            thread_id=request.thread_id,
            status="completed" if not result.get("error") else "error",
            intent=result.get("intent"),
            plan=result.get("plan"),
            report=result.get("report"),
            response=last_msg,
            error=result.get("error"),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Approval processing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/threads/{thread_id}/state")
async def get_thread_state(thread_id: str, req: Request) -> dict[str, Any]:
    """Get the current state of a conversation thread."""
    graph = req.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await graph.aget_state(config)
        return {
            "thread_id": thread_id,
            "values": dict(state.values) if state.values else {},
            "next": list(state.next) if state.next else [],
            "created_at": str(state.created_at) if state.created_at else None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get thread state: %s", exc)
        raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

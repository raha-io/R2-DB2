"""FastAPI routes for the LangGraph analytical agent."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
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


@router.get("/reports/{report_id}")
async def list_report_artifacts(report_id: str) -> dict[str, Any]:
    """List all artifacts for a report."""
    from r2-db2.config.settings import Settings

    settings = Settings()
    base_dir = Path(getattr(settings.report, "output_dir", "./reports"))

    report_dir = base_dir / report_id
    if not report_dir.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

    artifacts = []
    for f in report_dir.iterdir():
        if f.is_file():
            artifacts.append(
                {
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "download_url": f"/api/v1/reports/{report_id}/{f.name}",
                }
            )

    return {"report_id": report_id, "artifacts": artifacts}


@router.get("/reports/{report_id}/{filename}")
async def download_report_artifact(
    report_id: str,
    filename: str,
) -> FileResponse:
    """Download a generated report artifact file."""
    from r2-db2.config.settings import Settings

    settings = Settings()
    base_dir = Path(getattr(settings.report, "output_dir", "./reports"))

    file_path = base_dir / report_id / filename

    # Security: ensure the resolved path is within the reports directory
    try:
        file_path = file_path.resolve()
        base_dir_resolved = base_dir.resolve()
        if not str(file_path).startswith(str(base_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")

    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Report artifact not found: {filename}"
        )

    # Determine media type from extension
    media_types = {
        ".json": "application/json",
        ".csv": "text/csv",
        ".parquet": "application/octet-stream",
        ".html": "text/html",
        ".pdf": "application/pdf",
    }
    media_type = media_types.get(file_path.suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )

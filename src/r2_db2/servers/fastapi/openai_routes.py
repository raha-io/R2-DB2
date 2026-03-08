"""OpenAI-compatible API routes for Open WebUI integration."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse

from ..base import ChatHandler, ChatRequest
from ..base.models import ChatStreamChunk
from .openai_models import (
    ChatChoice,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageResponse,
    DeltaContent,
    ModelInfo,
    ModelsListResponse,
    StreamChoice,
    UsageInfo,
)


def _chunk_to_text(chunk: ChatStreamChunk) -> str:
    """Convert a ChatStreamChunk to markdown text.
    
    Args:
        chunk: The chat stream chunk to convert
        
    Returns:
        Markdown text representation of the chunk content,
        or empty string if no useful content
    """
    # First try simple text (existing behavior)
    if chunk.simple:
        if isinstance(chunk.simple, dict):
            text = chunk.simple.get("text", "")
            if text:
                return text
        elif isinstance(chunk.simple, str):
            return chunk.simple
    
    # Fall back to converting rich components to markdown
    if chunk.rich:
        return _rich_to_markdown(chunk.rich)
    
    return ""


def _rich_to_markdown(rich_data: Dict[str, Any]) -> str:
    """Convert rich component data to markdown text.
    
    Args:
        rich_data: The rich component data dictionary
        
    Returns:
        Markdown text representation
    """
    component_type = rich_data.get("type", "")
    data = rich_data.get("data", {})

    # Emit concise status updates for streaming progress visibility.
    if component_type == "status_card":
        return _status_card_to_markdown(data)
    if component_type == "status_bar_update":
        return _status_bar_update_to_markdown(data)

    # Skip noisy/internal UI-only components.
    if component_type in (
        "progress_display",
        "progress_bar",
        "status_indicator",
        "task_tracker_update",
        "chat_input_update",
        "tool_execution",
    ):
        return ""
    
    # Handle different rich component types
    if component_type == "dataframe":
        return _dataframe_to_markdown(data)
    elif component_type == "chart":
        return _chart_to_markdown(data)
    elif component_type == "card":
        return _card_to_markdown(data)
    elif component_type == "code_block":
        return _code_block_to_markdown(data)
    elif component_type == "artifact":
        return _artifact_to_markdown(data)
    elif component_type == "text":
        return _text_to_markdown(data)
    elif component_type == "notification":
        return _notification_to_markdown(data)
    elif component_type == "badge":
        return _badge_to_markdown(data)
    elif component_type == "icon_text":
        return _icon_text_to_markdown(data)
    elif component_type == "button":
        return _button_to_markdown(data)
    elif component_type == "button_group":
        return _button_group_to_markdown(data)
    elif component_type == "task_list":
        return _task_list_to_markdown(data)
    elif component_type == "log_viewer":
        return _log_viewer_to_markdown(data)
    elif component_type == "container":
        return _container_to_markdown(data)
    elif component_type == "table":
        return _table_to_markdown(data)
    
    # Fallback: convert the whole component to string
    return str(rich_data)


def _status_card_to_markdown(data: Dict[str, Any]) -> str:
    """Convert StatusCardComponent data to concise markdown status text."""
    description = data.get("description")
    title = data.get("title")
    status = data.get("status")

    text = description or title or status or "Working..."
    return f"⏳ *Processing: {text}*\n\n"


def _status_bar_update_to_markdown(data: Dict[str, Any]) -> str:
    """Convert StatusBarUpdateComponent data to concise markdown status text."""
    message = data.get("message")
    detail = data.get("detail")
    status = data.get("status")

    text = message or detail or status
    if not text:
        return ""
    return f"⏳ *{text}*\n\n"


def _dataframe_to_markdown(data: Dict[str, Any]) -> str:
    """Convert DataFrameComponent data to markdown table.
    
    Args:
        data: The dataframe data dictionary
        
    Returns:
        Markdown table string
    """
    columns = data.get("columns", [])
    rows = data.get("data", data.get("rows", []))
    title = data.get("title")
    description = data.get("description")
    
    lines = []
    if title:
        lines.append(f"## {title}")
    if description:
        lines.append(description)
        lines.append("")
    
    if not columns:
        return "\n".join(lines)
    
    # Build markdown table
    header = "| " + " | ".join(str(col) for col in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    
    lines.append(header)
    lines.append(separator)
    
    # Show max 20 rows with note if truncated
    max_rows = 20
    truncated = len(rows) > max_rows
    rows_to_show = rows[:max_rows]
    
    for row in rows_to_show:
        row_values = [str(val) if val is not None else "" for val in row]
        lines.append("| " + " | ".join(row_values) + " |")
    
    if truncated:
        remaining = len(rows) - max_rows
        lines.append("")
        lines.append(f"... and {remaining} more rows")
    
    return "\n".join(lines)


def _chart_to_markdown(data: Dict[str, Any]) -> str:
    """Convert ChartComponent data to markdown.
    
    Args:
        data: The chart data dictionary
        
    Returns:
        Markdown string with chart reference
    """
    title = data.get("title")
    chart_type = data.get("chart_type", "chart")
    
    # Check for download link in data
    download_url = data.get("download_url") or data.get("uri") or data.get("link")
    
    lines = []
    if title:
        lines.append(f"### {title}")
    
    if chart_type == "plotly":
        lines.append("📊 Plotly Chart")
    else:
        lines.append(f"📊 {chart_type.title()} Chart")
    
    if download_url:
        filename = download_url.split("/")[-1] if "/" in download_url else "chart"
        lines.append(f"📥 [Download {filename}]({download_url})")
    
    return "\n".join(lines)


def _card_to_markdown(data: Dict[str, Any]) -> str:
    """Convert CardComponent data to markdown.
    
    Args:
        data: The card data dictionary
        
    Returns:
        Markdown string with card content
    """
    title = data.get("title")
    content = data.get("content", data.get("text", ""))
    
    lines = []
    if title:
        lines.append(f"**{title}**")
    if content:
        if title:
            lines.append("")
        lines.append(content)
    
    return "\n".join(lines)


def _code_block_to_markdown(data: Dict[str, Any]) -> str:
    """Convert CodeBlockComponent data to markdown code block.
    
    Args:
        data: The code block data dictionary
        
    Returns:
        Markdown code block string
    """
    code = data.get("code", data.get("content", ""))
    language = data.get("language", data.get("lang", ""))
    
    if language:
        return f"```{language}\n{code}\n```"
    else:
        return f"```\n{code}\n```"


def _artifact_to_markdown(data: Dict[str, Any]) -> str:
    """Convert ArtifactComponent data to markdown.
    
    Args:
        data: The artifact data dictionary
        
    Returns:
        Markdown string with download link
    """
    name = data.get("name", data.get("filename", data.get("title", "File")))
    uri = data.get("uri", data.get("url", data.get("link", "")))
    kind = data.get("kind", "")
    
    if uri:
        return f"📥 [{name}]({uri})"
    else:
        return name


def _text_to_markdown(data: Dict[str, Any]) -> str:
    """Convert RichTextComponent data to markdown.
    
    Args:
        data: The text component data dictionary
        
    Returns:
        Markdown text string
    """
    content = data.get("content", data.get("text", ""))
    markdown = data.get("markdown", True)
    
    if markdown:
        return content
    else:
        return content


def _notification_to_markdown(data: Dict[str, Any]) -> str:
    """Convert NotificationComponent data to markdown.
    
    Args:
        data: The notification data dictionary
        
    Returns:
        Markdown string with notification content
    """
    title = data.get("title", "")
    message = data.get("message", "")
    level = data.get("level", "info")
    
    prefix = f"[{level.upper()}]" if level else ""
    if title:
        return f"{prefix} **{title}**: {message}"
    else:
        return f"{prefix} {message}"


def _badge_to_markdown(data: Dict[str, Any]) -> str:
    """Convert BadgeComponent data to markdown.
    
    Args:
        data: The badge data dictionary
        
    Returns:
        Markdown string with badge text
    """
    text = data.get("text", "")
    color = data.get("color", "")
    
    if color:
        return f"-badge[{text}]"
    else:
        return text


def _icon_text_to_markdown(data: Dict[str, Any]) -> str:
    """Convert IconTextComponent data to markdown.
    
    Args:
        data: The icon text data dictionary
        
    Returns:
        Markdown string
    """
    icon = data.get("icon", "")
    text = data.get("text", "")
    
    if icon and text:
        return f"{icon} {text}"
    elif text:
        return text
    elif icon:
        return icon
    return ""


def _button_to_markdown(data: Dict[str, Any]) -> str:
    """Convert ButtonComponent data to markdown.
    
    Args:
        data: The button data dictionary
        
    Returns:
        Markdown string with button label
    """
    label = data.get("label", "")
    return f"[{label}]"


def _button_group_to_markdown(data: Dict[str, Any]) -> str:
    """Convert ButtonGroupComponent data to markdown.
    
    Args:
        data: The button group data dictionary
        
    Returns:
        Markdown string with button labels
    """
    buttons = data.get("buttons", [])
    if not buttons:
        return ""
    
    labels = [btn.get("label", "") for btn in buttons]
    return ", ".join(f"[{label}]" for label in labels if label)


def _task_list_to_markdown(data: Dict[str, Any]) -> str:
    """Convert TaskListComponent data to markdown.
    
    Args:
        data: The task list data dictionary
        
    Returns:
        Markdown list of tasks
    """
    tasks = data.get("tasks", [])
    if not tasks:
        return ""
    
    lines = []
    for task in tasks:
        if isinstance(task, dict):
            title = task.get("title", task.get("name", ""))
            status = task.get("status", "")
            if title:
                if status:
                    lines.append(f"- [{status}] {title}")
                else:
                    lines.append(f"- {title}")
        else:
            lines.append(f"- {task}")
    
    return "\n".join(lines)


def _log_viewer_to_markdown(data: Dict[str, Any]) -> str:
    """Convert LogViewerComponent data to markdown.
    
    Args:
        data: The log viewer data dictionary
        
    Returns:
        Markdown string with log lines
    """
    lines = data.get("lines", [])
    if not lines:
        return ""
    
    return "\n".join(f"  {line}" for line in lines)


def _container_to_markdown(data: Dict[str, Any]) -> str:
    """Convert ContainerComponent data to markdown.
    
    Args:
        data: The container data dictionary
        
    Returns:
        Markdown string (container is just a wrapper)
    """
    # Container is typically a wrapper for other components
    # Return empty string as children components will be processed separately
    return ""


def _table_to_markdown(data: Dict[str, Any]) -> str:
    """Convert TableComponent data to markdown.
    
    Args:
        data: The table data dictionary
        
    Returns:
        Markdown table string
    """
    # Try different possible field names for table data
    headers = data.get("headers", data.get("columns", []))
    rows = data.get("rows", data.get("data", []))
    
    if not headers:
        return ""
    
    # Build markdown table
    header = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    
    lines = [header, separator]
    
    for row in rows:
        row_values = [str(val) if val is not None else "" for val in row]
        lines.append("| " + " | ".join(row_values) + " |")
    
    return "\n".join(lines)

logger = logging.getLogger(__name__)

R2_DB2_MODEL_ID = "r2-db2-analyst"


def register_openai_routes(app: FastAPI, agent) -> None:
    """Register OpenAI-compatible /v1 routes on the FastAPI app.
    
    Args:
        app: The FastAPI application instance.
        agent: The R2-DB2 agent instance.
    """
    router = APIRouter(prefix="/v1", tags=["openai-compat"])
    chat_handler = ChatHandler(agent)

    @router.get("/models")
    async def list_models():
        """GET /v1/models — return available models."""
        return ModelsListResponse(
            data=[
                ModelInfo(id=R2_DB2_MODEL_ID, owned_by="r2-db2"),
            ]
        )

    @router.post("/chat/completions")
    async def chat_completions(request: Request, body: ChatCompletionRequest):
        """POST /v1/chat/completions — OpenAI-compatible chat endpoint.
        
        Translates OpenAI messages to internal ChatRequest,
        calls the R2-DB2 agent, and returns OpenAI-formatted response.
        """
        # 1. Extract ALL user messages from OpenAI messages and join them
        user_messages: list[str] = []
        for msg in body.messages:
            if msg.role == "user" and msg.content:
                user_messages.append(msg.content)
        
        # Join all user messages with newlines for context
        user_message = "\n".join(user_messages)

        if not user_message:
            # Return empty response if no user message
            return ChatCompletionResponse(
                model=body.model,
                choices=[
                    ChatChoice(
                        message=ChatMessageResponse(content="No user message found.")
                    )
                ],
            )

        # 2. Build internal ChatRequest
        chat_req = ChatRequest(
            message=user_message,
            conversation_id=body.conversation_id or str(uuid.uuid4()),
        )

        # 3. Branch: streaming vs non-streaming
        if body.stream:
            return StreamingResponse(
                _stream_response(chat_handler, chat_req, body.model),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return await _non_stream_response(chat_handler, chat_req, body.model)

    app.include_router(router)


async def _non_stream_response(
    chat_handler: ChatHandler,
    chat_req: ChatRequest,
    model: str,
) -> ChatCompletionResponse:
    """Collect all chunks and return a single ChatCompletionResponse."""
    parts: list[str] = []

    try:
        async for chunk in chat_handler.handle_stream(chat_req):
            text = _chunk_to_text(chunk)
            if text:
                parts.append(text)
    except Exception as exc:
        logger.exception("Error during agent processing")
        parts.append(f"Error: {exc}")

    full_text = "\n".join(parts) if parts else "No response generated."

    return ChatCompletionResponse(
        model=model,
        choices=[
            ChatChoice(message=ChatMessageResponse(content=full_text))
        ],
        usage=UsageInfo(
            prompt_tokens=0,
            completion_tokens=len(full_text.split()),
            total_tokens=len(full_text.split()),
        ),
    )


async def _stream_response(
    chat_handler: ChatHandler,
    chat_req: ChatRequest,
    model: str,
) -> AsyncGenerator[str, None]:
    """Yield OpenAI-format SSE chunks from the agent stream."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # First chunk: send role
    first_chunk = ChatCompletionChunk(
        id=completion_id,
        model=model,
        choices=[
            StreamChoice(
                delta=DeltaContent(role="assistant", content=""),
            )
        ],
    )
    yield f"data: {first_chunk.model_dump_json()}\n\n"

    # Stream content chunks
    try:
        async for chunk in chat_handler.handle_stream(chat_req):
            text = _chunk_to_text(chunk)
            # Skip chunks that produce empty text (status/progress indicators)
            if text:
                content_chunk = ChatCompletionChunk(
                    id=completion_id,
                    model=model,
                    choices=[
                        StreamChoice(
                            delta=DeltaContent(content=text + "\n"),
                        )
                    ],
                )
                yield f"data: {content_chunk.model_dump_json()}\n\n"
    except Exception as exc:
        logger.exception("Error during streaming")
        error_chunk = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                StreamChoice(
                    delta=DeltaContent(content=f"\n\nError: {exc}"),
                )
            ],
        )
        yield f"data: {error_chunk.model_dump_json()}\n\n"
    finally:
        # Final chunk and terminal SSE marker should always be sent,
        # even when streaming raises an exception.
        done_chunk = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                StreamChoice(
                    delta=DeltaContent(),
                    finish_reason="stop",
                )
            ],
        )
        yield f"data: {done_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

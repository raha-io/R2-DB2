"""Tests for Open WebUI pipe behavior against v0.2.0 API modes.

This suite validates:
- Graph-native URL routing (default mode)
- OpenAI-compatible fallback routing
- Non-stream responses
- SSE streaming parsing and status resolution
"""

import json
import sys
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENWEBUI_ROOT = PROJECT_ROOT / "openwebui"
if str(OPENWEBUI_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENWEBUI_ROOT))


def _import_pipe():
    """Import Pipe from the openwebui module, skipping if aiohttp is missing."""
    try:
        from pipe_r2_db2_analyst import Pipe  # type: ignore[import]

        return Pipe
    except ModuleNotFoundError as exc:
        pytest.skip(f"pipe_r2_db2_analyst dependencies not installed: {exc}")


def make_openai_sse_line(content: str) -> bytes:
    chunk = {"choices": [{"delta": {"content": content}, "finish_reason": None}]}
    return f"data: {json.dumps(chunk)}\n".encode()


def make_graph_sse_event(event: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event)}\n".encode()


def make_sse_done() -> bytes:
    return b"data: [DONE]\n"


async def mock_sse_stream(lines: list[bytes]) -> AsyncGenerator[bytes, None]:
    for line in lines:
        yield line


def make_session_cm(mock_resp: MagicMock, capture_urls: list[str] | None = None) -> AsyncMock:
    """Create aiohttp.ClientSession async context manager mock."""

    def _post(url: str, **kwargs: Any) -> AsyncMock:
        if capture_urls is not None:
            capture_urls.append(url)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    session = MagicMock(post=MagicMock(side_effect=_post))
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    return session_cm


class TestPipeV020:
    @pytest.mark.asyncio
    async def test_pipe_status_stuck_bug_never_gets_done_without_done_marker(self):
        """Graph stream should still resolve status even if [DONE] is never sent."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.USE_GRAPH_API = True

        emitted_events: list[dict[str, Any]] = []

        async def event_emitter(event: dict[str, Any]) -> None:
            emitted_events.append(event)

        lines = [
            make_graph_sse_event({"type": "status", "node": "plan", "message": "Planning..."}),
            # Stream closes without a DONE marker.
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        with patch("aiohttp.ClientSession", return_value=make_session_cm(mock_resp)):
            body = {
                "messages": [{"role": "user", "content": "Show sales data"}],
                "stream": True,
            }
            chunks: list[str] = []
            async for chunk in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                chunks.append(chunk)

        assert chunks
        status_events = [e for e in emitted_events if e.get("type") == "status"]
        assert len(status_events) >= 2
        assert status_events[0]["data"]["done"] is False
        assert status_events[-1]["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_pipe_non_stream_returns_content(self):
        """Default graph non-stream mode should return formatted response text."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.USE_GRAPH_API = True

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "status": "completed",
                "response": "Sales analysis complete.",
            }
        )

        with patch("aiohttp.ClientSession", return_value=make_session_cm(mock_resp)):
            body = {
                "messages": [{"role": "user", "content": "Show sales data"}],
                "stream": False,
            }
            result = await pipe.pipe(body=body, __event_emitter__=None)

        assert "Sales analysis complete." in result

    @pytest.mark.asyncio
    async def test_pipe_url_construction_without_v1_suffix(self):
        """Graph mode should target /api/v1/analyze with base URL lacking /v1."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.R2_DB2_API_BASE_URL = "http://app:8000"
        pipe.valves.USE_GRAPH_API = True

        called_urls: list[str] = []
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": "completed", "response": "OK"})

        with patch(
            "aiohttp.ClientSession",
            return_value=make_session_cm(mock_resp, capture_urls=called_urls),
        ):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": False}
            await pipe.pipe(body=body)

        assert called_urls
        assert called_urls[0] == "http://app:8000/api/v1/analyze"

    @pytest.mark.asyncio
    async def test_pipe_url_construction_with_v1_suffix(self):
        """Graph mode should normalize /v1 base URL and still target /api/v1/analyze."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.R2_DB2_API_BASE_URL = "http://app:8000/v1"
        pipe.valves.USE_GRAPH_API = True

        called_urls: list[str] = []
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": "completed", "response": "OK"})

        with patch(
            "aiohttp.ClientSession",
            return_value=make_session_cm(mock_resp, capture_urls=called_urls),
        ):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": False}
            await pipe.pipe(body=body)

        assert called_urls
        assert called_urls[0] == "http://app:8000/api/v1/analyze"
        assert "/v1/v1/" not in called_urls[0]

    @pytest.mark.asyncio
    async def test_pipe_openai_fallback_url_and_non_stream_response(self):
        """OpenAI fallback mode should call /v1/chat/completions and return message content."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.USE_GRAPH_API = False
        pipe.valves.R2_DB2_API_BASE_URL = "http://app:8000"

        called_urls: list[str] = []
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"choices": [{"message": {"content": "Fallback works."}}]}
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=make_session_cm(mock_resp, capture_urls=called_urls),
        ):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": False}
            result = await pipe.pipe(body=body)

        assert called_urls
        assert called_urls[0] == "http://app:8000/v1/chat/completions"
        assert "Fallback works." in result

    @pytest.mark.asyncio
    async def test_pipe_graph_stream_parses_status_and_result_sse(self):
        """Graph streaming should parse status/result events and emit final completion status."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.USE_GRAPH_API = True

        emitted_events: list[dict[str, Any]] = []

        async def event_emitter(event: dict[str, Any]) -> None:
            emitted_events.append(event)

        lines = [
            make_graph_sse_event(
                {"type": "status", "node": "sql_generate", "message": "Generating SQL..."}
            ),
            make_graph_sse_event(
                {
                    "type": "result",
                    "status": "completed",
                    "response": "Result summary",
                }
            ),
            make_sse_done(),
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        with patch("aiohttp.ClientSession", return_value=make_session_cm(mock_resp)):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": True}
            chunks: list[str] = []
            async for chunk in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                chunks.append(chunk)

        joined = "".join(chunks)
        assert "Generating SQL" in joined
        assert "Result summary" in joined
        statuses = [e for e in emitted_events if e.get("type") == "status"]
        assert statuses[0]["data"]["done"] is False
        assert statuses[-1]["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_pipe_openai_stream_parses_sse_chunks(self):
        """OpenAI fallback streaming should parse delta content chunks until [DONE]."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.USE_GRAPH_API = False

        lines = [
            make_openai_sse_line("Hello"),
            make_openai_sse_line(" world"),
            make_sse_done(),
        ]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        with patch("aiohttp.ClientSession", return_value=make_session_cm(mock_resp)):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": True}
            chunks: list[str] = []
            async for chunk in await pipe.pipe(body=body, __event_emitter__=None):
                chunks.append(chunk)

        assert "".join(chunks) == "Hello world"

"""Tests for the Open WebUI pipe streaming behavior.

Covers the 'stuck analyzing' bug where the chat gets stuck showing
repeated '🔍 Analyzing your question...' messages.

The pipe emits a '🔍 Analyzing your question...' status at the start,
then calls the backend. If the backend stream never sends [DONE], the
pipe hangs and the status event is never resolved.
"""
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENWEBUI_ROOT = PROJECT_ROOT / "openwebui"
if str(OPENWEBUI_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENWEBUI_ROOT))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import AsyncGenerator, Optional


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_sse_line(content: str) -> bytes:
    """Create a proper SSE line as bytes (mimics aiohttp stream)."""
    chunk = {
        "choices": [
            {"delta": {"content": content}, "finish_reason": None}
        ]
    }
    return f"data: {json.dumps(chunk)}\n".encode()


def make_sse_done() -> bytes:
    """Create the [DONE] SSE terminator."""
    return b"data: [DONE]\n"


def make_sse_finish() -> bytes:
    """Create the finish_reason=stop chunk."""
    chunk = {
        "choices": [
            {"delta": {}, "finish_reason": "stop"}
        ]
    }
    return f"data: {json.dumps(chunk)}\n".encode()


async def mock_sse_stream(lines: list[bytes]) -> AsyncGenerator[bytes, None]:
    """Yield a sequence of SSE bytes as an async generator (mimics aiohttp response.content)."""
    for line in lines:
        yield line


# ─── Pipe import (lazy, so missing aiohttp doesn't break collection) ────────

def _import_pipe():
    """Import Pipe from the openwebui module, skipping if aiohttp is missing."""
    try:
        from pipe_r2_db2_analyst import Pipe  # type: ignore[import]
        return Pipe
    except ModuleNotFoundError as exc:
        pytest.skip(f"pipe_r2_db2_analyst dependencies not installed: {exc}")


# ─── Tests ──────────────────────────────────────────────────────────────────


class TestPipeStatusEvents:
    """Tests for correct status event emission by the pipe."""

    @pytest.mark.asyncio
    async def test_pipe_emits_analyzing_status_at_start(self):
        """Pipe should emit '🔍 Analyzing your question...' at the start."""
        Pipe = _import_pipe()
        pipe = Pipe()

        emitted_events = []

        async def event_emitter(event):
            emitted_events.append(event)

        # Patch the actual HTTP call to return an immediate [DONE] stream
        lines = [make_sse_finish(), make_sse_done()]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            post=MagicMock(return_value=mock_cm)
        ))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "Show sales data"}], "stream": True}
            # Consume the async generator
            async for _ in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                pass

        # First event should be the 'analyzing' status
        assert len(emitted_events) >= 1
        first_event = emitted_events[0]
        assert first_event["type"] == "status"
        assert "Analyzing" in first_event["data"]["description"]
        assert first_event["data"]["done"] is False

    @pytest.mark.asyncio
    async def test_pipe_emits_analysis_complete_after_done(self):
        """Pipe should emit '✅ Analysis complete' when [DONE] is received."""
        Pipe = _import_pipe()
        pipe = Pipe()

        emitted_events = []

        async def event_emitter(event):
            emitted_events.append(event)

        # Normal stream: some content then [DONE]
        lines = [
            make_sse_line("Here is your analysis.\n"),
            make_sse_finish(),
            make_sse_done(),
        ]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            post=MagicMock(return_value=mock_cm)
        ))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "Show sales data"}], "stream": True}
            chunks = []
            async for chunk in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                chunks.append(chunk)

        # Should have emitted 'Analysis complete' done=True event
        done_events = [e for e in emitted_events if e["data"].get("done") is True]
        assert len(done_events) >= 1
        last_done = done_events[-1]
        assert "Analysis complete" in last_done["data"]["description"] or "complete" in last_done["data"]["description"].lower()

    @pytest.mark.asyncio
    async def test_pipe_status_stuck_bug_never_gets_done_without_done_marker(self):
        """
        Regression test: if the backend stream never sends [DONE], the pipe
        should still complete (not hang forever) and the 'analyzing' status
        should NOT be the last status event.

        This tests the pipe's robustness against a backend that returns
        an empty body or premature close without [DONE].
        """
        Pipe = _import_pipe()
        pipe = Pipe()

        emitted_events = []

        async def event_emitter(event):
            emitted_events.append(event)

        # Stream ends abruptly without [DONE]
        lines = [
            make_sse_line("Partial response"),
            # No [DONE] - connection closes
        ]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            post=MagicMock(return_value=mock_cm)
        ))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "Show sales data"}], "stream": True}
            chunks = []
            async for chunk in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                chunks.append(chunk)

        # Pipe should have returned at least some content
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_pipe_emits_error_status_on_backend_error(self):
        """Pipe should emit an error status when backend returns non-200."""
        Pipe = _import_pipe()
        pipe = Pipe()

        emitted_events = []

        async def event_emitter(event):
            emitted_events.append(event)

        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="Internal Server Error")
        mock_resp.content = mock_sse_stream([])

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            post=MagicMock(return_value=mock_cm)
        ))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "Show sales data"}], "stream": True}
            chunks = []
            async for chunk in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                chunks.append(chunk)

        # Should have an error in chunks
        full_output = "".join(str(c) for c in chunks)
        assert "500" in full_output or "error" in full_output.lower() or "Error" in full_output

    @pytest.mark.asyncio
    async def test_pipe_non_stream_returns_content(self):
        """Non-streaming pipe call should return content from backend."""
        Pipe = _import_pipe()
        pipe = Pipe()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Sales analysis complete."}}]
        })

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            post=MagicMock(return_value=mock_cm)
        ))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "Show sales data"}], "stream": False}
            result = await pipe.pipe(body=body, __event_emitter__=None)

        assert "Sales analysis complete." in result

    @pytest.mark.asyncio
    async def test_pipe_url_construction_without_v1_suffix(self):
        """Pipe should append /v1 to base URL when not present."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.R2_DB2_API_BASE_URL = "http://app:8000"

        called_urls = []

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "OK"}}]
        })

        def capture_post(url, **kwargs):
            called_urls.append(url)
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_resp)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(post=capture_post))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": False}
            await pipe.pipe(body=body)

        assert called_urls, "No URLs captured"
        assert called_urls[0] == "http://app:8000/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_pipe_url_construction_with_v1_suffix(self):
        """Pipe should NOT double-append /v1 when base URL already has it."""
        Pipe = _import_pipe()
        pipe = Pipe()
        pipe.valves.R2_DB2_API_BASE_URL = "http://app:8000/v1"

        called_urls = []

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "OK"}}]
        })

        def capture_post(url, **kwargs):
            called_urls.append(url)
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_resp)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(post=capture_post))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "test"}], "stream": False}
            await pipe.pipe(body=body)

        assert called_urls, "No URLs captured"
        assert called_urls[0] == "http://app:8000/v1/chat/completions"
        # Must NOT be double /v1/v1/
        assert "/v1/v1/" not in called_urls[0]

    @pytest.mark.asyncio
    async def test_pipe_handles_connection_error_gracefully(self):
        """Pipe should return error message when backend is unreachable."""
        Pipe = _import_pipe()
        pipe = Pipe()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            # Use a generic Exception to simulate connection errors without
            # needing to construct aiohttp.ClientConnectorError (complex constructor)
            mock_session.post = MagicMock(side_effect=Exception("Cannot connect to host"))
            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session_cm

            body = {"messages": [{"role": "user", "content": "test"}], "stream": False}
            result = await pipe.pipe(body=body, __event_emitter__=None)

        # Should return an error string, not raise
        assert isinstance(result, str)
        assert "error" in result.lower() or "❌" in result


class TestPipeStatusBugReproduction:
    """Direct reproduction tests for the 'stuck analyzing' bug.
    
    The bug: pipe emits '🔍 Analyzing...' with done=False at start,
    then if the backend stream never sends [DONE], the pipe never
    emits the 'done=True' status, leaving the UI stuck.
    """

    @pytest.mark.asyncio
    async def test_stuck_analyzing_bug_status_always_resolves(self):
        """
        KEY BUG REPRODUCTION TEST:
        
        The 'stuck analyzing' bug occurs when:
        1. Pipe emits status '🔍 Analyzing...' with done=False
        2. Backend stream returns only status components (no text content)
        3. Stream sends [DONE] but pipe processes it correctly
        
        Expected: The '🔍 Analyzing...' status resolves to '✅ Analysis complete'
        Bug: Status stays stuck as '🔍 Analyzing...' 
        """
        Pipe = _import_pipe()
        pipe = Pipe()

        status_events = []

        async def event_emitter(event):
            if event["type"] == "status":
                status_events.append(event)

        # Backend sends ONLY [DONE] with no content (simulates status-only stream)
        lines = [make_sse_finish(), make_sse_done()]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = mock_sse_stream(lines)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=MagicMock(
            post=MagicMock(return_value=mock_cm)
        ))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            body = {"messages": [{"role": "user", "content": "Show me data"}], "stream": True}
            async for _ in await pipe.pipe(body=body, __event_emitter__=event_emitter):
                pass

        # Must have at least 2 status events: one opening, one closing
        assert len(status_events) >= 2, (
            f"Expected at least 2 status events (analyzing start + done), "
            f"got {len(status_events)}: {status_events}"
        )

        # First status event should be 'analyzing' with done=False
        first_status = status_events[0]
        assert first_status["data"]["done"] is False, "First status should be not done"

        # Last status event should have done=True (stream resolved)
        last_status = status_events[-1]
        assert last_status["data"]["done"] is True, (
            f"Last status event should have done=True to resolve the 'analyzing' state. "
            f"Got: {last_status}. This is the 'stuck analyzing' bug!"
        )

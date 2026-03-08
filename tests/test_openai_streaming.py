"""Tests for OpenAI-compatible streaming helpers and SSE graph streaming."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from r2-db2.servers.base.models import ChatStreamChunk
from r2-db2.servers.fastapi.openai_routes import (
    _chunk_to_text,
    _rich_to_markdown,
    _stream_graph_response,
)


class TestRichToMarkdown:
    def test_status_components_are_converted_to_concise_text(self):
        status_card = _rich_to_markdown(
            {
                "type": "status_card",
                "data": {"description": "Analyzing your question..."},
            }
        )
        status_bar = _rich_to_markdown(
            {
                "type": "status_bar_update",
                "data": {"message": "Loading schema context..."},
            }
        )

        assert "Processing" in status_card
        assert "Loading schema context" in status_bar

    def test_noise_components_are_suppressed(self):
        result = _rich_to_markdown(
            {
                "type": "progress_display",
                "data": {"title": "Loading", "current": 50, "total": 100},
            }
        )
        assert result == ""


class TestChunkToText:
    def test_prefers_simple_text(self):
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {"content": "Rich content"}},
            simple={"text": "Simple content"},
            conversation_id="test-conv",
            request_id="test-req",
        )
        assert _chunk_to_text(chunk) == "Simple content"

    def test_falls_back_to_rich_conversion(self):
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {"content": "Hello world"}},
            simple=None,
            conversation_id="test-conv",
            request_id="test-req",
        )
        assert _chunk_to_text(chunk) == "Hello world"


class TestStreamGraphResponse:
    @pytest.mark.asyncio
    async def test_stream_emits_role_then_done(self):
        mock_graph = MagicMock()

        async def mock_astream(*_args, **_kwargs):
            if False:
                yield None

        mock_graph.astream = mock_astream
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={"messages": []}))

        events = []
        async for event in _stream_graph_response(
            graph=mock_graph,
            user_message="What is 2+2?",
            model="r2-db2-analyst",
            conversation_id="conv-123",
        ):
            events.append(event)

        assert any('"role":"assistant"' in e or '"role": "assistant"' in e for e in events)
        assert events[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_stream_includes_thinking_and_final_content(self):
        mock_graph = MagicMock()

        async def mock_astream(*_args, **_kwargs):
            yield {"sql_generate": {"generated_sql": "SELECT 1"}}

        mock_graph.astream = mock_astream
        mock_graph.aget_state = AsyncMock(
            return_value=MagicMock(values={"messages": [{"role": "assistant", "content": "Final answer"}]})
        )

        events = []
        async for event in _stream_graph_response(
            graph=mock_graph,
            user_message="Run analysis",
            model="r2-db2-analyst",
            conversation_id="conv-123",
        ):
            events.append(event)

        assert any("Writing SQL query" in e for e in events)
        assert any("Final answer" in e for e in events)
        assert events[-1] == "data: [DONE]\n\n"

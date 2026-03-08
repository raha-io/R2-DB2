"""Tests for OpenAI-compatible SSE streaming routes."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator, Any

from r2-db2.servers.fastapi.openai_routes import (
    _chunk_to_text,
    _rich_to_markdown,
    _stream_response,
)
from r2-db2.servers.base.models import ChatStreamChunk


class TestRichToMarkdown:
    """Tests for _rich_to_markdown function."""

    def test_rich_to_markdown_drops_status_bar_update(self):
        """Test that status_bar_update component returns empty string."""
        rich_data = {
            "type": "status_bar_update",
            "data": {"status": "Analyzing your question..."}
        }
        result = _rich_to_markdown(rich_data)
        assert result == ""

    def test_rich_to_markdown_drops_status_card(self):
        """Test that status_card component returns empty string."""
        rich_data = {
            "type": "status_card",
            "data": {"title": "Processing", "status": "In progress"}
        }
        result = _rich_to_markdown(rich_data)
        assert result == ""

    def test_rich_to_markdown_drops_progress_display(self):
        """Test that progress_display component returns empty string."""
        rich_data = {
            "type": "progress_display",
            "data": {"title": "Loading", "current": 50, "total": 100}
        }
        result = _rich_to_markdown(rich_data)
        assert result == ""

    def test_rich_to_markdown_drops_progress_bar(self):
        """Test that progress_bar component returns empty string."""
        rich_data = {
            "type": "progress_bar",
            "data": {"progress": 0.5, "label": "50%"}
        }
        result = _rich_to_markdown(rich_data)
        assert result == ""

    def test_rich_to_markdown_drops_status_indicator(self):
        """Test that status_indicator component returns empty string."""
        rich_data = {
            "type": "status_indicator",
            "data": {"icon": "spinner", "text": "Working..."}
        }
        result = _rich_to_markdown(rich_data)
        assert result == ""

    def test_rich_to_markdown_keeps_text_content(self):
        """Test that markdown component returns content text."""
        rich_data = {
            "type": "text",
            "data": {"content": "Hello, this is **markdown** text!"}
        }
        result = _rich_to_markdown(rich_data)
        assert result == "Hello, this is **markdown** text!"

    def test_rich_to_markdown_keeps_markdown_content(self):
        """Test that text component with markdown returns content."""
        rich_data = {
            "type": "text",
            "data": {"content": "# Header\n\nSome content here."}
        }
        result = _rich_to_markdown(rich_data)
        assert result == "# Header\n\nSome content here."

    def test_rich_to_markdown_keeps_dataframe(self):
        """Test that dataframe component returns markdown table."""
        rich_data = {
            "type": "dataframe",
            "data": {
                "columns": ["name", "value"],
                "rows": [["Alice", 100], ["Bob", 200]]
            }
        }
        result = _rich_to_markdown(rich_data)
        assert "| name | value |" in result
        assert "| Alice | 100 |" in result
        assert "| Bob | 200 |" in result

    def test_rich_to_markdown_keeps_chart(self):
        """Test that chart component returns markdown reference."""
        rich_data = {
            "type": "chart",
            "data": {"title": "Sales Chart", "chart_type": "plotly"}
        }
        result = _rich_to_markdown(rich_data)
        assert "Sales Chart" in result
        assert "Plotly Chart" in result

    def test_rich_to_markdown_keeps_card(self):
        """Test that card component returns markdown."""
        rich_data = {
            "type": "card",
            "data": {"title": "Info", "content": "This is important info."}
        }
        result = _rich_to_markdown(rich_data)
        assert "**Info**" in result
        assert "This is important info." in result

    def test_rich_to_markdown_empty_type(self):
        """Test that empty type falls back to string conversion."""
        rich_data = {
            "type": "",
            "data": {"some": "data"}
        }
        result = _rich_to_markdown(rich_data)
        # Should fall back to str(rich_data)
        assert "{'type': '', 'data': {'some': 'data'}}" in result or "{'data': {'some': 'data'}, 'type': ''}" in result


class TestChunkToText:
    """Tests for _chunk_to_text function."""

    def test_chunk_to_text_with_rich_component_status_update(self):
        """Test chunk with status update rich component returns empty string."""
        chunk = ChatStreamChunk(
            rich={"type": "status_bar_update", "data": {"status": "Thinking..."}},
            simple=None,
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        assert result == ""

    def test_chunk_to_text_with_rich_component_text(self):
        """Test chunk with text rich component returns content."""
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {"content": "Hello world"}},
            simple=None,
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        assert result == "Hello world"

    def test_chunk_to_text_with_simple_text(self):
        """Test chunk with simple text returns content."""
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {}},  # rich is required, provide empty dict
            simple={"text": "Simple text content"},
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        assert result == "Simple text content"

    def test_chunk_to_text_with_simple_dict_text(self):
        """Test chunk with simple dict text returns content."""
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {}},  # rich is required
            simple={"text": "Dict text"},
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        assert result == "Dict text"

    def test_chunk_to_text_with_empty_simple(self):
        """Test chunk with empty simple dict returns empty string."""
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {}},  # rich is required
            simple={},
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        assert result == ""

    def test_chunk_to_text_with_empty_rich(self):
        """Test chunk with empty rich dict returns empty string."""
        chunk = ChatStreamChunk(
            rich={},  # Empty rich dict - empty dict is falsy in Python
            simple=None,
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        # Empty rich dict is falsy, so chunk.rich check fails and returns ""
        assert result == ""

    def test_chunk_to_text_with_both_rich_and_simple(self):
        """Test chunk with both rich and simple prefers simple."""
        chunk = ChatStreamChunk(
            rich={"type": "text", "data": {"content": "Rich content"}},
            simple={"text": "Simple content"},
            conversation_id="test-conv",
            request_id="test-req"
        )
        result = _chunk_to_text(chunk)
        # Simple is checked first, so should return simple content
        assert result == "Simple content"


class TestStreamResponse:
    """Tests for _stream_response function."""

    @pytest.mark.asyncio
    async def test_stream_response_always_emits_done(self):
        """Test that stream always terminates with [DONE]."""
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            yield ChatStreamChunk(
                rich={"type": "text", "data": {"content": "First message"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )
            yield ChatStreamChunk(
                rich={"type": "status_bar_update", "data": {"status": "Thinking..."}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )
            yield ChatStreamChunk(
                rich={"type": "text", "data": {"content": "Second message"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )

        # Create a proper async generator wrapper
        async def async_gen_wrapper():
            async for item in mock_generator():
                yield item

        events = []
        async for event in _stream_response(
            chat_handler=MagicMock(),
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # Last event should be [DONE]
        assert events[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_stream_response_emits_content_for_text_chunks(self):
        """Test that text chunks are emitted in SSE events."""
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            yield ChatStreamChunk(
                rich={"type": "text", "data": {"content": "Hello world"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )

        # We need to mock the chat_handler.handle_stream to return an async generator
        # Use MagicMock with __aiter__ to properly mock async generator
        mock_handler = MagicMock()
        mock_handler.handle_stream = MagicMock(return_value=mock_generator())

        events = []
        async for event in _stream_response(
            chat_handler=mock_handler,
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # Find the content chunk (not the first role chunk, not the done chunk)
        content_events = [e for e in events if "Hello world" in e]
        assert len(content_events) >= 1
        assert "Hello world" in content_events[0]

    @pytest.mark.asyncio
    async def test_stream_response_handles_only_status_chunks_gracefully(self):
        """Test that stream with only status chunks still terminates properly.
        
        This is the KEY test for the stuck behavior bug - if the agent only
        yields status components, the stream should still terminate with [DONE].
        """
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            yield ChatStreamChunk(
                rich={"type": "status_bar_update", "data": {"status": "Analyzing..."}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )
            yield ChatStreamChunk(
                rich={"type": "status_card", "data": {"title": "Processing", "status": "In progress"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )
            yield ChatStreamChunk(
                rich={"type": "progress_display", "data": {"title": "Loading", "current": 50, "total": 100}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )

        mock_handler = AsyncMock()
        mock_handler.handle_stream.return_value = mock_generator()

        events = []
        async for event in _stream_response(
            chat_handler=mock_handler,
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # Stream should still terminate with [DONE] (does NOT hang)
        assert events[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_stream_response_emits_finish_reason_stop(self):
        """Test that final chunk has finish_reason='stop'."""
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            yield ChatStreamChunk(
                rich={"type": "text", "data": {"content": "Final response"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )

        mock_handler = AsyncMock()
        mock_handler.handle_stream.return_value = mock_generator()

        events = []
        async for event in _stream_response(
            chat_handler=mock_handler,
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # Find the done chunk (last event before [DONE])
        done_chunk_event = events[-2]  # Second to last
        assert "finish_reason" in done_chunk_event
        assert '"finish_reason":"stop"' in done_chunk_event or '"finish_reason": "stop"' in done_chunk_event

    @pytest.mark.asyncio
    async def test_stream_response_handles_exception(self):
        """Test that exceptions are caught and stream still terminates."""
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            yield ChatStreamChunk(
                rich={"type": "text", "data": {"content": "Before error"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )
            raise ValueError("Simulated error during streaming")

        mock_handler = AsyncMock()
        mock_handler.handle_stream.return_value = mock_generator()

        events = []
        async for event in _stream_response(
            chat_handler=mock_handler,
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # Should have error chunk
        error_events = [e for e in events if "Error" in e or "error" in e]
        assert len(error_events) >= 1

        # Stream should still terminate with [DONE]
        assert events[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_stream_response_first_chunk_has_role_assistant(self):
        """Test that first chunk sets role to assistant."""
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            yield ChatStreamChunk(
                rich={"type": "text", "data": {"content": "Response"}},
                simple=None,
                conversation_id="test-conv",
                request_id="test-req"
            )

        mock_handler = AsyncMock()
        mock_handler.handle_stream.return_value = mock_generator()

        events = []
        async for event in _stream_response(
            chat_handler=mock_handler,
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # First event should have role: assistant
        first_event = events[0]
        assert '"role":"assistant"' in first_event or '"role": "assistant"' in first_event

    @pytest.mark.asyncio
    async def test_stream_response_empty_generator(self):
        """Test that empty generator still produces valid stream."""
        async def mock_generator() -> AsyncGenerator[ChatStreamChunk, None]:
            return  # Empty generator

        mock_handler = AsyncMock()
        mock_handler.handle_stream.return_value = mock_generator()

        events = []
        async for event in _stream_response(
            chat_handler=mock_handler,
            chat_req=MagicMock(),
            model="test-model"
        ):
            events.append(event)

        # Should still have role chunk and done chunk
        assert len(events) >= 2
        assert events[-1] == "data: [DONE]\n\n"

"""Tests for fastapi server routes - focused on important behavior only."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add src to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from r2-db2.servers.fastapi.app import R2-DB2FastAPIServer
from r2-db2.servers.fastapi.graph_routes import router as graph_router
from r2-db2.servers.fastapi.openai_models import (
    ChatCompletionRequest,
    ChatMessageRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    StreamChoice,
    DeltaContent,
    ChatChoice,
    ChatMessageResponse,
)
from r2-db2.servers.fastapi.routes import register_chat_routes
from r2-db2.servers.fastapi.openai_routes import register_openai_routes
from r2-db2.servers.base import ChatHandler, ChatRequest, ChatResponse, ChatStreamChunk
from r2-db2.core import Agent
from r2-db2.core.user.request_context import RequestContext


# ============== Fixtures ==============

@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = MagicMock(spec=Agent)
    agent.user_resolver = MagicMock()
    return agent


@pytest.fixture
def mock_chat_handler(mock_agent):
    """Create a mock ChatHandler with async handle_stream and handle_poll."""
    handler = MagicMock(spec=ChatHandler)
    handler.agent = mock_agent
    
    # Mock handle_stream to yield some chunks
    async def mock_handle_stream(chat_request):
        yield ChatStreamChunk(
            rich={"type": "text", "text": "Hello"},
            simple={"text": "Hello"},
            conversation_id=chat_request.conversation_id or "conv-123",
            request_id="req-123",
        )
        yield ChatStreamChunk(
            rich={"type": "text", "text": " World"},
            simple={"text": " World"},
            conversation_id=chat_request.conversation_id or "conv-123",
            request_id="req-123",
        )
    
    async def mock_handle_poll(chat_request):
        chunks = []
        async for chunk in mock_handle_stream(chat_request):
            chunks.append(chunk)
        return ChatResponse.from_chunks(chunks)
    
    handler.handle_stream = mock_handle_stream
    handler.handle_poll = mock_handle_poll
    return handler


@pytest.fixture
def fastapi_app(mock_agent, mock_chat_handler):
    """Create a FastAPI app with routes registered."""
    with patch("r2-db2.servers.fastapi.app.ChatHandler", return_value=mock_chat_handler):
        server = R2-DB2FastAPIServer(agent=mock_agent)
        app = server.create_app()
        return app


@pytest.fixture
def client(fastapi_app):
    """Create a TestClient for the FastAPI app."""
    return TestClient(fastapi_app)


# ============== Tests for R2-DB2FastAPIServer.create_app() ==============

class TestR2-DB2FastAPIServerCreateApp:
    """Tests for R2-DB2FastAPIServer.create_app() method."""
    
    def test_registers_chat_routes(self, fastapi_app, client):
        """Test that chat routes are registered."""
        # The /api/r2-db2/v2/chat_poll endpoint should exist
        response = client.post(
            "/api/r2-db2/v2/chat_poll",
            json={"message": "test", "conversation_id": "conv-123"}
        )
        # We expect a 500 because the mock handler will fail, but the route exists
        assert response.status_code in [500, 200]
    
    def test_registers_openai_routes(self, fastapi_app):
        """Test that OpenAI routes are registered."""
        # Check that /v1/models endpoint exists
        with TestClient(fastapi_app) as test_client:
            response = test_client.get("/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) > 0
    
    def test_cors_enabled_by_default(self, client):
        """Test that CORS is enabled by default."""
        # Make a preflight OPTIONS request
        response = client.options(
            "/api/r2-db2/v2/chat_poll",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "POST",
            }
        )
        # Check CORS headers are present
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_cors_can_be_disabled_via_config(self, mock_agent, mock_chat_handler):
        """Test that CORS can be disabled via config."""
        with patch("r2-db2.servers.fastapi.app.ChatHandler", return_value=mock_chat_handler):
            server = R2-DB2FastAPIServer(
                agent=mock_agent,
                config={"cors": {"enabled": False}}
            )
            app = server.create_app()
            
            # Make a preflight OPTIONS request
            with TestClient(app) as test_client:
                response = test_client.options(
                    "/api/r2-db2/v2/chat_poll",
                    headers={
                        "Origin": "http://example.com",
                        "Access-Control-Request-Method": "POST",
                    }
                )
                # CORS headers should NOT be present when disabled
                assert "Access-Control-Allow-Origin" not in response.headers
    
    def test_health_endpoint_returns_expected_payload(self, client):
        """Test that /health returns expected payload."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "r2-db2"


# ============== Tests for OpenAI facade in openai_routes.py ==============

class TestOpenAIRoutes:
    """Tests for OpenAI-compatible API routes."""
    
    def test_v1_models_returns_r2_db2_analyst(self, fastapi_app):
        """Test that GET /v1/models returns r2-db2-analyst."""
        with TestClient(fastapi_app) as test_client:
            response = test_client.get("/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            model_ids = [m["id"] for m in data["data"]]
            assert "r2-db2-analyst" in model_ids
    
    def test_non_stream_path_returns_combined_text(self, mock_agent, mock_chat_handler):
        """Test that non-streaming path returns combined text from streamed chunks."""
        # Create a new app with properly mocked handler that yields simple text
        # We need to patch ChatHandler at the openai_routes module level
        with patch("r2-db2.servers.fastapi.openai_routes.ChatHandler", return_value=mock_chat_handler):
            server = R2-DB2FastAPIServer(agent=mock_agent)
            app = server.create_app()
        
        with TestClient(app) as test_client:
            response = test_client.post(
                "/v1/chat/completions",
                json={
                    "model": "r2-db2-analyst",
                    "messages": [
                        {"role": "user", "content": "What is 2+2?"}
                    ],
                    "stream": False
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "chat.completion"
            assert len(data["choices"]) > 0
            # The combined text should be in the message content
            content = data["choices"][0]["message"]["content"]
            # The mock yields simple text chunks, so check for expected content
            assert "Hello" in content or " World" in content or "Hello World" in content
    
    def test_stream_path_emits_first_role_chunk(self, fastapi_app, mock_chat_handler):
        """Test that streaming path emits first role chunk."""
        with TestClient(fastapi_app) as test_client:
            response = test_client.post(
                "/v1/chat/completions",
                json={
                    "model": "r2-db2-analyst",
                    "messages": [
                        {"role": "user", "content": "What is 2+2?"}
                    ],
                    "stream": True
                },
                headers={"Accept": "text/event-stream"}
            )
            assert response.status_code == 200
            
            # Read the SSE stream
            lines = response.text.strip().split("\n")
            data_lines = [l for l in lines if l.startswith("data: ")]
            
            # First chunk should have role
            first_chunk = json.loads(data_lines[0][6:])  # Remove "data: " prefix
            assert first_chunk["choices"][0]["delta"]["role"] == "assistant"
    
    def test_stream_path_emits_content_chunks(self, mock_agent, mock_chat_handler):
        """Test that streaming path emits content chunks."""
        # Create a new app with properly mocked handler that yields simple text
        with patch("r2-db2.servers.fastapi.openai_routes.ChatHandler", return_value=mock_chat_handler):
            server = R2-DB2FastAPIServer(agent=mock_agent)
            app = server.create_app()
        
        with TestClient(app) as test_client:
            response = test_client.post(
                "/v1/chat/completions",
                json={
                    "model": "r2-db2-analyst",
                    "messages": [
                        {"role": "user", "content": "What is 2+2?"}
                    ],
                    "stream": True
                },
                headers={"Accept": "text/event-stream"}
            )
            assert response.status_code == 200
            
            # Read the SSE stream
            lines = response.text.strip().split("\n")
            data_lines = [l for l in lines if l.startswith("data: ")]
            
            # Check for content chunks (skip [DONE] marker)
            has_content = False
            for line in data_lines[1:]:  # Skip first role chunk
                if line.strip() == "data: [DONE]":
                    continue
                try:
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"]
                    if delta.get("content"):
                        has_content = True
                        break
                except (json.JSONDecodeError, KeyError):
                    continue
            assert has_content, "Should have content chunks"
    
    def test_stream_path_emits_done(self, fastapi_app, mock_chat_handler):
        """Test that streaming path emits [DONE]."""
        with TestClient(fastapi_app) as test_client:
            response = test_client.post(
                "/v1/chat/completions",
                json={
                    "model": "r2-db2-analyst",
                    "messages": [
                        {"role": "user", "content": "What is 2+2?"}
                    ],
                    "stream": True
                },
                headers={"Accept": "text/event-stream"}
            )
            assert response.status_code == 200
            
            # Read the SSE stream
            lines = response.text.strip().split("\n")
            done_lines = [l for l in lines if l == "data: [DONE]"]
            assert len(done_lines) > 0, "Should have [DONE] marker"
    
    def test_empty_user_message_fallback_response(self, fastapi_app):
        """Test that empty user message returns fallback response."""
        with TestClient(fastapi_app) as test_client:
            response = test_client.post(
                "/v1/chat/completions",
                json={
                    "model": "r2-db2-analyst",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant"}
                    ],
                    "stream": False
                }
            )
            assert response.status_code == 200
            data = response.json()
            # Should return a fallback message
            content = data["choices"][0]["message"]["content"]
            assert "No user message" in content or "No response" in content


# ============== Tests for routes.py ==============

class TestChatRoutes:
    """Tests for chat routes in routes.py."""
    
    def test_chat_poll_success_path(self, fastapi_app, mock_chat_handler):
        """Test that /api/r2-db2/v2/chat_poll success path works."""
        with TestClient(fastapi_app) as test_client:
            response = test_client.post(
                "/api/r2-db2/v2/chat_poll",
                json={"message": "test", "conversation_id": "conv-123"}
            )
            # Should return 200 with ChatResponse structure
            assert response.status_code == 200
            data = response.json()
            assert "chunks" in data
            assert "conversation_id" in data
            assert "request_id" in data
            assert "total_chunks" in data
    
    def test_chat_poll_error_path_returns_500(self, mock_agent):
        """Test that /api/r2-db2/v2/chat_poll error path returns HTTP 500."""
        # Create a handler that raises an exception
        handler = MagicMock(spec=ChatHandler)
        handler.agent = mock_agent
        
        async def mock_handle_poll(chat_request):
            raise Exception("Test error")
        
        handler.handle_poll = mock_handle_poll
        
        with patch("r2-db2.servers.fastapi.app.ChatHandler", return_value=handler):
            server = R2-DB2FastAPIServer(agent=mock_agent)
            app = server.create_app()
            
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/api/r2-db2/v2/chat_poll",
                    json={"message": "test", "conversation_id": "conv-123"}
                )
                assert response.status_code == 500
    
    def test_chat_sse_emits_chunks_and_done(self, fastapi_app, mock_chat_handler):
        """Test that /api/r2-db2/v2/chat_sse emits chunks + done."""
        with TestClient(fastapi_app) as test_client:
            response = test_client.post(
                "/api/r2-db2/v2/chat_sse",
                json={"message": "test", "conversation_id": "conv-123"},
                headers={"Accept": "text/event-stream"}
            )
            assert response.status_code == 200
            
            # Read the SSE stream
            lines = response.text.strip().split("\n")
            data_lines = [l for l in lines if l.startswith("data: ")]
            done_lines = [l for l in lines if l == "data: [DONE]"]
            
            assert len(data_lines) > 0, "Should have data chunks"
            assert len(done_lines) > 0, "Should have [DONE] marker"


# ============== Tests for graph_routes.py ==============

class TestGraphRoutes:
    """Tests for LangGraph analytical agent routes."""
    
    @pytest.mark.asyncio
    async def test_analyze_completed_flow(self, mock_agent, mock_chat_handler):
        """Test that /analyze completed flow works."""
        from r2-db2.servers.fastapi.graph_routes import router
        
        # Create a mock graph that returns completed state
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "intent": "new_analysis",
            "report": {"summary": "Test report"},
            "messages": [{"role": "assistant", "content": "Analysis complete"}]
        })
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(
            next=None,  # No pending approval
            values={
                "conversation_id": "conv-123",
                "thread_id": "thread-123"
            }
        ))
        
        # Create app with graph
        app = MagicMock()
        app.state.graph = mock_graph
        
        # Create request
        request = MagicMock()
        request.app = app
        
        # Call the analyze endpoint
        from r2-db2.servers.fastapi.graph_routes import analyze
        response = await analyze(
            request=MagicMock(
                question="What is sales?",
                conversation_id="conv-123",
                user_id="user-123"
            ),
            req=request
        )
        
        assert response.status == "completed"
        assert response.intent == "new_analysis"
        assert response.report is not None
    
    @pytest.mark.asyncio
    async def test_analyze_awaiting_approval_flow(self, mock_agent, mock_chat_handler):
        """Test that /analyze awaiting approval flow when state.next exists."""
        from r2-db2.servers.fastapi.graph_routes import router
        
        # Create a mock graph that returns state with pending approval
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "intent": "new_analysis",
            "plan": {"steps": ["query", "analyze"]}
        })
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(
            next=["hitl_approval"],  # Pending approval
            values={
                "conversation_id": "conv-123",
                "thread_id": "thread-123"
            }
        ))
        
        # Create app with graph
        app = MagicMock()
        app.state.graph = mock_graph
        
        # Create request
        request = MagicMock()
        request.app = app
        
        # Call the analyze endpoint
        from r2-db2.servers.fastapi.graph_routes import analyze
        response = await analyze(
            request=MagicMock(
                question="What is sales?",
                conversation_id="conv-123",
                user_id="user-123"
            ),
            req=request
        )
        
        assert response.status == "awaiting_approval"
        assert response.plan is not None
    
    @pytest.mark.asyncio
    async def test_approve_handles_no_pending_approval_400(self, mock_agent, mock_chat_handler):
        """Test that /approve handles no pending approval (400)."""
        from r2-db2.servers.fastapi.graph_routes import router
        
        # Create a mock graph with no pending approval
        mock_graph = MagicMock()
        mock_graph.aget_state = AsyncMock(return_value=MagicMock(
            next=None,  # No pending approval
            values={}
        ))
        
        # Create app with graph
        app = MagicMock()
        app.state.graph = mock_graph
        
        # Create request
        request = MagicMock()
        request.app = app
        
        # Call the approve endpoint
        from r2-db2.servers.fastapi.graph_routes import approve
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await approve(
                request=MagicMock(
                    thread_id="thread-123",
                    approved=True
                ),
                req=request
            )
        
        assert exc_info.value.status_code == 400
        assert "No pending approval" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_threads_thread_id_state_returns_serialized_state(self, mock_agent, mock_chat_handler):
        """Test that /threads/{thread_id}/state returns serialized state."""
        from r2-db2.servers.fastapi.graph_routes import router
        
        # Create a mock graph state
        mock_state = MagicMock()
        mock_state.values = {"conversation_id": "conv-123", "status": "running"}
        mock_state.next = ["sql_generate"]
        mock_state.created_at = "2024-01-01T00:00:00Z"
        
        mock_graph = MagicMock()
        mock_graph.aget_state = AsyncMock(return_value=mock_state)
        
        # Create app with graph
        app = MagicMock()
        app.state.graph = mock_graph
        
        # Create request
        request = MagicMock()
        request.app = app
        
        # Call the get_thread_state endpoint
        from r2-db2.servers.fastapi.graph_routes import get_thread_state
        response = await get_thread_state(thread_id="thread-123", req=request)
        
        assert response["thread_id"] == "thread-123"
        assert "values" in response
        assert "next" in response
        assert "created_at" in response
    
    @pytest.mark.asyncio
    async def test_reports_report_id_lists_artifacts(self, tmp_path, mock_agent, mock_chat_handler):
        """Test that /reports/{report_id} lists artifacts."""
        # Create a temporary report directory with some files
        report_dir = tmp_path / "report-123"
        report_dir.mkdir()
        (report_dir / "summary.json").write_text('{"test": "data"}')
        (report_dir / "chart.html").write_text("<html></html>")
        
        with patch("r2-db2.config.settings.Settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.report = MagicMock()
            mock_settings_instance.report.output_dir = str(tmp_path)
            mock_settings.return_value = mock_settings_instance
            
            from r2-db2.servers.fastapi.graph_routes import list_report_artifacts
            response = await list_report_artifacts(report_id="report-123")
            
            assert response["report_id"] == "report-123"
            assert len(response["artifacts"]) == 2
            filenames = [a["filename"] for a in response["artifacts"]]
            assert "summary.json" in filenames
            assert "chart.html" in filenames
    
    @pytest.mark.asyncio
    async def test_reports_report_id_filename_download_success(self, tmp_path, mock_agent, mock_chat_handler):
        """Test that /reports/{report_id}/{filename} download success."""
        # Create a temporary report directory with a file
        report_dir = tmp_path / "report-123"
        report_dir.mkdir()
        test_file = report_dir / "summary.json"
        test_file.write_text('{"test": "data"}')
        
        with patch("r2-db2.config.settings.Settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.report = MagicMock()
            mock_settings_instance.report.output_dir = str(tmp_path)
            mock_settings.return_value = mock_settings_instance
            
            from r2-db2.servers.fastapi.graph_routes import download_report_artifact
            from fastapi.responses import FileResponse
            
            response = await download_report_artifact(report_id="report-123", filename="summary.json")
            
            assert isinstance(response, FileResponse)
            assert response.path == str(test_file)
    
    @pytest.mark.asyncio
    async def test_reports_report_id_filename_traversal_protection(self, tmp_path, mock_agent, mock_chat_handler):
        """Test that /reports/{report_id}/{filename} has traversal protection."""
        # Create a temporary report directory with a file inside
        report_dir = tmp_path / "report-123"
        report_dir.mkdir()
        (report_dir / "chart.html").write_text("<div>chart</div>")
        
        # Try to access a file outside the reports directory using traversal
        # Use ../../etc/passwd which resolves to /etc/passwd (outside tmp_path)
        with patch("r2-db2.config.settings.Settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.report = MagicMock()
            mock_settings_instance.report.output_dir = str(tmp_path)
            mock_settings.return_value = mock_settings_instance
            
            from r2-db2.servers.fastapi.graph_routes import download_report_artifact
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as exc_info:
                await download_report_artifact(report_id="report-123", filename="../../etc/passwd")
            
            assert exc_info.value.status_code == 403


# ============== Tests for openai_models.py ==============

class TestOpenAIModels:
    """Tests for OpenAI-compatible models in openai_models.py."""
    
    def test_chat_message_request_validation(self):
        """Test ChatMessageRequest basic validation."""
        # Valid message
        msg = ChatMessageRequest(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        
        # Message without content
        msg = ChatMessageRequest(role="assistant")
        assert msg.role == "assistant"
        assert msg.content is None
    
    def test_chat_completion_request_defaults(self):
        """Test ChatCompletionRequest defaults."""
        req = ChatCompletionRequest(messages=[ChatMessageRequest(role="user", content="test")])
        assert req.model == "r2-db2-analyst"
        assert req.stream is False
        assert req.temperature is None
        assert req.max_tokens is None
        assert req.conversation_id is None
    
    def test_chat_completion_response_defaults(self):
        """Test ChatCompletionResponse defaults."""
        resp = ChatCompletionResponse(
            choices=[ChatChoice(message=ChatMessageResponse(content="test"))]
        )
        assert resp.object == "chat.completion"
        assert resp.model == "r2-db2-analyst"
        assert len(resp.choices) == 1
        assert resp.usage.prompt_tokens == 0
        assert resp.usage.completion_tokens == 0
        assert resp.usage.total_tokens == 0
    
    def test_chat_completion_chunk_defaults(self):
        """Test ChatCompletionChunk defaults."""
        chunk = ChatCompletionChunk(
            choices=[StreamChoice(delta=DeltaContent())]
        )
        assert chunk.object == "chat.completion.chunk"
        assert chunk.model == "r2-db2-analyst"
        assert len(chunk.choices) == 1

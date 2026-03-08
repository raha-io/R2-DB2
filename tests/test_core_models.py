"""Tests for core models and base classes from 7 core subdirectories."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from typing import Any

# Section 1: LLM models and base classes
# ======================================

from r2-db2.core.llm.models import LlmMessage, LlmRequest, LlmResponse, LlmStreamChunk
from r2-db2.core.llm.base import LlmService
from r2-db2.core.user.models import User
from r2-db2.core.tool.models import ToolCall


class TestLlmMessage:
    """Tests for LlmMessage Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating LlmMessage with required fields."""
        message = LlmMessage(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"

    def test_with_tool_calls(self):
        """Test LlmMessage with tool_calls."""
        tool_call = ToolCall(id="tc-1", name="run_sql", arguments={"sql": "SELECT 1"})
        message = LlmMessage(role="assistant", content="I'll run that query", tool_calls=[tool_call])
        assert len(message.tool_calls) == 1


class TestLlmRequest:
    """Tests for LlmRequest Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating LlmRequest with required fields."""
        user = User(id="user-1", username="testuser")
        message = LlmMessage(role="user", content="Hello")
        request = LlmRequest(messages=[message], user=user)
        assert len(request.messages) == 1
        assert request.user.id == "user-1"
        assert request.temperature == 0.7

    def test_temperature_validation(self):
        """Test temperature validation (0.0 to 2.0)."""
        user = User(id="user-1", username="testuser")
        message = LlmMessage(role="user", content="Hello")
        
        request = LlmRequest(messages=[message], user=user, temperature=0.0)
        assert request.temperature == 0.0
        
        request = LlmRequest(messages=[message], user=user, temperature=2.0)
        assert request.temperature == 2.0


class TestLlmResponse:
    """Tests for LlmResponse Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating LlmResponse with content."""
        response = LlmResponse(content="Hello there!")
        assert response.content == "Hello there!"

    def test_is_tool_call_with_tool_calls(self):
        """Test is_tool_call returns True when tool_calls present."""
        tool_call = ToolCall(id="tc-1", name="run_sql", arguments={"sql": "SELECT 1"})
        response = LlmResponse(tool_calls=[tool_call])
        assert response.is_tool_call() is True

    def test_is_tool_call_without_tool_calls(self):
        """Test is_tool_call returns False when no tool_calls."""
        response = LlmResponse(content="Hello")
        assert response.is_tool_call() is False


class MockLlmService(LlmService):
    """Mock implementation of LlmService protocol."""

    async def send_request(self, request: Any) -> Any:
        """Send a request to the LLM."""
        return LlmResponse(content="Mock response")

    async def stream_request(self, request: Any):
        """Stream a request to the LLM."""
        yield LlmStreamChunk(content="Chunk 1")

    async def validate_tools(self, tools: list) -> list:
        """Validate tool schemas and return any errors."""
        return []


class TestLlmServiceProtocol:
    """Tests for LlmService protocol/abstract base class."""

    def test_llm_service_is_abstract(self):
        """Test that LlmService is an abstract base class."""
        assert LlmService.__abstractmethods__ == {"send_request", "stream_request", "validate_tools"}

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_service = MockLlmService()
        assert isinstance(mock_service, LlmService)

    @pytest.mark.asyncio
    async def test_mock_implementation_send_request(self):
        """Test mock implementation of send_request."""
        mock_service = MockLlmService()
        user = User(id="user-1", username="testuser")
        message = LlmMessage(role="user", content="Hello")
        request = LlmRequest(messages=[message], user=user)
        
        response = await mock_service.send_request(request)
        assert isinstance(response, LlmResponse)
        assert response.content == "Mock response"


# Section 2: Audit models and base classes
# =========================================

from r2-db2.core.audit.models import (
    AuditEventType,
    AuditEvent,
    ToolAccessCheckEvent,
    ToolInvocationEvent,
    ToolResultEvent,
    UiFeatureAccessCheckEvent,
    AiResponseEvent,
)
from r2-db2.core.audit.base import AuditLogger


class TestAuditEventType:
    """Tests for AuditEventType enum."""

    def test_all_event_types(self):
        """Test all audit event types are defined."""
        assert AuditEventType.TOOL_ACCESS_CHECK == "tool_access_check"
        assert AuditEventType.TOOL_INVOCATION == "tool_invocation"
        assert AuditEventType.TOOL_RESULT == "tool_result"
        assert AuditEventType.MESSAGE_RECEIVED == "message_received"
        assert AuditEventType.AI_RESPONSE_GENERATED == "ai_response_generated"


class TestAuditEvent:
    """Tests for AuditEvent Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating AuditEvent with required fields."""
        event = AuditEvent(
            event_type=AuditEventType.MESSAGE_RECEIVED,
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1"
        )
        assert event.event_id is not None
        assert event.event_type == AuditEventType.MESSAGE_RECEIVED
        assert event.user_id == "user-1"


class TestToolAccessCheckEvent:
    """Tests for ToolAccessCheckEvent Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolAccessCheckEvent."""
        event = ToolAccessCheckEvent(
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1",
            tool_name="run_sql",
            access_granted=True
        )
        assert event.event_type == AuditEventType.TOOL_ACCESS_CHECK
        assert event.tool_name == "run_sql"
        assert event.access_granted is True


class TestToolInvocationEvent:
    """Tests for ToolInvocationEvent Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolInvocationEvent."""
        event = ToolInvocationEvent(
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1",
            tool_call_id="tc-1",
            tool_name="run_sql"
        )
        assert event.event_type == AuditEventType.TOOL_INVOCATION
        assert event.tool_call_id == "tc-1"
        assert event.tool_name == "run_sql"
        assert event.parameters == {}


class TestToolResultEvent:
    """Tests for ToolResultEvent Pydantic model."""

    def test_valid_instantiation_success(self):
        """Test creating ToolResultEvent with success."""
        event = ToolResultEvent(
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1",
            tool_call_id="tc-1",
            tool_name="run_sql",
            success=True
        )
        assert event.event_type == AuditEventType.TOOL_RESULT
        assert event.success is True

    def test_valid_instantiation_failure(self):
        """Test creating ToolResultEvent with failure."""
        event = ToolResultEvent(
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1",
            tool_call_id="tc-1",
            tool_name="run_sql",
            success=False,
            error="Connection failed"
        )
        assert event.success is False
        assert event.error == "Connection failed"


class TestUiFeatureAccessCheckEvent:
    """Tests for UiFeatureAccessCheckEvent Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating UiFeatureAccessCheckEvent."""
        event = UiFeatureAccessCheckEvent(
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1",
            feature_name="export_pdf",
            access_granted=True
        )
        assert event.event_type == AuditEventType.UI_FEATURE_ACCESS_CHECK
        assert event.feature_name == "export_pdf"


class TestAiResponseEvent:
    """Tests for AiResponseEvent Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating AiResponseEvent."""
        event = AiResponseEvent(
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1",
            response_length_chars=100,
            response_hash="abc123"
        )
        assert event.event_type == AuditEventType.AI_RESPONSE_GENERATED
        assert event.response_length_chars == 100
        assert event.response_hash == "abc123"


class MockAuditLogger(AuditLogger):
    """Mock implementation of AuditLogger protocol."""

    def __init__(self):
        self.events = []

    async def log_event(self, event: Any) -> None:
        """Log a single audit event."""
        self.events.append(event)


class TestAuditLoggerProtocol:
    """Tests for AuditLogger protocol/abstract base class."""

    def test_audit_logger_is_abstract(self):
        """Test that AuditLogger is an abstract base class."""
        assert AuditLogger.__abstractmethods__ == {"log_event"}

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_logger = MockAuditLogger()
        assert isinstance(mock_logger, AuditLogger)

    @pytest.mark.asyncio
    async def test_mock_implementation_log_event(self):
        """Test mock implementation of log_event."""
        mock_logger = MockAuditLogger()
        event = AuditEvent(
            event_type=AuditEventType.MESSAGE_RECEIVED,
            user_id="user-1",
            conversation_id="conv-1",
            request_id="req-1"
        )
        await mock_logger.log_event(event)
        assert len(mock_logger.events) == 1


# Section 3: Storage models and base classes
# ==========================================

from r2-db2.core.storage.models import Message, Conversation
from r2-db2.core.storage.base import ConversationStore


class TestMessage:
    """Tests for Message Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating Message with required fields."""
        message = Message(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.timestamp is not None


class TestConversation:
    """Tests for Conversation Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating Conversation with required fields."""
        user = User(id="user-1", username="testuser")
        conversation = Conversation(id="conv-1", user=user)
        assert conversation.id == "conv-1"
        assert conversation.user.id == "user-1"
        assert conversation.messages == []

    def test_add_message(self):
        """Test add_message method."""
        user = User(id="user-1", username="testuser")
        conversation = Conversation(id="conv-1", user=user)
        
        message = Message(role="user", content="Hello")
        conversation.add_message(message)
        
        assert len(conversation.messages) == 1


class MockConversationStore(ConversationStore):
    """Mock implementation of ConversationStore protocol."""

    def __init__(self):
        self.conversations = {}

    async def create_conversation(self, conversation_id: str, user: Any, initial_message: str) -> Any:
        """Create a new conversation with the specified ID."""
        from r2-db2.core.storage.models import Conversation, Message
        
        message = Message(role="user", content=initial_message)
        conversation = Conversation(
            id=conversation_id,
            user=user,
            messages=[message]
        )
        self.conversations[conversation_id] = conversation
        return conversation

    async def get_conversation(self, conversation_id: str, user: Any) -> Any:
        """Get conversation by ID, scoped to user."""
        return self.conversations.get(conversation_id)

    async def update_conversation(self, conversation: Any) -> None:
        """Update conversation with new messages."""
        if conversation.id in self.conversations:
            self.conversations[conversation.id] = conversation

    async def delete_conversation(self, conversation_id: str, user: Any) -> bool:
        """Delete conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            return True
        return False

    async def list_conversations(self, user: Any, limit: int = 50, offset: int = 0) -> list:
        """List conversations for user."""
        return list(self.conversations.values())[offset:offset + limit]


class TestConversationStoreProtocol:
    """Tests for ConversationStore protocol/abstract base class."""

    def test_conversation_store_is_abstract(self):
        """Test that ConversationStore is an abstract base class."""
        expected_methods = {
            "create_conversation",
            "get_conversation",
            "update_conversation",
            "delete_conversation",
            "list_conversations",
        }
        assert ConversationStore.__abstractmethods__ == expected_methods

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_store = MockConversationStore()
        assert isinstance(mock_store, ConversationStore)

    @pytest.mark.asyncio
    async def test_mock_implementation_create_conversation(self):
        """Test mock implementation of create_conversation."""
        mock_store = MockConversationStore()
        user = User(id="user-1", username="testuser")
        
        conversation = await mock_store.create_conversation(
            conversation_id="conv-1",
            user=user,
            initial_message="Hello"
        )
        
        assert conversation.id == "conv-1"
        assert len(conversation.messages) == 1

    @pytest.mark.asyncio
    async def test_mock_implementation_get_conversation(self):
        """Test mock implementation of get_conversation."""
        mock_store = MockConversationStore()
        user = User(id="user-1", username="testuser")
        
        await mock_store.create_conversation("conv-1", user, "Hello")
        conversation = await mock_store.get_conversation("conv-1", user)
        
        assert conversation is not None
        assert conversation.id == "conv-1"

    @pytest.mark.asyncio
    async def test_mock_implementation_delete_conversation(self):
        """Test mock implementation of delete_conversation."""
        mock_store = MockConversationStore()
        user = User(id="user-1", username="testuser")
        
        await mock_store.create_conversation("conv-1", user, "Hello")
        result = await mock_store.delete_conversation("conv-1", user)
        
        assert result is True
        conversation = await mock_store.get_conversation("conv-1", user)
        assert conversation is None


# Section 4: Tool models and base classes
# =======================================

from r2-db2.core.tool.models import ToolCall, ToolResult, ToolSchema, ToolRejection
from r2-db2.core.tool.base import Tool


class TestToolCall:
    """Tests for ToolCall Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolCall with required fields."""
        tool_call = ToolCall(id="tc-1", name="run_sql", arguments={"sql": "SELECT 1"})
        assert tool_call.id == "tc-1"
        assert tool_call.name == "run_sql"
        assert tool_call.arguments == {"sql": "SELECT 1"}


class TestToolResult:
    """Tests for ToolResult Pydantic model."""

    def test_valid_instantiation_success(self):
        """Test creating ToolResult with success."""
        result = ToolResult(
            success=True,
            result_for_llm="Query executed successfully"
        )
        assert result.success is True
        assert result.result_for_llm == "Query executed successfully"

    def test_valid_instantiation_failure(self):
        """Test creating ToolResult with failure."""
        result = ToolResult(
            success=False,
            result_for_llm="Error occurred",
            error="Connection failed"
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestToolSchema:
    """Tests for ToolSchema Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolSchema with required fields."""
        schema = ToolSchema(
            name="run_sql",
            description="Execute SQL queries",
            parameters={"type": "object", "properties": {}}
        )
        assert schema.name == "run_sql"
        assert schema.description == "Execute SQL queries"
        assert schema.access_groups == []


class TestToolRejection:
    """Tests for ToolRejection Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolRejection with required fields."""
        rejection = ToolRejection(reason="User not authorized")
        assert rejection.reason == "User not authorized"


class MockTool(Tool):
    """Mock implementation of Tool protocol."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def access_groups(self) -> list:
        return ["admin"]

    def get_args_schema(self):
        from pydantic import BaseModel

        class Args(BaseModel):
            query: str

        return Args

    async def execute(self, context: Any, args: Any) -> ToolResult:
        return ToolResult(
            success=True,
            result_for_llm=f"Executed {args.query}"
        )


class TestToolProtocol:
    """Tests for Tool protocol/abstract base class."""

    def test_tool_is_abstract(self):
        """Test that Tool is an abstract base class."""
        expected_methods = {"name", "description", "get_args_schema", "execute"}
        assert Tool.__abstractmethods__ == expected_methods

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_tool = MockTool()
        assert isinstance(mock_tool, Tool)

    def test_mock_implementation_name(self):
        """Test mock implementation of name property."""
        mock_tool = MockTool()
        assert mock_tool.name == "mock_tool"

    def test_mock_implementation_description(self):
        """Test mock implementation of description property."""
        mock_tool = MockTool()
        assert mock_tool.description == "A mock tool for testing"

    def test_mock_implementation_get_schema(self):
        """Test mock implementation of get_schema method."""
        mock_tool = MockTool()
        schema = mock_tool.get_schema()
        assert schema.name == "mock_tool"
        assert schema.description == "A mock tool for testing"


# Section 5: User models and base classes
# =======================================

from r2-db2.core.user.models import User
from r2-db2.core.user.base import UserService
from r2-db2.core.user.request_context import RequestContext
from r2-db2.core.user.resolver import UserResolver


class TestUser:
    """Tests for User Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating User with required fields."""
        user = User(id="user-1")
        assert user.id == "user-1"
        assert user.username is None
        assert user.email is None
        assert user.metadata == {}
        assert user.group_memberships == []

    def test_with_optional_fields(self):
        """Test User with all optional fields."""
        user = User(
            id="user-1",
            username="testuser",
            email="test@example.com",
            metadata={"role": "admin"},
            group_memberships=["admin", "data"]
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.metadata == {"role": "admin"}
        assert user.group_memberships == ["admin", "data"]


class TestRequestContext:
    """Tests for RequestContext Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating RequestContext with required fields."""
        context = RequestContext()
        assert context.cookies == {}
        assert context.headers == {}
        assert context.remote_addr is None

    def test_with_cookies_and_headers(self):
        """Test RequestContext with cookies and headers."""
        context = RequestContext(
            cookies={"session": "abc123"},
            headers={"Authorization": "Bearer token"},
            remote_addr="192.168.1.1"
        )
        assert context.cookies == {"session": "abc123"}
        assert context.headers == {"Authorization": "Bearer token"}
        assert context.remote_addr == "192.168.1.1"

    def test_get_cookie(self):
        """Test get_cookie method."""
        context = RequestContext(cookies={"session": "abc123"})
        
        assert context.get_cookie("session") == "abc123"
        assert context.get_cookie("nonexistent") is None
        assert context.get_cookie("nonexistent", "default") == "default"

    def test_get_header(self):
        """Test get_header method (case-insensitive)."""
        context = RequestContext(headers={"Authorization": "Bearer token"})
        
        assert context.get_header("Authorization") == "Bearer token"
        assert context.get_header("authorization") == "Bearer token"


class MockUserService(UserService):
    """Mock implementation of UserService protocol."""

    def __init__(self):
        self.users = {
            "user-1": User(id="user-1", username="testuser", email="test@example.com"),
            "user-2": User(id="user-2", username="admin", email="admin@example.com", group_memberships=["admin"]),
        }

    async def get_user(self, user_id: str) -> User:
        """Get user by ID."""
        return self.users.get(user_id)

    async def authenticate(self, credentials: dict) -> User:
        """Authenticate user and return User object if successful."""
        username = credentials.get("username")
        password = credentials.get("password")
        
        if username == "testuser" and password == "password123":
            return self.users.get("user-1")
        return None

    async def has_permission(self, user: User, permission: str) -> bool:
        """Check if user has specific permission."""
        if permission == "admin" and "admin" in user.group_memberships:
            return True
        return False


class MockUserResolver(UserResolver):
    """Mock implementation of UserResolver protocol."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        """Resolve user from request context."""
        auth_header = request_context.get_header("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == "valid-token":
                return User(id="user-1", username="authenticated_user")
        raise ValueError("Authentication failed")


class TestUserServiceProtocol:
    """Tests for UserService protocol/abstract base class."""

    def test_user_service_has_all_required_methods(self):
        """Test that UserService defines all required methods."""
        required_methods = ["get_user", "authenticate", "has_permission"]
        for method in required_methods:
            assert hasattr(UserService, method)

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_service = MockUserService()
        assert isinstance(mock_service, UserService)

    @pytest.mark.asyncio
    async def test_mock_implementation_get_user(self):
        """Test mock implementation of get_user."""
        mock_service = MockUserService()
        
        user = await mock_service.get_user("user-1")
        assert user.id == "user-1"
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_mock_implementation_authenticate_success(self):
        """Test mock implementation of authenticate with success."""
        mock_service = MockUserService()
        
        user = await mock_service.authenticate({"username": "testuser", "password": "password123"})
        assert user is not None
        assert user.id == "user-1"

    @pytest.mark.asyncio
    async def test_mock_implementation_authenticate_failure(self):
        """Test mock implementation of authenticate with failure."""
        mock_service = MockUserService()
        
        user = await mock_service.authenticate({"username": "testuser", "password": "wrong"})
        assert user is None

    @pytest.mark.asyncio
    async def test_mock_implementation_has_permission(self):
        """Test mock implementation of has_permission."""
        mock_service = MockUserService()
        
        user = await mock_service.get_user("user-2")
        has_admin = await mock_service.has_permission(user, "admin")
        has_read = await mock_service.has_permission(user, "read")
        
        assert has_admin is True
        assert has_read is False


class TestUserResolverProtocol:
    """Tests for UserResolver protocol/abstract base class."""

    def test_user_resolver_has_all_required_methods(self):
        """Test that UserResolver defines all required methods."""
        assert hasattr(UserResolver, "resolve_user")

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_resolver = MockUserResolver()
        assert isinstance(mock_resolver, UserResolver)

    @pytest.mark.asyncio
    async def test_mock_implementation_resolve_user_success(self):
        """Test mock implementation of resolve_user with success."""
        mock_resolver = MockUserResolver()
        context = RequestContext(headers={"Authorization": "Bearer valid-token"})
        
        user = await mock_resolver.resolve_user(context)
        assert user.id == "user-1"
        assert user.username == "authenticated_user"

    @pytest.mark.asyncio
    async def test_mock_implementation_resolve_user_failure(self):
        """Test mock implementation of resolve_user with failure."""
        mock_resolver = MockUserResolver()
        context = RequestContext(headers={"Authorization": "Bearer invalid-token"})
        
        with pytest.raises(ValueError):
            await mock_resolver.resolve_user(context)


# Section 6: Observability models and base classes
# ================================================

from r2-db2.core.observability.models import Span, Metric
from r2-db2.core.observability.base import ObservabilityProvider


class TestSpan:
    """Tests for Span Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating Span with required fields."""
        span = Span(name="test_operation")
        assert span.id is not None
        assert span.name == "test_operation"
        assert span.start_time is not None
        assert span.end_time is None
        assert span.attributes == {}

    def test_with_attributes(self):
        """Test Span with attributes."""
        span = Span(
            name="test_operation",
            attributes={"key": "value", "status": "success"}
        )
        assert span.attributes == {"key": "value", "status": "success"}

    def test_end(self):
        """Test end method."""
        span = Span(name="test_operation")
        span.end()
        assert span.end_time is not None

    def test_set_attribute(self):
        """Test set_attribute method."""
        span = Span(name="test_operation")
        span.set_attribute("key1", "value1")
        
        assert span.attributes == {"key1": "value1"}


class TestMetric:
    """Tests for Metric Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating Metric with required fields."""
        metric = Metric(name="test_metric", value=100.0)
        assert metric.name == "test_metric"
        assert metric.value == 100.0
        assert metric.unit == ""
        assert metric.tags == {}

    def test_with_unit_and_tags(self):
        """Test Metric with unit and tags."""
        metric = Metric(
            name="request_duration",
            value=150.5,
            unit="ms",
            tags={"endpoint": "/api/users", "method": "GET"}
        )
        assert metric.unit == "ms"
        assert metric.tags == {"endpoint": "/api/users", "method": "GET"}


class MockObservabilityProvider(ObservabilityProvider):
    """Mock implementation of ObservabilityProvider protocol."""

    def __init__(self):
        self.metrics = []
        self.spans = []

    async def record_metric(self, name: str, value: float, unit: str = "", tags: dict = None) -> None:
        """Record a metric measurement."""
        self.metrics.append({
            "name": name,
            "value": value,
            "unit": unit,
            "tags": tags or {}
        })

    async def create_span(self, name: str, attributes: dict = None) -> Span:
        """Create a new span for tracing."""
        span = Span(name=name, attributes=attributes or {})
        self.spans.append(span)
        return span

    async def end_span(self, span: Span) -> None:
        """End a span and record it."""
        span.end()


class TestObservabilityProviderProtocol:
    """Tests for ObservabilityProvider protocol/abstract base class."""

    def test_observability_provider_has_all_required_methods(self):
        """Test that ObservabilityProvider defines all required methods."""
        required_methods = ["record_metric", "create_span", "end_span"]
        for method in required_methods:
            assert hasattr(ObservabilityProvider, method)

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_provider = MockObservabilityProvider()
        assert isinstance(mock_provider, ObservabilityProvider)

    @pytest.mark.asyncio
    async def test_mock_implementation_record_metric(self):
        """Test mock implementation of record_metric."""
        mock_provider = MockObservabilityProvider()
        
        await mock_provider.record_metric(
            name="test_metric",
            value=100.0,
            unit="ms",
            tags={"key": "value"}
        )
        
        assert len(mock_provider.metrics) == 1
        assert mock_provider.metrics[0]["name"] == "test_metric"

    @pytest.mark.asyncio
    async def test_mock_implementation_create_span(self):
        """Test mock implementation of create_span."""
        mock_provider = MockObservabilityProvider()
        
        span = await mock_provider.create_span(
            name="test_span",
            attributes={"key": "value"}
        )
        
        assert span.name == "test_span"
        assert span.attributes == {"key": "value"}


# Section 7: Recovery models and base classes
# ===========================================

from r2-db2.core.recovery.models import RecoveryActionType, RecoveryAction
from r2-db2.core.recovery.base import ErrorRecoveryStrategy


class TestRecoveryActionType:
    """Tests for RecoveryActionType enum."""

    def test_all_action_types(self):
        """Test all recovery action types are defined."""
        assert RecoveryActionType.RETRY == "retry"
        assert RecoveryActionType.FAIL == "fail"
        assert RecoveryActionType.FALLBACK == "fallback"
        assert RecoveryActionType.SKIP == "skip"


class TestRecoveryAction:
    """Tests for RecoveryAction Pydantic model."""

    def test_valid_instantiation_retry(self):
        """Test creating RecoveryAction with retry action."""
        action = RecoveryAction(
            action=RecoveryActionType.RETRY,
            retry_delay_ms=1000,
            message="Retrying operation"
        )
        assert action.action == RecoveryActionType.RETRY
        assert action.retry_delay_ms == 1000
        assert action.message == "Retrying operation"

    def test_valid_instantiation_fail(self):
        """Test creating RecoveryAction with fail action."""
        action = RecoveryAction(
            action=RecoveryActionType.FAIL,
            message="Operation failed"
        )
        assert action.action == RecoveryActionType.FAIL
        assert action.message == "Operation failed"

    def test_valid_instantiation_fallback(self):
        """Test creating RecoveryAction with fallback action."""
        action = RecoveryAction(
            action=RecoveryActionType.FALLBACK,
            fallback_value={"cached": True},
            message="Using fallback value"
        )
        assert action.action == RecoveryActionType.FALLBACK
        assert action.fallback_value == {"cached": True}

    def test_valid_instantiation_skip(self):
        """Test creating RecoveryAction with skip action."""
        action = RecoveryAction(
            action=RecoveryActionType.SKIP,
            message="Skipping operation"
        )
        assert action.action == RecoveryActionType.SKIP


class MockErrorRecoveryStrategy(ErrorRecoveryStrategy):
    """Mock implementation of ErrorRecoveryStrategy protocol."""

    async def handle_tool_error(self, error: Exception, context: Any, attempt: int = 1) -> RecoveryAction:
        """Handle errors during tool execution."""
        if attempt < 3:
            return RecoveryAction(
                action=RecoveryActionType.RETRY,
                retry_delay_ms=attempt * 1000,
                message=f"Retrying after {attempt * 1000}ms"
            )
        return RecoveryAction(
            action=RecoveryActionType.FAIL,
            message="Max retries exceeded"
        )

    async def handle_llm_error(self, error: Exception, request: Any, attempt: int = 1) -> RecoveryAction:
        """Handle errors during LLM communication."""
        return RecoveryAction(
            action=RecoveryActionType.FALLBACK,
            fallback_value={"fallback": True},
            message="Using fallback for LLM error"
        )


class TestErrorRecoveryStrategyProtocol:
    """Tests for ErrorRecoveryStrategy protocol/abstract base class."""

    def test_error_recovery_strategy_has_all_required_methods(self):
        """Test that ErrorRecoveryStrategy defines all required methods."""
        required_methods = ["handle_tool_error", "handle_llm_error"]
        for method in required_methods:
            assert hasattr(ErrorRecoveryStrategy, method)

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_strategy = MockErrorRecoveryStrategy()
        assert isinstance(mock_strategy, ErrorRecoveryStrategy)

    @pytest.mark.asyncio
    async def test_mock_implementation_handle_tool_error_retry(self):
        """Test mock implementation of handle_tool_error with retry."""
        mock_strategy = MockErrorRecoveryStrategy()
        
        action = await mock_strategy.handle_tool_error(
            error=ValueError("Test error"),
            context=None,
            attempt=1
        )
        
        assert action.action == RecoveryActionType.RETRY
        assert action.retry_delay_ms == 1000

    @pytest.mark.asyncio
    async def test_mock_implementation_handle_tool_error_fail(self):
        """Test mock implementation of handle_tool_error with fail."""
        mock_strategy = MockErrorRecoveryStrategy()
        
        action = await mock_strategy.handle_tool_error(
            error=ValueError("Test error"),
            context=None,
            attempt=3
        )
        
        assert action.action == RecoveryActionType.FAIL

    @pytest.mark.asyncio
    async def test_mock_implementation_handle_llm_error(self):
        """Test mock implementation of handle_llm_error."""
        mock_strategy = MockErrorRecoveryStrategy()
        
        action = await mock_strategy.handle_llm_error(
            error=ValueError("LLM error"),
            request=None
        )
        
        assert action.action == RecoveryActionType.FALLBACK
        assert action.fallback_value == {"fallback": True}

"""Tests for src/r2-db2/core/errors.py exception classes."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from r2-db2.core.errors import (
    AgentError,
    ToolExecutionError,
    ToolNotFoundError,
    PermissionError,
    ConversationNotFoundError,
    LlmServiceError,
    ValidationError,
)


class TestAgentError:
    """Tests for AgentError base exception."""

    def test_agent_error_instantiation(self):
        """Test AgentError can be instantiated."""
        error = AgentError()
        assert isinstance(error, AgentError)
        assert isinstance(error, Exception)

    def test_agent_error_with_message(self):
        """Test AgentError preserves message."""
        msg = "Test agent error message"
        error = AgentError(msg)
        assert str(error) == msg

    def test_agent_error_is_subclass_of_exception(self):
        """Test AgentError is a subclass of Exception."""
        assert issubclass(AgentError, Exception)


class TestToolExecutionError:
    """Tests for ToolExecutionError exception."""

    def test_instantiation(self):
        """Test ToolExecutionError can be instantiated."""
        error = ToolExecutionError()
        assert isinstance(error, ToolExecutionError)

    def test_with_message(self):
        """Test ToolExecutionError preserves message."""
        msg = "Tool execution failed"
        error = ToolExecutionError(msg)
        assert str(error) == msg

    def test_is_subclass_of_agent_error(self):
        """Test ToolExecutionError is a subclass of AgentError."""
        assert issubclass(ToolExecutionError, AgentError)


class TestToolNotFoundError:
    """Tests for ToolNotFoundError exception."""

    def test_instantiation(self):
        """Test ToolNotFoundError can be instantiated."""
        error = ToolNotFoundError()
        assert isinstance(error, ToolNotFoundError)

    def test_with_message(self):
        """Test ToolNotFoundError preserves message."""
        msg = "Tool 'my_tool' not found"
        error = ToolNotFoundError(msg)
        assert str(error) == msg

    def test_is_subclass_of_agent_error(self):
        """Test ToolNotFoundError is a subclass of AgentError."""
        assert issubclass(ToolNotFoundError, AgentError)


class TestPermissionError:
    """Tests for PermissionError exception."""

    def test_instantiation(self):
        """Test PermissionError can be instantiated."""
        error = PermissionError()
        assert isinstance(error, PermissionError)

    def test_with_message(self):
        """Test PermissionError preserves message."""
        msg = "User lacks required permissions"
        error = PermissionError(msg)
        assert str(error) == msg

    def test_is_subclass_of_agent_error(self):
        """Test PermissionError is a subclass of AgentError."""
        assert issubclass(PermissionError, AgentError)


class TestConversationNotFoundError:
    """Tests for ConversationNotFoundError exception."""

    def test_instantiation(self):
        """Test ConversationNotFoundError can be instantiated."""
        error = ConversationNotFoundError()
        assert isinstance(error, ConversationNotFoundError)

    def test_with_message(self):
        """Test ConversationNotFoundError preserves message."""
        msg = "Conversation 'abc123' not found"
        error = ConversationNotFoundError(msg)
        assert str(error) == msg

    def test_is_subclass_of_agent_error(self):
        """Test ConversationNotFoundError is a subclass of AgentError."""
        assert issubclass(ConversationNotFoundError, AgentError)


class TestLlmServiceError:
    """Tests for LlmServiceError exception."""

    def test_instantiation(self):
        """Test LlmServiceError can be instantiated."""
        error = LlmServiceError()
        assert isinstance(error, LlmServiceError)

    def test_with_message(self):
        """Test LlmServiceError preserves message."""
        msg = "LLM service unavailable"
        error = LlmServiceError(msg)
        assert str(error) == msg

    def test_is_subclass_of_agent_error(self):
        """Test LlmServiceError is a subclass of AgentError."""
        assert issubclass(LlmServiceError, AgentError)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_instantiation(self):
        """Test ValidationError can be instantiated."""
        error = ValidationError()
        assert isinstance(error, ValidationError)

    def test_with_message(self):
        """Test ValidationError preserves message."""
        msg = "Invalid data format"
        error = ValidationError(msg)
        assert str(error) == msg

    def test_is_subclass_of_agent_error(self):
        """Test ValidationError is a subclass of AgentError."""
        assert issubclass(ValidationError, AgentError)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_agent_error(self):
        """Test all custom exceptions inherit from AgentError."""
        exceptions = [
            ToolExecutionError,
            ToolNotFoundError,
            PermissionError,
            ConversationNotFoundError,
            LlmServiceError,
            ValidationError,
        ]
        for exc in exceptions:
            assert issubclass(exc, AgentError)

    def test_all_exceptions_inherit_from_exception(self):
        """Test all custom exceptions inherit from Exception."""
        exceptions = [
            AgentError,
            ToolExecutionError,
            ToolNotFoundError,
            PermissionError,
            ConversationNotFoundError,
            LlmServiceError,
            ValidationError,
        ]
        for exc in exceptions:
            assert issubclass(exc, Exception)


class TestExceptionRaising:
    """Tests that exceptions can be raised and caught."""

    def test_raise_agent_error(self):
        """Test raising AgentError."""
        with pytest.raises(AgentError):
            raise AgentError("Test error")

    def test_raise_tool_execution_error(self):
        """Test raising ToolExecutionError."""
        with pytest.raises(ToolExecutionError):
            raise ToolExecutionError("Tool failed")

    def test_raise_tool_not_found_error(self):
        """Test raising ToolNotFoundError."""
        with pytest.raises(ToolNotFoundError):
            raise ToolNotFoundError("Tool not found")

    def test_raise_permission_error(self):
        """Test raising PermissionError."""
        with pytest.raises(PermissionError):
            raise PermissionError("No permission")

    def test_raise_conversation_not_found_error(self):
        """Test raising ConversationNotFoundError."""
        with pytest.raises(ConversationNotFoundError):
            raise ConversationNotFoundError("Not found")

    def test_raise_llm_service_error(self):
        """Test raising LlmServiceError."""
        with pytest.raises(LlmServiceError):
            raise LlmServiceError("Service error")

    def test_raise_validation_error(self):
        """Test raising ValidationError."""
        with pytest.raises(ValidationError):
            raise ValidationError("Invalid")

    def test_catch_base_exception_catches_derived(self):
        """Test catching AgentError catches derived exceptions."""
        with pytest.raises(AgentError):
            raise ToolExecutionError("Tool failed")

    def test_catch_base_exception_catches_all_derived(self):
        """Test catching Exception catches all exceptions."""
        exceptions_to_test = [
            (AgentError, "base"),
            (ToolExecutionError, "tool"),
            (ValidationError, "validation"),
        ]
        for exc_class, msg in exceptions_to_test:
            with pytest.raises(Exception):
                raise exc_class(msg)

"""Tests for src/r2-db2/core/registry.py and ToolRegistry class."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from typing import Dict, List, Type
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel, Field

from r2-db2.core.registry import ToolRegistry, _LocalToolWrapper
from r2-db2.core.tool import Tool, ToolCall, ToolContext, ToolRejection, ToolResult, ToolSchema
from r2-db2.core.user import User
from r2-db2.capabilities.agent_memory import AgentMemory
from r2-db2.integrations.local.agent_memory.in_memory import DemoAgentMemory


# ============================================================================
# Mock Tool Implementation for Testing
# ============================================================================

class MockToolArgs(BaseModel):
    """Mock tool arguments model."""
    query: str = Field(description="Query string")
    limit: int = Field(default=10, ge=1, le=100)


class MockTool(Tool[MockToolArgs]):
    """Mock tool implementation for testing."""
    
    @property
    def name(self) -> str:
        return "mock_tool"
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def access_groups(self) -> List[str]:
        return ["admin", "user"]
    
    def get_args_schema(self) -> Type[MockToolArgs]:
        return MockToolArgs
    
    async def execute(self, context: ToolContext, args: MockToolArgs) -> ToolResult:
        return ToolResult(
            success=True,
            result_for_llm=f"Executed: {args.query}",
            ui_component=None,
            error=None,
            metadata={"executed": True}
        )


class MockToolNoAccessGroups(Tool[MockToolArgs]):
    """Mock tool with no access groups (accessible to all)."""
    
    @property
    def name(self) -> str:
        return "public_tool"
    
    @property
    def description(self) -> str:
        return "A public tool"
    
    @property
    def access_groups(self) -> List[str]:
        return []
    
    def get_args_schema(self) -> Type[MockToolArgs]:
        return MockToolArgs
    
    async def execute(self, context: ToolContext, args: MockToolArgs) -> ToolResult:
        return ToolResult(
            success=True,
            result_for_llm=f"Public: {args.query}",
            ui_component=None,
            error=None
        )


class MockToolAdminOnly(Tool[MockToolArgs]):
    """Mock tool accessible only to admin group."""
    
    @property
    def name(self) -> str:
        return "admin_tool"
    
    @property
    def description(self) -> str:
        return "An admin-only tool"
    
    @property
    def access_groups(self) -> List[str]:
        return ["admin"]
    
    def get_args_schema(self) -> Type[MockToolArgs]:
        return MockToolArgs
    
    async def execute(self, context: ToolContext, args: MockToolArgs) -> ToolResult:
        return ToolResult(
            success=True,
            result_for_llm=f"Admin: {args.query}",
            ui_component=None,
            error=None
        )


# ============================================================================
# Test _LocalToolWrapper
# ============================================================================

class TestLocalToolWrapper:
    """Tests for _LocalToolWrapper class."""
    
    def test_wrapper_preserves_name(self):
        """Test that wrapper preserves wrapped tool's name."""
        mock_tool = MockTool()
        wrapper = _LocalToolWrapper(mock_tool, ["admin"])
        assert wrapper.name == "mock_tool"
    
    def test_wrapper_preserves_description(self):
        """Test that wrapper preserves wrapped tool's description."""
        mock_tool = MockTool()
        wrapper = _LocalToolWrapper(mock_tool, ["admin"])
        assert wrapper.description == "A mock tool for testing"
    
    def test_wrapper_stores_access_groups(self):
        """Test that wrapper stores access groups."""
        mock_tool = MockTool()
        wrapper = _LocalToolWrapper(mock_tool, ["admin", "user"])
        assert wrapper.access_groups == ["admin", "user"]
    
    def test_wrapper_preserves_args_schema(self):
        """Test that wrapper preserves args schema."""
        mock_tool = MockTool()
        wrapper = _LocalToolWrapper(mock_tool, ["admin"])
        assert wrapper.get_args_schema() == MockToolArgs
    
    @pytest.mark.asyncio
    async def test_wrapper_delegates_execute(self):
        """Test that wrapper delegates execute to wrapped tool."""
        mock_tool = MockTool()
        wrapper = _LocalToolWrapper(mock_tool, ["admin"])
        
        mock_context = MagicMock(spec=ToolContext)
        mock_args = MockToolArgs(query="test", limit=5)
        
        result = await wrapper.execute(mock_context, mock_args)
        assert result is not None


# ============================================================================
# Test ToolRegistry Initialization
# ============================================================================

class TestToolRegistryInit:
    """Tests for ToolRegistry initialization."""
    
    def test_registry_initializes_with_empty_tools(self):
        """Test that registry starts with empty tools dict."""
        registry = ToolRegistry()
        assert registry._tools == {}
    
    def test_registry_accepts_audit_logger(self):
        """Test that registry accepts optional audit logger."""
        mock_audit_logger = MagicMock()
        registry = ToolRegistry(audit_logger=mock_audit_logger)
        assert registry.audit_logger == mock_audit_logger
    
    def test_registry_accepts_audit_config(self):
        """Test that registry accepts optional audit config."""
        from r2-db2.core.agent.config import AuditConfig
        
        audit_config = AuditConfig(enabled=False)
        registry = ToolRegistry(audit_config=audit_config)
        assert registry.audit_config == audit_config
    
    def test_registry_creates_default_audit_config(self):
        """Test that registry creates default AuditConfig when not provided."""
        registry = ToolRegistry()
        assert registry.audit_config is not None
        assert hasattr(registry.audit_config, 'enabled')


# ============================================================================
# Test register_local_tool
# ============================================================================

class TestRegisterLocalTool:
    """Tests for ToolRegistry.register_local_tool method."""
    
    def test_register_tool_without_access_groups(self):
        """Test registering a tool without access group restrictions."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()
        
        registry.register_local_tool(tool, [])
        
        assert "public_tool" in registry._tools
        assert registry._tools["public_tool"] is tool
    
    def test_register_tool_with_access_groups(self):
        """Test registering a tool with access group restrictions."""
        registry = ToolRegistry()
        tool = MockTool()
        
        registry.register_local_tool(tool, ["admin", "user"])
        
        assert "mock_tool" in registry._tools
        # Should be wrapped with access groups
        assert isinstance(registry._tools["mock_tool"], _LocalToolWrapper)
    
    def test_register_tool_with_single_access_group(self):
        """Test registering a tool with a single access group."""
        registry = ToolRegistry()
        tool = MockToolAdminOnly()
        
        registry.register_local_tool(tool, ["admin"])
        
        assert "admin_tool" in registry._tools
        assert isinstance(registry._tools["admin_tool"], _LocalToolWrapper)
    
    def test_register_duplicate_tool_raises_error(self):
        """Test that registering a duplicate tool raises ValueError."""
        registry = ToolRegistry()
        tool = MockTool()
        
        registry.register_local_tool(tool, ["admin"])
        
        with pytest.raises(ValueError, match="Tool 'mock_tool' already registered"):
            registry.register_local_tool(tool, ["admin"])
    
    def test_register_tool_with_empty_access_groups_list(self):
        """Test registering a tool with empty access groups list."""
        registry = ToolRegistry()
        tool = MockTool()
        
        registry.register_local_tool(tool, [])
        
        # Empty list means no access restrictions
        assert "mock_tool" in registry._tools
        assert registry._tools["mock_tool"] is tool
    
    def test_register_tool_with_none_access_groups(self):
        """Test registering a tool with None access groups."""
        registry = ToolRegistry()
        tool = MockTool()
        
        # None should be treated like empty list (no restrictions)
        registry.register_local_tool(tool, None)
        
        assert "mock_tool" in registry._tools
        # None is falsy, so it should be treated as no restrictions
        assert registry._tools["mock_tool"] is tool


# ============================================================================
# Test get_tool
# ============================================================================

class TestGetTool:
    """Tests for ToolRegistry.get_tool method."""
    
    @pytest.mark.asyncio
    async def test_get_existing_tool_without_access_groups(self):
        """Test getting an existing registered tool without access groups."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()
        registry.register_local_tool(tool, [])
        
        result = await registry.get_tool("public_tool")
        
        assert result is tool
    
    @pytest.mark.asyncio
    async def test_get_existing_tool_with_access_groups(self):
        """Test getting an existing registered tool with access groups."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin"])
        
        result = await registry.get_tool("mock_tool")
        
        # Should return the wrapped tool
        assert isinstance(result, _LocalToolWrapper)
        assert result.name == "mock_tool"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_tool_returns_none(self):
        """Test getting a non-existent tool returns None."""
        registry = ToolRegistry()
        
        result = await registry.get_tool("nonexistent_tool")
        
        assert result is None


# ============================================================================
# Test list_tools
# ============================================================================

class TestListTools:
    """Tests for ToolRegistry.list_tools method."""
    
    @pytest.mark.asyncio
    async def test_list_empty_registry(self):
        """Test listing tools from empty registry."""
        registry = ToolRegistry()
        
        result = await registry.list_tools()
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_list_single_tool(self):
        """Test listing a single registered tool."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin"])
        
        result = await registry.list_tools()
        
        assert result == ["mock_tool"]
    
    @pytest.mark.asyncio
    async def test_list_multiple_tools(self):
        """Test listing multiple registered tools."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = MockToolNoAccessGroups()
        tool3 = MockToolAdminOnly()
        
        registry.register_local_tool(tool1, ["admin"])
        registry.register_local_tool(tool2, [])
        registry.register_local_tool(tool3, ["admin"])
        
        result = await registry.list_tools()
        
        assert set(result) == {"mock_tool", "public_tool", "admin_tool"}
    
    @pytest.mark.asyncio
    async def test_list_tools_returns_copy(self):
        """Test that list_tools returns a copy, not the internal dict."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin"])
        
        result = await registry.list_tools()
        result.append("new_tool")
        
        # Original list should not be modified
        assert "new_tool" not in await registry.list_tools()


# ============================================================================
# Test get_schemas
# ============================================================================

class TestGetSchemas:
    """Tests for ToolRegistry.get_schemas method."""
    
    @pytest.mark.asyncio
    async def test_get_schemas_empty_registry(self):
        """Test getting schemas from empty registry."""
        registry = ToolRegistry()
        
        result = await registry.get_schemas()
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_schemas_with_public_tool(self):
        """Test getting schemas with a public tool."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()
        registry.register_local_tool(tool, [])
        
        result = await registry.get_schemas()
        
        assert len(result) == 1
        assert isinstance(result[0], ToolSchema)
        assert result[0].name == "public_tool"
    
    @pytest.mark.asyncio
    async def test_get_schemas_with_restricted_tool_no_user(self):
        """Test getting schemas with restricted tool and no user."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin"])
        
        result = await registry.get_schemas(user=None)
        
        # Tool has access groups, but user is None, so it should be included
        # (since None user means no restrictions)
        assert len(result) == 1
        assert result[0].name == "mock_tool"
    
    @pytest.mark.asyncio
    async def test_get_schemas_with_restricted_tool_matching_user(self):
        """Test getting schemas with restricted tool and matching user."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin", "user"])
        
        user = User(id="user1", group_memberships=["admin"])
        result = await registry.get_schemas(user=user)
        
        assert len(result) == 1
        assert result[0].name == "mock_tool"
    
    @pytest.mark.asyncio
    async def test_get_schemas_with_restricted_tool_non_matching_user(self):
        """Test getting schemas with restricted tool and non-matching user."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin"])
        
        user = User(id="user1", group_memberships=["user"])
        result = await registry.get_schemas(user=user)
        
        # User doesn't have admin group, so tool should not be included
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_get_schemas_schema_structure(self):
        """Test that returned schemas have correct structure."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()
        registry.register_local_tool(tool, [])
        
        result = await registry.get_schemas()
        
        assert len(result) == 1
        schema = result[0]
        assert schema.name == "public_tool"
        assert schema.description == "A public tool"
        assert schema.parameters is not None
        assert "query" in schema.parameters.get("properties", {})


# ============================================================================
# Helper function to create valid ToolContext
# ============================================================================

def create_valid_context(user: User, conversation_id: str = "conv1", request_id: str = "req1") -> ToolContext:
    """Create a valid ToolContext with a real AgentMemory instance."""
    agent_memory = DemoAgentMemory()
    return ToolContext(
        user=user,
        conversation_id=conversation_id,
        request_id=request_id,
        agent_memory=agent_memory
    )


# ============================================================================
# Test execute - Tool Not Found
# ============================================================================

class TestExecuteToolNotFound:
    """Tests for ToolRegistry.execute when tool is not found."""
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a non-existent tool."""
        registry = ToolRegistry()
        
        user = User(id="user1")
        context = create_valid_context(user)
        
        tool_call = ToolCall(id="call1", name="nonexistent", arguments={})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        assert "not found" in result.result_for_llm.lower()
        assert result.error is not None


# ============================================================================
# Test execute - Permission Denied
# ============================================================================

class TestExecutePermissionDenied:
    """Tests for ToolRegistry.execute when user lacks permission."""
    
    @pytest.mark.asyncio
    async def test_execute_tool_without_permission(self):
        """Test executing a tool without required permissions."""
        registry = ToolRegistry()
        tool = MockToolAdminOnly()
        registry.register_local_tool(tool, ["admin"])
        
        user = User(id="user1", group_memberships=["user"])
        context = create_valid_context(user)
        
        tool_call = ToolCall(id="call1", name="admin_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        assert "Insufficient group access" in result.result_for_llm
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_permission(self):
        """Test executing a tool with required permissions."""
        registry = ToolRegistry()
        tool = MockToolAdminOnly()
        registry.register_local_tool(tool, ["admin"])
        
        user = User(id="user1", group_memberships=["admin"])
        context = create_valid_context(user)
        
        tool_call = ToolCall(id="call1", name="admin_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        assert "Admin:" in result.result_for_llm


# ============================================================================
# Test execute - Invalid Arguments
# ============================================================================

class TestExecuteInvalidArguments:
    """Tests for ToolRegistry.execute with invalid arguments."""
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_missing_required_arg(self):
        """Test executing a tool with missing required argument."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        
        # Missing required 'query' argument
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        assert "Invalid arguments" in result.result_for_llm or "error" in result.result_for_llm.lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_invalid_arg_type(self):
        """Test executing a tool with invalid argument type."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        
        # 'limit' should be int, not string
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"query": "test", "limit": "not_an_int"})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        assert "Invalid arguments" in result.result_for_llm or "error" in result.result_for_llm.lower()


# ============================================================================
# Test execute - Successful Execution
# ============================================================================

class TestExecuteSuccess:
    """Tests for successful ToolRegistry.execute calls."""
    
    @pytest.mark.asyncio
    async def test_execute_successful_tool_call(self):
        """Test successful tool execution."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"query": "SELECT * FROM users", "limit": 5})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        assert "Public: SELECT * FROM users" in result.result_for_llm
        assert result.error is None
        assert "execution_time_ms" in result.metadata


# ============================================================================
# Test transform_args
# ============================================================================

class TestTransformArgs:
    """Tests for ToolRegistry.transform_args method."""
    
    @pytest.mark.asyncio
    async def test_transform_args_default_noop(self):
        """Test that default transform_args returns args unchanged."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        user = User(id="user1")
        context = create_valid_context(user)
        args = MockToolArgs(query="test", limit=10)
        
        result = await registry.transform_args(tool, args, user, context)
        
        assert result is args
        assert result.query == "test"
        assert result.limit == 10
    
    @pytest.mark.asyncio
    async def test_transform_args_returns_rejection(self):
        """Test that transform_args can return ToolRejection."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        user = User(id="user1")
        context = create_valid_context(user)
        args = MockToolArgs(query="test", limit=10)
        
        # Override transform_args to return rejection
        async def custom_transform(tool, args, user, context):
            return ToolRejection(reason="Custom rejection")
        
        registry.transform_args = custom_transform
        
        result = await registry.transform_args(tool, args, user, context)
        
        assert isinstance(result, ToolRejection)
        assert result.reason == "Custom rejection"


# ============================================================================
# Test execute with transform_args rejection
# ============================================================================

class TestExecuteWithTransformRejection:
    """Tests for ToolRegistry.execute when transform_args returns rejection."""
    
    @pytest.mark.asyncio
    async def test_execute_with_transform_rejection(self):
        """Test that execution fails when transform_args returns rejection."""
        registry = ToolRegistry()
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"query": "test", "limit": 10})
        
        # Override transform_args to return rejection
        async def custom_transform(tool, args, user, context):
            return ToolRejection(reason="Not allowed for this user")
        
        registry.transform_args = custom_transform
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        assert "Not allowed for this user" in result.result_for_llm
        assert result.error == "Not allowed for this user"


# ============================================================================
# Test execute with audit logging
# ============================================================================

class TestExecuteWithAudit:
    """Tests for ToolRegistry.execute with audit logging."""
    
    @pytest.mark.asyncio
    async def test_execute_logs_tool_access_check_on_denial(self):
        """Test that audit logger is called when access is denied."""
        from r2-db2.core.audit.base import AuditLogger
        
        mock_audit_logger = AsyncMock(spec=AuditLogger)
        registry = ToolRegistry(audit_logger=mock_audit_logger)
        tool = MockToolAdminOnly()
        registry.register_local_tool(tool, ["admin"])
        
        user = User(id="user1", group_memberships=["user"])
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="admin_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        # Audit logger should be called for access check denial
        assert mock_audit_logger.log_tool_access_check.called
    
    @pytest.mark.asyncio
    async def test_execute_logs_tool_access_check_on_success(self):
        """Test that audit logger is called when access is granted."""
        from r2-db2.core.audit.base import AuditLogger
        
        mock_audit_logger = AsyncMock(spec=AuditLogger)
        registry = ToolRegistry(audit_logger=mock_audit_logger)
        tool = MockToolAdminOnly()
        registry.register_local_tool(tool, ["admin"])
        
        user = User(id="user1", group_memberships=["admin"])
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="admin_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        # Audit logger should be called for access check
        assert mock_audit_logger.log_tool_access_check.called
    
    @pytest.mark.asyncio
    async def test_execute_logs_tool_invocation(self):
        """Test that audit logger is called for tool invocation."""
        from r2-db2.core.audit.base import AuditLogger
        
        mock_audit_logger = AsyncMock(spec=AuditLogger)
        registry = ToolRegistry(audit_logger=mock_audit_logger)
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        # Audit logger should be called for tool invocation
        assert mock_audit_logger.log_tool_invocation.called
    
    @pytest.mark.asyncio
    async def test_execute_logs_tool_result(self):
        """Test that audit logger is called for tool result."""
        from r2-db2.core.audit.base import AuditLogger
        
        mock_audit_logger = AsyncMock(spec=AuditLogger)
        registry = ToolRegistry(audit_logger=mock_audit_logger)
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        # Audit logger should be called for tool result
        assert mock_audit_logger.log_tool_result.called


# ============================================================================
# Test execute with audit disabled
# ============================================================================

class TestExecuteWithAuditDisabled:
    """Tests for ToolRegistry.execute when audit is disabled."""
    
    @pytest.mark.asyncio
    async def test_execute_with_audit_disabled(self):
        """Test that execution works when audit is disabled."""
        from r2-db2.core.audit.base import AuditLogger
        from r2-db2.core.agent.config import AuditConfig
        
        mock_audit_logger = AsyncMock(spec=AuditLogger)
        audit_config = AuditConfig(
            log_tool_access_checks=False,
            log_tool_invocations=False,
            log_tool_results=False
        )
        registry = ToolRegistry(
            audit_logger=mock_audit_logger,
            audit_config=audit_config
        )
        tool = MockToolNoAccessGroups()  # Use tool without access groups
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="public_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        # Audit logger should NOT be called when audit is disabled
        assert not mock_audit_logger.log_tool_access_check.called
        assert not mock_audit_logger.log_tool_invocation.called
        assert not mock_audit_logger.log_tool_result.called


# ============================================================================
# Test execute with tool execution error
# ============================================================================

class TestExecuteWithToolError:
    """Tests for ToolRegistry.execute when tool execution fails."""
    
    @pytest.mark.asyncio
    async def test_execute_with_tool_execution_error(self):
        """Test that execution error is properly handled."""
        class ErrorTool(Tool[MockToolArgs]):
            @property
            def name(self) -> str:
                return "error_tool"
            
            @property
            def description(self) -> str:
                return "A tool that always fails"
            
            @property
            def access_groups(self) -> List[str]:
                return []
            
            def get_args_schema(self) -> Type[MockToolArgs]:
                return MockToolArgs
            
            async def execute(self, context: ToolContext, args: MockToolArgs) -> ToolResult:
                raise RuntimeError("Intentional failure")
        
        registry = ToolRegistry()
        tool = ErrorTool()
        registry.register_local_tool(tool, [])
        
        user = User(id="user1")
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="error_tool", arguments={"query": "test", "limit": 10})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is False
        assert "Execution failed" in result.result_for_llm
        assert "Intentional failure" in result.error


# ============================================================================
# Test edge cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases in ToolRegistry."""
    
    @pytest.mark.asyncio
    async def test_get_tool_name_property(self):
        """Test that tool name property is correctly accessed."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register_local_tool(tool, ["admin"])
        
        result = await registry.get_tool("mock_tool")
        assert result is not None
        assert result.name == "mock_tool"
    
    @pytest.mark.asyncio
    async def test_list_tools_order_preserved(self):
        """Test that list_tools preserves insertion order."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = MockToolNoAccessGroups()
        tool3 = MockToolAdminOnly()
        
        registry.register_local_tool(tool1, ["admin"])
        registry.register_local_tool(tool2, [])
        registry.register_local_tool(tool3, ["admin"])
        
        result = await registry.list_tools()
        
        # Order should be preserved (insertion order)
        assert result == ["mock_tool", "public_tool", "admin_tool"]


# ============================================================================
# Integration tests
# ============================================================================

class TestIntegration:
    """Integration tests for ToolRegistry."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete workflow: register, list, get, execute."""
        registry = ToolRegistry()
        
        # Register tools
        tool1 = MockTool()
        tool2 = MockToolNoAccessGroups()
        registry.register_local_tool(tool1, ["admin"])
        registry.register_local_tool(tool2, [])
        
        # List tools
        tools = await registry.list_tools()
        assert set(tools) == {"mock_tool", "public_tool"}
        
        # Get tools
        retrieved_tool = await registry.get_tool("mock_tool")
        assert retrieved_tool is not None
        assert retrieved_tool.name == "mock_tool"
        
        # Execute tool
        user = User(id="user1", group_memberships=["admin"])
        context = create_valid_context(user)
        tool_call = ToolCall(id="call1", name="mock_tool", arguments={"query": "test", "limit": 5})
        
        result = await registry.execute(tool_call, context)
        
        assert result.success is True
        assert "Executed: test" in result.result_for_llm
    
    @pytest.mark.asyncio
    async def test_multiple_users_with_different_permissions(self):
        """Test multiple users with different permission levels."""
        registry = ToolRegistry()
        admin_tool = MockToolAdminOnly()
        public_tool = MockToolNoAccessGroups()
        
        registry.register_local_tool(admin_tool, ["admin"])
        registry.register_local_tool(public_tool, [])
        
        # Admin user
        admin_user = User(id="admin1", group_memberships=["admin"])
        admin_schemas = await registry.get_schemas(user=admin_user)
        assert len(admin_schemas) == 2  # Both tools
        
        # Regular user
        user = User(id="user1", group_memberships=["user"])
        user_schemas = await registry.get_schemas(user=user)
        assert len(user_schemas) == 1  # Only public tool
        
        # No user
        no_user_schemas = await registry.get_schemas(user=None)
        assert len(no_user_schemas) == 2  # All tools

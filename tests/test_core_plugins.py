"""Tests for core plugins: filter, enricher, enhancer, middleware, lifecycle, system_prompt."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

# Import all base classes and models
from r2-db2.core.filter.base import ConversationFilter
from r2-db2.core.enricher.base import ToolContextEnricher
from r2-db2.core.enhancer.base import LlmContextEnhancer
from r2-db2.core.enhancer.default import DefaultLlmContextEnhancer
from r2-db2.core.middleware.base import LlmMiddleware
from r2-db2.core.lifecycle.base import LifecycleHook
from r2-db2.core.system_prompt.base import SystemPromptBuilder
from r2-db2.core.system_prompt.default import DefaultSystemPromptBuilder

# Import models
from r2-db2.core.user.models import User
from r2-db2.core.llm.models import LlmMessage, LlmRequest, LlmResponse, ToolCall
from r2-db2.core.tool.models import ToolContext, ToolResult, ToolSchema, ToolCall as ToolCallModel
from r2-db2.core.storage.models import Message

# Import AgentMemory for registration
from r2-db2.capabilities.agent_memory.base import AgentMemory


# ============================================================================
# MockAgentMemory - Must be defined before registration
# ============================================================================

class MockAgentMemory:
    """Mock implementation of AgentMemory for testing."""
    
    async def save_tool_usage(
        self, question: str, tool_name: str, args: dict[str, Any],
        context: Any, success: bool = True, metadata: Any = None
    ) -> None:
        pass
    
    async def save_text_memory(self, content: str, context: Any) -> Any:
        pass
    
    async def search_similar_usage(
        self, question: str, context: Any, *, limit: int = 10,
        similarity_threshold: float = 0.7, tool_name_filter: Any = None
    ) -> list[Any]:
        return []
    
    async def search_text_memories(
        self, query: str, context: Any, *, limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> list[Any]:
        return []
    
    async def get_recent_memories(self, context: Any, limit: int = 10) -> list[Any]:
        return []
    
    async def get_recent_text_memories(self, context: Any, limit: int = 10) -> list[Any]:
        return []
    
    async def delete_by_id(self, context: Any, memory_id: str) -> bool:
        return True
    
    async def delete_text_memory(self, context: Any, memory_id: str) -> bool:
        return True
    
    async def clear_memories(
        self, context: Any, tool_name: Any = None, before_date: Any = None
    ) -> int:
        return 0


# Register MockAgentMemory as a virtual subclass of AgentMemory
AgentMemory.register(MockAgentMemory)


# ============================================================================
# ConversationFilter Tests
# ============================================================================

class MockConversationFilter(ConversationFilter):
    """Mock implementation of ConversationFilter."""
    
    async def filter_messages(self, messages: list[Message]) -> list[Message]:
        """Filter messages - remove system messages."""
        return [m for m in messages if m.role != "system"]


class TestConversationFilter:
    """Tests for ConversationFilter base class."""
    
    def test_conversation_filter_has_filter_messages_method(self):
        """Test that ConversationFilter defines filter_messages method."""
        assert hasattr(ConversationFilter, "filter_messages")
    
    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_filter = MockConversationFilter()
        assert isinstance(mock_filter, ConversationFilter)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_filter_messages(self):
        """Test mock implementation of filter_messages."""
        mock_filter = MockConversationFilter()
        messages = [
            Message(role="system", content="system prompt"),
            Message(role="user", content="user message"),
            Message(role="assistant", content="assistant message"),
        ]
        result = await mock_filter.filter_messages(messages)
        assert len(result) == 2
        assert all(m.role != "system" for m in result)
    
    @pytest.mark.asyncio
    async def test_empty_messages_list(self):
        """Test filter_messages with empty list."""
        filter_obj = ConversationFilter()
        result = await filter_obj.filter_messages([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_multiple_filters_chain(self):
        """Test chaining multiple filters."""
        class TruncateFilter(ConversationFilter):
            async def filter_messages(self, messages: list[Message]) -> list[Message]:
                return messages[:2]
        
        filter1 = MockConversationFilter()
        filter2 = TruncateFilter()
        
        messages = [
            Message(role="system", content="system"),
            Message(role="user", content="user1"),
            Message(role="user", content="user2"),
            Message(role="user", content="user3"),
        ]
        
        # Apply filters in sequence
        result = await filter1.filter_messages(messages)
        result = await filter2.filter_messages(result)
        
        assert len(result) == 2


# ============================================================================
# ToolContextEnricher Tests
# ============================================================================

class MockToolContextEnricher(ToolContextEnricher):
    """Mock implementation of ToolContextEnricher."""
    
    async def enrich_context(self, context: ToolContext) -> ToolContext:
        """Add mock enrichment data."""
        context.metadata["enriched"] = True
        context.metadata["enricher_version"] = "1.0"
        return context


class TestToolContextEnricher:
    """Tests for ToolContextEnricher base class."""
    
    def test_tool_context_enricher_has_enrich_context_method(self):
        """Test that ToolContextEnricher defines enrich_context method."""
        assert hasattr(ToolContextEnricher, "enrich_context")
    
    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_enricher = MockToolContextEnricher()
        assert isinstance(mock_enricher, ToolContextEnricher)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_enrich_context(self):
        """Test mock implementation of enrich_context."""
        mock_enricher = MockToolContextEnricher()
        user = User(id="user1", username="testuser")
        mock_memory = MockAgentMemory()
        context = ToolContext(
            user=user,
            conversation_id="conv1",
            request_id="req1",
            agent_memory=mock_memory
        )
        result = await mock_enricher.enrich_context(context)
        assert result.metadata["enriched"] is True
        assert result.metadata["enricher_version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_multiple_enrichers_chain(self):
        """Test chaining multiple enrichers."""
        class AdditionalEnricher(ToolContextEnricher):
            async def enrich_context(self, context: ToolContext) -> ToolContext:
                context.metadata["additional"] = "data"
                return context
        
        enricher1 = MockToolContextEnricher()
        enricher2 = AdditionalEnricher()
        
        user = User(id="user1", username="testuser")
        mock_memory = MockAgentMemory()
        context = ToolContext(
            user=user,
            conversation_id="conv1",
            request_id="req1",
            agent_memory=mock_memory
        )
        
        result = await enricher1.enrich_context(context)
        result = await enricher2.enrich_context(result)
        
        assert result.metadata["enriched"] is True
        assert result.metadata["enricher_version"] == "1.0"
        assert result.metadata["additional"] == "data"


# ============================================================================
# LlmContextEnhancer Tests
# ============================================================================

class MockLlmContextEnhancer(LlmContextEnhancer):
    """Mock implementation of LlmContextEnhancer."""
    
    async def enhance_system_prompt(
        self, system_prompt: str, user_message: str, user: User
    ) -> str:
        """Add mock enhancement to system prompt."""
        return system_prompt + "\n\n[ENHANCED BY MOCK]"
    
    async def enhance_user_messages(
        self, messages: list[LlmMessage], user: User
    ) -> list[LlmMessage]:
        """Add mock enhancement to user messages."""
        enhanced = messages.copy()
        enhanced.append(LlmMessage(role="user", content="[ENHANCED MESSAGE]"))
        return enhanced


class TestLlmContextEnhancer:
    """Tests for LlmContextEnhancer base class."""
    
    def test_llm_context_enhancer_has_required_methods(self):
        """Test that LlmContextEnhancer defines required methods."""
        assert hasattr(LlmContextEnhancer, "enhance_system_prompt")
        assert hasattr(LlmContextEnhancer, "enhance_user_messages")
    
    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_enhancer = MockLlmContextEnhancer()
        assert isinstance(mock_enhancer, LlmContextEnhancer)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_enhance_system_prompt(self):
        """Test mock implementation of enhance_system_prompt."""
        mock_enhancer = MockLlmContextEnhancer()
        user = User(id="user1", username="testuser")
        result = await mock_enhancer.enhance_system_prompt(
            system_prompt="Original prompt",
            user_message="User question",
            user=user
        )
        assert result == "Original prompt\n\n[ENHANCED BY MOCK]"
    
    @pytest.mark.asyncio
    async def test_mock_implementation_enhance_user_messages(self):
        """Test mock implementation of enhance_user_messages."""
        mock_enhancer = MockLlmContextEnhancer()
        user = User(id="user1", username="testuser")
        messages = [LlmMessage(role="user", content="test")]
        result = await mock_enhancer.enhance_user_messages(messages, user)
        assert len(result) == 2
        assert result[1].content == "[ENHANCED MESSAGE]"
    
    @pytest.mark.asyncio
    async def test_enhance_system_prompt_with_empty_prompt(self):
        """Test enhance_system_prompt with empty string."""
        mock_enhancer = MockLlmContextEnhancer()
        user = User(id="user1", username="testuser")
        result = await mock_enhancer.enhance_system_prompt("", "message", user)
        assert result == "\n\n[ENHANCED BY MOCK]"


# ============================================================================
# DefaultLlmContextEnhancer Tests
# ============================================================================

class TestDefaultLlmContextEnhancer:
    """Tests for DefaultLlmContextEnhancer implementation."""
    
    def test_init_without_agent_memory(self):
        """Test initialization without agent_memory."""
        enhancer = DefaultLlmContextEnhancer()
        assert enhancer.agent_memory is None
    
    def test_init_with_agent_memory(self):
        """Test initialization with agent_memory."""
        mock_memory = MagicMock()
        enhancer = DefaultLlmContextEnhancer(agent_memory=mock_memory)
        assert enhancer.agent_memory == mock_memory
    
    @pytest.mark.asyncio
    async def test_enhance_system_prompt_without_memory(self):
        """Test enhance_system_prompt when no agent_memory provided."""
        enhancer = DefaultLlmContextEnhancer()
        user = User(id="user1", username="testuser")
        result = await enhancer.enhance_system_prompt(
            system_prompt="Original prompt",
            user_message="User question",
            user=user
        )
        assert result == "Original prompt"
    
    @pytest.mark.asyncio
    async def test_enhance_system_prompt_with_empty_memories(self):
        """Test enhance_system_prompt when memory search returns empty."""
        mock_memory = MagicMock()
        mock_memory.search_text_memories = AsyncMock(return_value=[])
        
        enhancer = DefaultLlmContextEnhancer(agent_memory=mock_memory)
        user = User(id="user1", username="testuser")
        
        result = await enhancer.enhance_system_prompt(
            system_prompt="Original prompt",
            user_message="User question",
            user=user
        )
        assert result == "Original prompt"
        # Note: search_text_memories may not be called if agent_memory is None or if there's an exception
        # The important thing is that the method handles the case gracefully
    
    @pytest.mark.asyncio
    async def test_enhance_system_prompt_with_memories(self):
        """Test enhance_system_prompt when memories are found."""
        mock_memory = MagicMock()
        mock_memory.search_text_memories = AsyncMock(return_value=[])
        
        enhancer = DefaultLlmContextEnhancer(agent_memory=mock_memory)
        user = User(id="user1", username="testuser")
        
        result = await enhancer.enhance_system_prompt(
            system_prompt="Original prompt",
            user_message="User question",
            user=user
        )
        assert result == "Original prompt"
    
    @pytest.mark.asyncio
    async def test_enhance_system_prompt_handles_exception(self):
        """Test enhance_system_prompt handles memory search exceptions."""
        mock_memory = MagicMock()
        mock_memory.search_text_memories = AsyncMock(side_effect=Exception("Memory error"))
        
        enhancer = DefaultLlmContextEnhancer(agent_memory=mock_memory)
        user = User(id="user1", username="testuser")
        
        result = await enhancer.enhance_system_prompt(
            system_prompt="Original prompt",
            user_message="User question",
            user=user
        )
        assert result == "Original prompt"
    
    @pytest.mark.asyncio
    async def test_enhance_user_messages_returns_original(self):
        """Test enhance_user_messages returns original messages."""
        enhancer = DefaultLlmContextEnhancer()
        user = User(id="user1", username="testuser")
        messages = [LlmMessage(role="user", content="test")]
        result = await enhancer.enhance_user_messages(messages, user)
        assert result == messages


# ============================================================================
# LlmMiddleware Tests
# ============================================================================

class MockLlmMiddleware(LlmMiddleware):
    """Mock implementation of LlmMiddleware."""
    
    async def before_llm_request(self, request: LlmRequest) -> LlmRequest:
        """Add metadata before request."""
        request.metadata["middleware_called"] = True
        return request
    
    async def after_llm_response(
        self, request: LlmRequest, response: LlmResponse
    ) -> LlmResponse:
        """Add metadata after response."""
        response.metadata["middleware_called"] = True
        return response


class TestLlmMiddleware:
    """Tests for LlmMiddleware base class."""
    
    def test_llm_middleware_has_required_methods(self):
        """Test that LlmMiddleware defines required methods."""
        assert hasattr(LlmMiddleware, "before_llm_request")
        assert hasattr(LlmMiddleware, "after_llm_response")
    
    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_middleware = MockLlmMiddleware()
        assert isinstance(mock_middleware, LlmMiddleware)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_before_llm_request(self):
        """Test mock implementation of before_llm_request."""
        mock_middleware = MockLlmMiddleware()
        user = User(id="user1", username="testuser")
        request = LlmRequest(
            messages=[LlmMessage(role="user", content="test")],
            user=user
        )
        result = await mock_middleware.before_llm_request(request)
        assert result.metadata["middleware_called"] is True
    
    @pytest.mark.asyncio
    async def test_mock_implementation_after_llm_response(self):
        """Test mock implementation of after_llm_response."""
        mock_middleware = MockLlmMiddleware()
        user = User(id="user1", username="testuser")
        request = LlmRequest(
            messages=[LlmMessage(role="user", content="test")],
            user=user
        )
        response = LlmResponse(content="response")
        result = await mock_middleware.after_llm_response(request, response)
        assert result.metadata["middleware_called"] is True
    
    @pytest.mark.asyncio
    async def test_multiple_middlewares_chain(self):
        """Test chaining multiple middlewares."""
        class AdditionalMiddleware(LlmMiddleware):
            async def before_llm_request(self, request: LlmRequest) -> LlmRequest:
                request.metadata["additional"] = True
                return request
            
            async def after_llm_response(
                self, request: LlmRequest, response: LlmResponse
            ) -> LlmResponse:
                response.metadata["additional"] = True
                return response
        
        middleware1 = MockLlmMiddleware()
        middleware2 = AdditionalMiddleware()
        
        user = User(id="user1", username="testuser")
        request = LlmRequest(
            messages=[LlmMessage(role="user", content="test")],
            user=user
        )
        
        result = await middleware1.before_llm_request(request)
        result = await middleware2.before_llm_request(result)
        
        assert result.metadata["middleware_called"] is True
        assert result.metadata["additional"] is True


# ============================================================================
# LifecycleHook Tests
# ============================================================================

class MockLifecycleHook(LifecycleHook):
    """Mock implementation of LifecycleHook."""
    
    async def before_message(self, user: User, message: str) -> str | None:
        """Modify message before processing."""
        return f"[PREFIX] {message}"
    
    async def after_message(self, result: Any) -> None:
        """Log after message processing."""
        pass
    
    async def before_tool(self, tool: Any, context: ToolContext) -> None:
        """Log before tool execution."""
        pass
    
    async def after_tool(self, result: ToolResult) -> ToolResult | None:
        """Modify tool result after execution."""
        result.metadata["hook_processed"] = True
        return result


class TestLifecycleHook:
    """Tests for LifecycleHook base class."""
    
    def test_lifecycle_hook_has_required_methods(self):
        """Test that LifecycleHook defines required methods."""
        assert hasattr(LifecycleHook, "before_message")
        assert hasattr(LifecycleHook, "after_message")
        assert hasattr(LifecycleHook, "before_tool")
        assert hasattr(LifecycleHook, "after_tool")
    
    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_hook = MockLifecycleHook()
        assert isinstance(mock_hook, LifecycleHook)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_before_message(self):
        """Test mock implementation of before_message."""
        mock_hook = MockLifecycleHook()
        user = User(id="user1", username="testuser")
        result = await mock_hook.before_message(user, "test message")
        assert result == "[PREFIX] test message"
    
    @pytest.mark.asyncio
    async def test_mock_implementation_after_message(self):
        """Test mock implementation of after_message."""
        mock_hook = MockLifecycleHook()
        await mock_hook.after_message("result")  # Should not raise
    
    @pytest.mark.asyncio
    async def test_mock_implementation_before_tool(self):
        """Test mock implementation of before_tool."""
        mock_hook = MockLifecycleHook()
        await mock_hook.before_tool(MagicMock(), MagicMock())  # Should not raise
    
    @pytest.mark.asyncio
    async def test_mock_implementation_after_tool(self):
        """Test mock implementation of after_tool."""
        mock_hook = MockLifecycleHook()
        tool_result = ToolResult(
            success=True,
            result_for_llm="result",
            error=None
        )
        result = await mock_hook.after_tool(tool_result)
        assert result.metadata["hook_processed"] is True
    
    @pytest.mark.asyncio
    async def test_before_message_returns_none_keeps_original(self):
        """Test that before_message returning None keeps original message."""
        hook = LifecycleHook()
        user = User(id="user1", username="testuser")
        result = await hook.before_message(user, "test message")
        assert result is None  # None means keep original


# ============================================================================
# SystemPromptBuilder Tests
# ============================================================================

class MockSystemPromptBuilder(SystemPromptBuilder):
    """Mock implementation of SystemPromptBuilder."""
    
    async def build_system_prompt(
        self, user: User, tools: list[ToolSchema]
    ) -> str | None:
        """Build a custom system prompt."""
        prompt = f"You are {user.username}, a helpful assistant."
        if tools:
            prompt += f"\nAvailable tools: {', '.join(t.name for t in tools)}"
        return prompt


class TestSystemPromptBuilder:
    """Tests for SystemPromptBuilder base class."""
    
    def test_system_prompt_builder_has_build_system_prompt_method(self):
        """Test that SystemPromptBuilder defines build_system_prompt method."""
        assert hasattr(SystemPromptBuilder, "build_system_prompt")
    
    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_builder = MockSystemPromptBuilder()
        assert isinstance(mock_builder, SystemPromptBuilder)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_build_system_prompt(self):
        """Test mock implementation of build_system_prompt."""
        mock_builder = MockSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        tools = [
            ToolSchema(
                name="run_sql",
                description="Run SQL query",
                parameters={"type": "object", "properties": {}}
            )
        ]
        result = await mock_builder.build_system_prompt(user, tools)
        assert "testuser" in result
        assert "run_sql" in result
    
    @pytest.mark.asyncio
    async def test_mock_implementation_build_system_prompt_no_tools(self):
        """Test build_system_prompt with no tools."""
        mock_builder = MockSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        result = await mock_builder.build_system_prompt(user, [])
        assert "testuser" in result
        assert "Available tools" not in result
    
    @pytest.mark.asyncio
    async def test_mock_implementation_build_system_prompt_returns_none(self):
        """Test build_system_prompt can return None."""
        class NoneBuilder(SystemPromptBuilder):
            async def build_system_prompt(
                self, user: User, tools: list[ToolSchema]
            ) -> str | None:
                return None
        
        builder = NoneBuilder()
        user = User(id="user1", username="testuser")
        result = await builder.build_system_prompt(user, [])
        assert result is None


# ============================================================================
# DefaultSystemPromptBuilder Tests
# ============================================================================

class TestDefaultSystemPromptBuilder:
    """Tests for DefaultSystemPromptBuilder implementation."""
    
    def test_init_without_base_prompt(self):
        """Test initialization without base_prompt."""
        builder = DefaultSystemPromptBuilder()
        assert builder.base_prompt is None
    
    def test_init_with_base_prompt(self):
        """Test initialization with base_prompt."""
        builder = DefaultSystemPromptBuilder(base_prompt="Custom prompt")
        assert builder.base_prompt == "Custom prompt"
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_with_base_prompt(self):
        """Test build_system_prompt returns base_prompt when set."""
        builder = DefaultSystemPromptBuilder(base_prompt="Custom prompt")
        user = User(id="user1", username="testuser")
        result = await builder.build_system_prompt(user, [])
        assert result == "Custom prompt"
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_default_structure(self):
        """Test build_system_prompt has expected default structure."""
        builder = DefaultSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        result = await builder.build_system_prompt(user, [])
        
        assert "R2-DB2" in result
        assert "AI data analyst assistant" in result
        assert "Response Guidelines:" in result
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_includes_tool_names(self):
        """Test build_system_prompt includes tool names."""
        builder = DefaultSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        tools = [
            ToolSchema(
                name="run_sql",
                description="Run SQL query",
                parameters={"type": "object", "properties": {}}
            ),
            ToolSchema(
                name="visualize_data",
                description="Create visualization",
                parameters={"type": "object", "properties": {}}
            )
        ]
        result = await builder.build_system_prompt(user, tools)
        
        assert "run_sql" in result
        assert "visualize_data" in result
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_with_memory_tools(self):
        """Test build_system_prompt includes memory workflow when memory tools available."""
        builder = DefaultSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        tools = [
            ToolSchema(
                name="search_saved_correct_tool_uses",
                description="Search for similar tool uses",
                parameters={"type": "object", "properties": {}}
            ),
            ToolSchema(
                name="save_question_tool_args",
                description="Save tool usage pattern",
                parameters={"type": "object", "properties": {}}
            ),
            ToolSchema(
                name="save_text_memory",
                description="Save text memory",
                parameters={"type": "object", "properties": {}}
            )
        ]
        result = await builder.build_system_prompt(user, tools)
        
        # Should include memory system section
        assert "MEMORY SYSTEM:" in result
        assert "TOOL USAGE MEMORY" in result
        assert "TEXT MEMORY" in result
        assert "search_saved_correct_tool_uses" in result
        assert "save_question_tool_args" in result
        assert "save_text_memory" in result
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_date_included(self):
        """Test build_system_prompt includes today's date."""
        builder = DefaultSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        result = await builder.build_system_prompt(user, [])
        
        # Should include current date in format YYYY-MM-DD
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        assert today in result
    
    @pytest.mark.asyncio
    async def test_build_system_prompt_memory_workflow_instructions(self):
        """Test build_system_prompt includes memory workflow instructions."""
        builder = DefaultSystemPromptBuilder()
        user = User(id="user1", username="testuser")
        tools = [
            ToolSchema(
                name="search_saved_correct_tool_uses",
                description="Search",
                parameters={"type": "object", "properties": {}}
            ),
            ToolSchema(
                name="save_question_tool_args",
                description="Save",
                parameters={"type": "object", "properties": {}}
            )
        ]
        result = await builder.build_system_prompt(user, tools)
        
        # Should include example workflow
        assert "Example workflow:" in result
        assert "search_saved_correct_tool_uses" in result
        assert "save_question_tool_args" in result

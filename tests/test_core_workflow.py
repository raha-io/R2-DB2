"""
Unit tests for core/workflow module.

Tests base.py and default.py workflow handler implementations.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List

# Import workflow module classes
from r2-db2.core.workflow.base import WorkflowHandler, WorkflowResult
from r2-db2.core.workflow.default import DefaultWorkflowHandler

# Import components
from r2-db2.components import (
    UiComponent,
    RichTextComponent,
    CardComponent,
    ButtonComponent,
    ButtonGroupComponent,
    StatusCardComponent,
    SimpleTextComponent,
)

# Import models
from r2-db2.core.user.models import User
from r2-db2.core.storage.models import Conversation, Message


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_agent():
    """Create a mock agent with tool registry."""
    agent = MagicMock()
    agent.tool_registry = MagicMock()
    agent.agent_memory = None
    return agent


@pytest.fixture
def mock_user():
    """Create a mock user."""
    return User(
        id="user-123",
        username="testuser",
        email="test@example.com",
        group_memberships=["admin"],
    )


@pytest.fixture
def mock_user_non_admin():
    """Create a mock non-admin user."""
    return User(
        id="user-456",
        username="regularuser",
        email="user@example.com",
        group_memberships=["user"],
    )


@pytest.fixture
def mock_conversation(mock_user):
    """Create a mock conversation."""
    return Conversation(
        id="conv-123",
        user=mock_user,
        messages=[],
    )


@pytest.fixture
def default_workflow():
    """Create a DefaultWorkflowHandler instance."""
    return DefaultWorkflowHandler()


# ============================================================================
# WorkflowResult Tests (base.py)
# ============================================================================

class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_workflow_result_creation(self):
        """Test basic WorkflowResult creation."""
        result = WorkflowResult(should_skip_llm=True)
        assert result.should_skip_llm is True
        assert result.components is None
        assert result.conversation_mutation is None

    def test_workflow_result_with_components(self):
        """Test WorkflowResult with components."""
        components = [RichTextComponent(content="test", markdown=True)]
        result = WorkflowResult(
            should_skip_llm=True,
            components=components,
        )
        assert result.should_skip_llm is True
        assert result.components == components

    def test_workflow_result_with_conversation_mutation(self):
        """Test WorkflowResult with conversation mutation callback."""
        async def mock_mutation(conv):
            conv.messages.clear()

        result = WorkflowResult(
            should_skip_llm=True,
            conversation_mutation=mock_mutation,
        )
        assert result.should_skip_llm is True
        assert result.conversation_mutation == mock_mutation

    def test_workflow_result_skip_llm_false(self):
        """Test WorkflowResult with should_skip_llm=False."""
        result = WorkflowResult(should_skip_llm=False)
        assert result.should_skip_llm is False


# ============================================================================
# WorkflowHandler Protocol Tests (base.py)
# ============================================================================

class TestWorkflowHandlerProtocol:
    """Tests for WorkflowHandler abstract base class."""

    def test_workflow_handler_is_abstract(self):
        """Test that WorkflowHandler is an abstract class."""
        assert hasattr(WorkflowHandler, '__abstractmethods__')

    def test_workflow_handler_cannot_be_instantiated_without_implementation(self):
        """Test that WorkflowHandler cannot be instantiated without implementation."""

        class IncompleteHandler(WorkflowHandler):
            pass

        with pytest.raises(TypeError, match="abstract class"):
            IncompleteHandler()

    async def test_get_starter_ui_default_returns_none(self):
        """Test that get_starter_ui default implementation returns None."""

        class MinimalHandler(WorkflowHandler):
            async def try_handle(self, agent, user, conversation, message):
                return WorkflowResult(should_skip_llm=False)

        handler = MinimalHandler()
        result = await handler.get_starter_ui(
            agent=MagicMock(),
            user=MagicMock(),
            conversation=MagicMock(),
        )
        assert result is None


# ============================================================================
# DefaultWorkflowHandler Tests (default.py)
# ============================================================================

class TestDefaultWorkflowHandlerInit:
    """Tests for DefaultWorkflowHandler initialization."""

    def test_init_default_welcome_message(self, default_workflow):
        """Test initialization with default welcome message."""
        assert default_workflow.welcome_message is None

    def test_init_custom_welcome_message(self):
        """Test initialization with custom welcome message."""
        custom_msg = "Welcome to my custom workflow!"
        workflow = DefaultWorkflowHandler(welcome_message=custom_msg)
        assert workflow.welcome_message == custom_msg


class TestDefaultWorkflowHandlerAnalyzeSetup:
    """Tests for DefaultWorkflowHandler._analyze_setup method."""

    def test_analyze_setup_no_tools(self, default_workflow):
        """Test analyze_setup with no tools."""
        result = default_workflow._analyze_setup([])

        assert result["has_sql"] is False
        assert result["has_memory"] is False
        assert result["has_search"] is False
        assert result["has_save"] is False
        assert result["has_viz"] is False
        assert result["is_complete"] is False
        assert result["is_functional"] is False
        assert result["tool_count"] == 0

    def test_analyze_setup_with_sql_only(self, default_workflow):
        """Test analyze_setup with only SQL tool."""
        result = default_workflow._analyze_setup(["run_sql"])

        assert result["has_sql"] is True
        assert result["has_memory"] is False
        assert result["is_complete"] is False
        assert result["is_functional"] is True

    def test_analyze_setup_with_all_tools(self, default_workflow):
        """Test analyze_setup with all tools."""
        tools = [
            "run_sql",
            "search_saved_correct_tool_uses",
            "save_question_tool_args",
            "visualize_data",
        ]
        result = default_workflow._analyze_setup(tools)

        assert result["has_sql"] is True
        assert result["has_memory"] is True
        assert result["has_viz"] is True
        assert result["is_complete"] is True
        assert result["is_functional"] is True

    def test_analyze_setup_sql_variations(self, default_workflow):
        """Test analyze_setup with different SQL tool names."""
        sql_variations = ["sql_query", "execute_sql", "query_sql"]
        for sql_tool in sql_variations:
            result = default_workflow._analyze_setup([sql_tool])
            assert result["has_sql"] is True, f"Failed for {sql_tool}"

    def test_analyze_setup_memory_variations(self, default_workflow):
        """Test analyze_setup with memory tool variations."""
        result = default_workflow._analyze_setup(["search_saved_correct_tool_uses"])
        assert result["has_search"] is True
        assert result["has_memory"] is False  # Need both search and save

        result = default_workflow._analyze_setup(["save_question_tool_args"])
        assert result["has_save"] is True
        assert result["has_memory"] is False  # Need both search and save

    def test_analyze_setup_viz_variations(self, default_workflow):
        """Test analyze_setup with visualization tool variations."""
        viz_variations = ["create_chart", "plot_data", "generate_chart"]
        for viz_tool in viz_variations:
            result = default_workflow._analyze_setup([viz_tool])
            assert result["has_viz"] is True, f"Failed for {viz_tool}"


class TestDefaultWorkflowHandlerGenerateStarterCard:
    """Tests for DefaultWorkflowHandler._generate_starter_card method."""

    def test_generate_starter_card_admin_no_sql(self, default_workflow):
        """Test generate_starter_card for admin with no SQL."""
        analysis = {
            "has_sql": False,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": False,
            "tool_count": 0,
            "tool_names": [],
        }

        result = default_workflow._generate_starter_card(analysis, is_admin=True)

        assert isinstance(result, UiComponent)
        assert isinstance(result.rich_component, CardComponent)

    def test_generate_starter_card_admin_complete(self, default_workflow):
        """Test generate_starter_card for admin with complete setup."""
        analysis = {
            "has_sql": True,
            "has_memory": True,
            "has_search": True,
            "has_save": True,
            "has_viz": True,
            "is_complete": True,
            "is_functional": True,
            "tool_count": 4,
            "tool_names": ["run_sql", "search_saved_correct_tool_uses", "save_question_tool_args", "visualize_data"],
        }

        result = default_workflow._generate_starter_card(analysis, is_admin=True)

        assert isinstance(result, UiComponent)
        assert isinstance(result.rich_component, CardComponent)

    def test_generate_starter_card_admin_partial(self, default_workflow):
        """Test generate_starter_card for admin with partial setup."""
        analysis = {
            "has_sql": True,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 1,
            "tool_names": ["run_sql"],
        }

        result = default_workflow._generate_starter_card(analysis, is_admin=True)

        assert isinstance(result, UiComponent)
        assert isinstance(result.rich_component, CardComponent)

    def test_generate_starter_card_user_no_sql(self, default_workflow):
        """Test generate_starter_card for user with no SQL."""
        analysis = {
            "has_sql": False,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": False,
            "tool_count": 0,
            "tool_names": [],
        }

        result = default_workflow._generate_starter_card(analysis, is_admin=False)

        assert isinstance(result, UiComponent)
        assert isinstance(result.rich_component, RichTextComponent)

    def test_generate_starter_card_user_with_sql(self, default_workflow):
        """Test generate_starter_card for user with SQL."""
        analysis = {
            "has_sql": True,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 1,
            "tool_names": ["run_sql"],
        }

        result = default_workflow._generate_starter_card(analysis, is_admin=False)

        assert isinstance(result, UiComponent)
        assert isinstance(result.rich_component, RichTextComponent)


class TestDefaultWorkflowHandlerGenerateAdminStarterCard:
    """Tests for DefaultWorkflowHandler._generate_admin_starter_card method."""

    def test_generate_admin_starter_card_title(self, default_workflow):
        """Test admin starter card title when no SQL."""
        analysis = {
            "has_sql": False,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": False,
            "tool_count": 0,
            "tool_names": [],
        }

        result = default_workflow._generate_admin_starter_card(analysis)

        assert isinstance(result.rich_component, CardComponent)
        assert "Setup Required" in result.rich_component.title

    def test_generate_admin_starter_card_success_title(self, default_workflow):
        """Test admin starter card title when complete setup."""
        analysis = {
            "has_sql": True,
            "has_memory": True,
            "has_search": True,
            "has_save": True,
            "has_viz": True,
            "is_complete": True,
            "is_functional": True,
            "tool_count": 4,
            "tool_names": ["run_sql", "search_saved_correct_tool_uses", "save_question_tool_args", "visualize_data"],
        }

        result = default_workflow._generate_admin_starter_card(analysis)

        assert isinstance(result.rich_component, CardComponent)
        assert "System Ready" in result.rich_component.title

    def test_generate_admin_starter_card_partial_title(self, default_workflow):
        """Test admin starter card title when partial setup."""
        analysis = {
            "has_sql": True,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 1,
            "tool_names": ["run_sql"],
        }

        result = default_workflow._generate_admin_starter_card(analysis)

        assert isinstance(result.rich_component, CardComponent)
        assert "System Ready" in result.rich_component.title

    def test_generate_admin_starter_card_with_content(self, default_workflow):
        """Test admin starter card includes content."""
        analysis = {
            "has_sql": True,
            "has_memory": True,
            "has_search": True,
            "has_save": True,
            "has_viz": True,
            "is_complete": True,
            "is_functional": True,
            "tool_count": 4,
            "tool_names": ["run_sql", "search_saved_correct_tool_uses", "save_question_tool_args", "visualize_data"],
        }

        result = default_workflow._generate_admin_starter_card(analysis)

        assert isinstance(result.rich_component, CardComponent)
        assert result.rich_component.content is not None
        assert "Admin View" in result.rich_component.content


class TestDefaultWorkflowHandlerGenerateUserStarterCard:
    """Tests for DefaultWorkflowHandler._generate_user_starter_card method."""

    def test_generate_user_starter_card_no_sql(self, default_workflow):
        """Test user starter card with no SQL."""
        analysis = {
            "has_sql": False,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": False,
            "tool_count": 0,
            "tool_names": [],
        }

        result = default_workflow._generate_user_starter_card(analysis)

        assert isinstance(result.rich_component, RichTextComponent)
        assert "Setup Required" in result.rich_component.content

    def test_generate_user_starter_card_with_sql(self, default_workflow):
        """Test user starter card with SQL."""
        analysis = {
            "has_sql": True,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 1,
            "tool_names": ["run_sql"],
        }

        result = default_workflow._generate_user_starter_card(analysis)

        assert isinstance(result.rich_component, RichTextComponent)
        assert "Welcome to R2-DB2 AI" in result.rich_component.content


class TestDefaultWorkflowHandlerGenerateSetupStatusCards:
    """Tests for DefaultWorkflowHandler._generate_setup_status_cards method."""

    def test_generate_setup_status_cards_complete(self, default_workflow):
        """Test status cards for complete setup."""
        analysis = {
            "has_sql": True,
            "has_memory": True,
            "has_search": True,
            "has_save": True,
            "has_viz": True,
            "is_complete": True,
            "is_functional": True,
            "tool_count": 4,
            "tool_names": ["run_sql", "search_saved_correct_tool_uses", "save_question_tool_args", "visualize_data"],
        }

        result = default_workflow._generate_setup_status_cards(analysis)

        assert len(result) == 3  # SQL, Memory, Viz
        for component in result:
            assert isinstance(component, UiComponent)

    def test_generate_setup_status_cards_missing_sql(self, default_workflow):
        """Test status cards when SQL is missing."""
        analysis = {
            "has_sql": False,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": False,
            "tool_count": 0,
            "tool_names": [],
        }

        result = default_workflow._generate_setup_status_cards(analysis)

        assert len(result) == 3
        # SQL should be error status
        sql_card = result[0]
        assert isinstance(sql_card.rich_component, StatusCardComponent)
        assert sql_card.rich_component.status == "error"

    def test_generate_setup_status_cards_partial_memory(self, default_workflow):
        """Test status cards with partial memory setup."""
        analysis = {
            "has_sql": True,
            "has_memory": False,
            "has_search": True,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 1,
            "tool_names": ["run_sql"],
        }

        result = default_workflow._generate_setup_status_cards(analysis)

        assert len(result) == 3
        # Memory should be warning status
        memory_card = result[1]
        assert isinstance(memory_card.rich_component, StatusCardComponent)
        assert memory_card.rich_component.status == "warning"


class TestDefaultWorkflowHandlerGenerateSetupGuidance:
    """Tests for DefaultWorkflowHandler._generate_setup_guidance method."""

    def test_generate_setup_guidance_no_sql(self, default_workflow):
        """Test setup guidance when SQL is missing."""
        analysis = {
            "has_sql": False,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": False,
            "tool_count": 0,
            "tool_names": [],
        }

        result = default_workflow._generate_setup_guidance(analysis)

        assert result is not None
        assert isinstance(result, UiComponent)
        assert isinstance(result.rich_component, RichTextComponent)
        assert "Setup Required" in result.rich_component.content

    def test_generate_setup_guidance_missing_memory(self, default_workflow):
        """Test setup guidance when memory is missing."""
        analysis = {
            "has_sql": True,
            "has_memory": False,
            "has_search": False,
            "has_save": False,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 1,
            "tool_names": ["run_sql"],
        }

        result = default_workflow._generate_setup_guidance(analysis)

        assert result is not None
        assert isinstance(result, UiComponent)
        assert "Add Memory Tools" in result.rich_component.content

    def test_generate_setup_guidance_missing_viz(self, default_workflow):
        """Test setup guidance when visualization is missing."""
        analysis = {
            "has_sql": True,
            "has_memory": True,
            "has_search": True,
            "has_save": True,
            "has_viz": False,
            "is_complete": False,
            "is_functional": True,
            "tool_count": 3,
            "tool_names": ["run_sql", "search_saved_correct_tool_uses", "save_question_tool_args"],
        }

        result = default_workflow._generate_setup_guidance(analysis)

        assert result is not None
        assert isinstance(result, UiComponent)
        assert "Add Visualization" in result.rich_component.content

    def test_generate_setup_guidance_complete_no_guidance(self, default_workflow):
        """Test setup guidance returns None for complete setup."""
        analysis = {
            "has_sql": True,
            "has_memory": True,
            "has_search": True,
            "has_save": True,
            "has_viz": True,
            "is_complete": True,
            "is_functional": True,
            "tool_count": 4,
            "tool_names": ["run_sql", "search_saved_correct_tool_uses", "save_question_tool_args", "visualize_data"],
        }

        result = default_workflow._generate_setup_guidance(analysis)

        assert result is None


class TestDefaultWorkflowHandlerGenerateStatusCheck:
    """Tests for DefaultWorkflowHandler._generate_status_check method."""

    @pytest.mark.asyncio
    async def test_generate_status_check_complete(self, default_workflow, mock_user):
        """Test status check for complete setup."""
        mock_agent = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "run_sql"
        mock_tool2 = MagicMock()
        mock_tool2.name = "search_saved_correct_tool_uses"
        mock_tool3 = MagicMock()
        mock_tool3.name = "save_question_tool_args"
        mock_tool4 = MagicMock()
        mock_tool4.name = "visualize_data"
        mock_agent.tool_registry.get_schemas = AsyncMock(return_value=[
            mock_tool1, mock_tool2, mock_tool3, mock_tool4
        ])

        result = await default_workflow._generate_status_check(mock_agent, mock_user)

        assert result.should_skip_llm is True
        assert result.components is not None
        assert len(result.components) > 0

    @pytest.mark.asyncio
    async def test_generate_status_check_functional(self, default_workflow, mock_user):
        """Test status check for functional (partial) setup."""
        mock_agent = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "run_sql"
        mock_agent.tool_registry.get_schemas = AsyncMock(return_value=[mock_tool])

        result = await default_workflow._generate_status_check(mock_agent, mock_user)

        assert result.should_skip_llm is True
        assert result.components is not None

    @pytest.mark.asyncio
    async def test_generate_status_check_no_setup(self, default_workflow, mock_user):
        """Test status check for no setup."""
        mock_agent = MagicMock()
        mock_agent.tool_registry.get_schemas = AsyncMock(return_value=[])

        result = await default_workflow._generate_status_check(mock_agent, mock_user)

        assert result.should_skip_llm is True
        assert result.components is not None


# ============================================================================
# Integration Tests
# ============================================================================

class TestDefaultWorkflowHandlerIntegration:
    """Integration tests for DefaultWorkflowHandler."""

    @pytest.mark.asyncio
    async def test_full_workflow_starter_ui_generation(self, default_workflow, mock_user, mock_conversation):
        """Test full workflow with starter UI generation."""
        mock_agent = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "run_sql"
        mock_tool2 = MagicMock()
        mock_tool2.name = "search_saved_correct_tool_uses"
        mock_tool3 = MagicMock()
        mock_tool3.name = "save_question_tool_args"
        mock_tool4 = MagicMock()
        mock_tool4.name = "visualize_data"
        mock_agent.tool_registry.get_schemas = AsyncMock(return_value=[
            mock_tool1, mock_tool2, mock_tool3, mock_tool4
        ])

        result = await default_workflow.get_starter_ui(
            agent=mock_agent,
            user=mock_user,
            conversation=mock_conversation,
        )

        assert result is not None
        assert len(result) > 0
        assert all(isinstance(c, UiComponent) for c in result)

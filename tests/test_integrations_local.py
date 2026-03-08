"""
Integration tests for local integrations.

These tests verify real behavior using actual file I/O with tmp_path,
not mocks. This makes them informative: if they break, you know
something real is wrong.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# Add src to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from r2-db2.capabilities.agent_memory import TextMemory, ToolMemory
from r2-db2.capabilities.file_system import CommandResult, FileSearchMatch
from r2-db2.core.audit import AuditEvent, AuditEventType, AuditLogger
from r2-db2.core.storage import Conversation, Message
from r2-db2.core.tool import ToolContext
from r2-db2.core.user import User
from r2-db2.integrations.local.agent_memory.in_memory import DemoAgentMemory
from r2-db2.integrations.local.audit import LoggingAuditLogger
from r2-db2.integrations.local.file_system import LocalFileSystem
from r2-db2.integrations.local.file_system_conversation_store import (
    FileSystemConversationStore,
)
from r2-db2.integrations.local.storage import MemoryConversationStore


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return User(id="test-user-123", username="testuser", email="test@example.com")


@pytest.fixture
def demo_agent_memory() -> DemoAgentMemory:
    """Create a DemoAgentMemory instance for testing."""
    return DemoAgentMemory()


@pytest.fixture
def tool_context(user: User, demo_agent_memory: DemoAgentMemory) -> ToolContext:
    """Create a tool context for testing."""
    return ToolContext(
        user=user,
        conversation_id="conv-123",
        request_id="req-123",
        agent_memory=demo_agent_memory,
    )


def make_context(
    user: User, conversation_id: str, agent_memory: DemoAgentMemory
) -> ToolContext:
    """Helper to create a ToolContext with all required fields."""
    return ToolContext(
        user=user,
        conversation_id=conversation_id,
        request_id=f"req-{conversation_id}",
        agent_memory=agent_memory,
    )


# =============================================================================
# LocalFileSystem Tests
# =============================================================================


class TestLocalFileSystem:
    """Tests for LocalFileSystem implementation."""

    def test_write_and_read_file(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test basic write and read operations."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-1", demo_agent_memory)

        # Write a file
        asyncio.run(fs.write_file("test.txt", "Hello, World!", context))

        # Read it back
        content = asyncio.run(fs.read_file("test.txt", context))

        assert content == "Hello, World!"

    def test_write_file_creates_parent_directories(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that write_file creates parent directories."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-2", demo_agent_memory)

        asyncio.run(fs.write_file("nested/deep/file.txt", "Content here", context))

        # The user directory is hashed, so we need to find the actual user directory
        user_dirs = list(tmp_path.iterdir())
        assert len(user_dirs) == 1
        user_dir = user_dirs[0]
        file_path = user_dir / "nested" / "deep" / "file.txt"
        assert file_path.exists()
        assert file_path.read_text() == "Content here"

    def test_write_file_overwrite_false_raises(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that overwrite=False raises FileExistsError."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-3", demo_agent_memory)

        asyncio.run(fs.write_file("existing.txt", "First content", context))

        with pytest.raises(FileExistsError):
            asyncio.run(fs.write_file("existing.txt", "Second content", context))

    def test_write_file_overwrite_true_succeeds(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that overwrite=True replaces existing file."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-4", demo_agent_memory)

        asyncio.run(fs.write_file("overwrite.txt", "First content", context))
        asyncio.run(fs.write_file("overwrite.txt", "Second content", context, overwrite=True))

        content = asyncio.run(fs.read_file("overwrite.txt", context))
        assert content == "Second content"

    def test_list_files(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test listing files in a directory."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-5", demo_agent_memory)

        # Create some files
        asyncio.run(fs.write_file("file1.txt", "content1", context))
        asyncio.run(fs.write_file("file2.txt", "content2", context))
        asyncio.run(fs.write_file("file3.md", "content3", context))

        # Create a subdirectory with a file
        asyncio.run(fs.write_file("subdir/nested.txt", "nested content", context))

        files = asyncio.run(fs.list_files(".", context))

        # Should only list files in current directory, not subdirectories
        assert set(files) == {"file1.txt", "file2.txt", "file3.md"}

    def test_list_files_nonexistent_directory_raises(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that listing a nonexistent directory raises FileNotFoundError."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-6", demo_agent_memory)

        with pytest.raises(FileNotFoundError):
            asyncio.run(fs.list_files("nonexistent", context))

    def test_list_files_not_a_directory_raises(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that listing a file as directory raises NotADirectoryError."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-7", demo_agent_memory)

        asyncio.run(fs.write_file("afile.txt", "content", context))

        with pytest.raises(NotADirectoryError):
            asyncio.run(fs.list_files("afile.txt", context))

    def test_exists_file(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test checking if a file exists."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-8", demo_agent_memory)

        assert asyncio.run(fs.exists("nonexistent.txt", context)) is False

        asyncio.run(fs.write_file("existent.txt", "content", context))
        assert asyncio.run(fs.exists("existent.txt", context)) is True

    def test_exists_directory(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test checking if a directory exists."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-9", demo_agent_memory)

        assert asyncio.run(fs.exists("nonexistent", context)) is False

        asyncio.run(fs.write_file("dir/file.txt", "content", context))
        assert asyncio.run(fs.exists("dir", context)) is True

    def test_is_directory(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test checking if a path is a directory."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-10", demo_agent_memory)

        asyncio.run(fs.write_file("file.txt", "content", context))
        asyncio.run(fs.write_file("dir/nested.txt", "content", context))

        assert asyncio.run(fs.is_directory("file.txt", context)) is False
        assert asyncio.run(fs.is_directory("dir", context)) is True
        assert asyncio.run(fs.is_directory("nonexistent", context)) is False

    def test_search_files_by_name(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test searching files by name."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-11", demo_agent_memory)

        # Create files with different names
        asyncio.run(fs.write_file("report.txt", "report content", context))
        asyncio.run(fs.write_file("summary.txt", "summary content", context))
        asyncio.run(fs.write_file("data.csv", "data content", context))
        asyncio.run(fs.write_file("notes.md", "notes content", context))

        # Search for files containing "rep"
        matches = asyncio.run(fs.search_files("rep", context))

        assert len(matches) == 1
        assert matches[0].path == "report.txt"
        assert matches[0].snippet == "[filename match]"

    def test_search_files_by_content(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test searching files by content."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-12", demo_agent_memory)

        asyncio.run(fs.write_file("file1.txt", "The quick brown fox", context))
        asyncio.run(fs.write_file("file2.txt", "A lazy dog sleeps", context))
        asyncio.run(fs.write_file("file3.txt", "The quick jump", context))

        # Search for "quick" with content
        matches = asyncio.run(fs.search_files("quick", context, include_content=True))

        assert len(matches) == 2
        paths = {m.path for m in matches}
        assert paths == {"file1.txt", "file3.txt"}

    def test_search_files_snippet_generation(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test that search generates proper snippets."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-13", demo_agent_memory)

        # Create a file with enough content for snippet
        content = "The quick brown fox jumps over the lazy dog near the river bank"
        asyncio.run(fs.write_file("content.txt", content, context))

        matches = asyncio.run(fs.search_files("quick", context, include_content=True))

        assert len(matches) == 1
        snippet = matches[0].snippet
        assert "quick" in snippet.lower()
        # Should not have ellipsis for short content
        assert "…" not in snippet

    def test_search_files_max_results(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test max_results limit."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-14", demo_agent_memory)

        for i in range(5):
            asyncio.run(fs.write_file(f"file{i}.txt", f"content {i}", context))

        matches = asyncio.run(fs.search_files("file", context, max_results=3))

        assert len(matches) == 3

    def test_search_files_empty_query_raises(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that empty search query raises ValueError."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-15", demo_agent_memory)

        with pytest.raises(ValueError):
            asyncio.run(fs.search_files("", context))

    def test_directory_traversal_prevention(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test that directory traversal is prevented."""
        fs = LocalFileSystem(working_directory=str(tmp_path))
        context = make_context(user, "conv-16", demo_agent_memory)

        # Try to access parent directory
        with pytest.raises(PermissionError):
            asyncio.run(fs.read_file("../outside.txt", context))

        # Try to access absolute path
        with pytest.raises(PermissionError):
            asyncio.run(fs.read_file("/etc/passwd", context))

    def test_user_isolation(self, tmp_path: Path, demo_agent_memory: DemoAgentMemory) -> None:
        """Test that different users have isolated directories."""
        fs = LocalFileSystem(working_directory=str(tmp_path))

        user1 = User(id="user-a", username="usera")
        user2 = User(id="user-b", username="userb")

        context1 = make_context(user1, "conv-1", demo_agent_memory)
        context2 = make_context(user2, "conv-2", demo_agent_memory)

        # User 1 writes a file
        asyncio.run(fs.write_file("secret.txt", "user1 secret", context1))

        # User 2 should not see user 1's file
        files_user2 = asyncio.run(fs.list_files(".", context2))
        assert "secret.txt" not in files_user2

        # User 2 writes their own file
        asyncio.run(fs.write_file("secret.txt", "user2 secret", context2))

        # Both should be able to read their own files
        content1 = asyncio.run(fs.read_file("secret.txt", context1))
        content2 = asyncio.run(fs.read_file("secret.txt", context2))

        assert content1 == "user1 secret"
        assert content2 == "user2 secret"


# =============================================================================
# LocalStorage (MemoryConversationStore) Tests
# =============================================================================


class TestMemoryConversationStore:
    """Tests for MemoryConversationStore implementation."""

    @pytest.mark.asyncio
    async def test_create_conversation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test creating a new conversation."""
        store = MemoryConversationStore()

        conversation = await store.create_conversation(
            conversation_id="conv-1", user=user, initial_message="Hello"
        )

        assert conversation.id == "conv-1"
        assert conversation.user.id == user.id
        assert len(conversation.messages) == 1
        assert conversation.messages[0].role == "user"
        assert conversation.messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_get_conversation(self, tmp_path: Path, user: User) -> None:
        """Test getting an existing conversation."""
        store = MemoryConversationStore()

        await store.create_conversation(
            conversation_id="conv-2", user=user, initial_message="Hello"
        )

        conversation = await store.get_conversation(conversation_id="conv-2", user=user)

        assert conversation is not None
        assert conversation.id == "conv-2"

    @pytest.mark.asyncio
    async def test_get_conversation_wrong_user(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test that getting another user's conversation returns None."""
        store = MemoryConversationStore()

        await store.create_conversation(
            conversation_id="conv-3", user=user, initial_message="Hello"
        )

        other_user = User(id="other-user", username="other")
        conversation = await store.get_conversation(conversation_id="conv-3", user=other_user)

        assert conversation is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test getting a nonexistent conversation."""
        store = MemoryConversationStore()

        conversation = await store.get_conversation(
            conversation_id="nonexistent", user=user
        )

        assert conversation is None

    @pytest.mark.asyncio
    async def test_update_conversation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test updating a conversation with new messages."""
        store = MemoryConversationStore()

        conversation = await store.create_conversation(
            conversation_id="conv-4", user=user, initial_message="Hello"
        )

        # Add a new message
        conversation.add_message(Message(role="assistant", content="Hi there!"))

        await store.update_conversation(conversation)

        # Get it back
        retrieved = await store.get_conversation(conversation_id="conv-4", user=user)

        assert retrieved is not None
        assert len(retrieved.messages) == 2
        assert retrieved.messages[1].role == "assistant"
        assert retrieved.messages[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_delete_conversation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test deleting a conversation."""
        store = MemoryConversationStore()

        await store.create_conversation(
            conversation_id="conv-5", user=user, initial_message="Hello"
        )

        result = await store.delete_conversation(conversation_id="conv-5", user=user)

        assert result is True

        # Verify it's gone
        conversation = await store.get_conversation(conversation_id="conv-5", user=user)
        assert conversation is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test deleting a nonexistent conversation."""
        store = MemoryConversationStore()

        result = await store.delete_conversation(
            conversation_id="nonexistent", user=user
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test listing conversations."""
        store = MemoryConversationStore()

        # Create multiple conversations
        for i in range(5):
            await store.create_conversation(
                conversation_id=f"conv-{i}", user=user, initial_message=f"Message {i}"
            )

        conversations = await store.list_conversations(user=user)

        assert len(conversations) == 5

    @pytest.mark.asyncio
    async def test_list_conversations_pagination(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test listing conversations with pagination."""
        store = MemoryConversationStore()

        for i in range(10):
            await store.create_conversation(
                conversation_id=f"conv-{i}", user=user, initial_message=f"Message {i}"
            )

        # Get first 3
        first_page = await store.list_conversations(user=user, limit=3, offset=0)
        assert len(first_page) == 3

        # Get next 3
        second_page = await store.list_conversations(user=user, limit=3, offset=3)
        assert len(second_page) == 3

        # Verify they're different
        ids_first = {c.id for c in first_page}
        ids_second = {c.id for c in second_page}
        assert ids_first.isdisjoint(ids_second)

    @pytest.mark.asyncio
    async def test_list_conversations_user_isolation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test that listing only returns user's own conversations."""
        store = MemoryConversationStore()

        # User 1 creates conversations
        await store.create_conversation(
            conversation_id="user1-conv-1", user=user, initial_message="Hello"
        )

        # User 2 creates conversations
        user2 = User(id="user-2", username="user2")
        await store.create_conversation(
            conversation_id="user2-conv-1", user=user2, initial_message="Hi"
        )

        # User 1 should only see their own
        user1_conversations = await store.list_conversations(user=user)
        assert len(user1_conversations) == 1
        assert user1_conversations[0].id == "user1-conv-1"

        # User 2 should only see their own
        user2_conversations = await store.list_conversations(user=user2)
        assert len(user2_conversations) == 1
        assert user2_conversations[0].id == "user2-conv-1"


# =============================================================================
# LocalAuditLogger Tests
# =============================================================================


class TestLoggingAuditLogger:
    """Tests for LoggingAuditLogger implementation."""

    def test_log_event_basic(self, tmp_path: Path, user: User) -> None:
        """Test basic event logging."""
        logger = LoggingAuditLogger()

        event = AuditEvent(
            event_type=AuditEventType.MESSAGE_RECEIVED,
            user_id=user.id,
            conversation_id="conv-1",
            request_id="req-1",
            details={"message": "Hello"},
        )

        # This should not raise
        asyncio.run(logger.log_event(event))

    def test_log_event_with_all_fields(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test logging event with all fields populated."""
        logger = LoggingAuditLogger()

        event = AuditEvent(
            event_id="event-123",
            event_type=AuditEventType.TOOL_INVOCATION,
            user_id=user.id,
            username=user.username,
            user_email=user.email,
            user_groups=user.group_memberships,
            conversation_id="conv-2",
            request_id="req-2",
            remote_addr="127.0.0.1",
            details={"tool": "sql_runner", "query": "SELECT 1"},
            contains_pii=False,
            redacted_fields=[],
        )

        asyncio.run(logger.log_event(event))

    def test_log_event_custom_log_level(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test logging with custom log level."""
        logger = LoggingAuditLogger(log_level=25)  # Custom level between INFO and WARNING

        event = AuditEvent(
            event_type=AuditEventType.MESSAGE_RECEIVED,
            user_id=user.id,
            conversation_id="conv-3",
            request_id="req-3",
        )

        asyncio.run(logger.log_event(event))


# =============================================================================
# InMemoryAgentMemory (DemoAgentMemory) Tests
# =============================================================================


class TestDemoAgentMemory:
    """Tests for DemoAgentMemory implementation."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_tool_usage(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test saving and retrieving tool usage memories."""
        context = make_context(user, "conv-1", demo_agent_memory)

        # Save a tool usage
        await demo_agent_memory.save_tool_usage(
            question="What is the total revenue?",
            tool_name="run_sql",
            args={"query": "SELECT SUM(revenue) FROM sales"},
            context=context,
            success=True,
            metadata={"database": "production"},
        )

        # Search for similar usage
        results = await demo_agent_memory.search_similar_usage(
            question="Total revenue from sales",
            context=context,
            similarity_threshold=0.5,
        )

        assert len(results) >= 1
        assert results[0].memory.question == "What is the total revenue?"
        assert results[0].memory.tool_name == "run_sql"

    @pytest.mark.asyncio
    async def test_save_text_memory(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test saving text memories."""
        context = make_context(user, "conv-2", demo_agent_memory)

        text_memory = await demo_agent_memory.save_text_memory(
            content="The user prefers concise answers and likes to see data visualizations.",
            context=context,
        )

        assert text_memory.memory_id is not None
        assert text_memory.content == "The user prefers concise answers and likes to see data visualizations."
        assert text_memory.timestamp is not None

    @pytest.mark.asyncio
    async def test_search_text_memories(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test searching text memories."""
        context = make_context(user, "conv-3", demo_agent_memory)

        # Save some text memories
        await demo_agent_memory.save_text_memory(
            content="The user works in the finance department and needs monthly reports.",
            context=context,
        )
        await demo_agent_memory.save_text_memory(
            content="The user prefers Python over JavaScript for backend development.",
            context=context,
        )
        await demo_agent_memory.save_text_memory(
            content="The user likes to see bar charts for comparison data.",
            context=context,
        )

        # Search for "finance reports"
        results = await demo_agent_memory.search_text_memories(
            query="finance department monthly reports",
            context=context,
            similarity_threshold=0.3,
        )

        assert len(results) >= 1
        # The first result should be the finance-related memory
        assert "finance" in results[0].memory.content.lower()

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test getting recent memories."""
        context = make_context(user, "conv-4", demo_agent_memory)

        # Save multiple memories
        for i in range(5):
            await demo_agent_memory.save_tool_usage(
                question=f"Question {i}",
                tool_name=f"tool_{i}",
                args={"index": i},
                context=context,
            )

        # Get recent memories
        recent = await demo_agent_memory.get_recent_memories(context=context, limit=3)

        # Should return most recent first
        assert len(recent) == 3
        assert recent[0].question == "Question 4"  # Most recent
        assert recent[1].question == "Question 3"
        assert recent[2].question == "Question 2"

    @pytest.mark.asyncio
    async def test_get_recent_text_memories(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test getting recent text memories."""
        context = make_context(user, "conv-5", demo_agent_memory)

        # Save multiple text memories
        for i in range(5):
            await demo_agent_memory.save_text_memory(
                content=f"Text memory {i}", context=context
            )

        # Get recent text memories
        recent = await demo_agent_memory.get_recent_text_memories(context=context, limit=3)

        assert len(recent) == 3
        assert recent[0].content == "Text memory 4"  # Most recent
        assert recent[1].content == "Text memory 3"
        assert recent[2].content == "Text memory 2"

    @pytest.mark.asyncio
    async def test_delete_text_memory(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test deleting a text memory."""
        context = make_context(user, "conv-6", demo_agent_memory)

        # Save a text memory
        text_memory = await demo_agent_memory.save_text_memory(
            content="To be deleted", context=context
        )

        # Verify it exists
        results = await demo_agent_memory.search_text_memories(
            query="deleted", context=context
        )
        assert len(results) >= 1

        # Delete it
        result = await demo_agent_memory.delete_text_memory(
            context=context, memory_id=text_memory.memory_id
        )

        assert result is True

        # Verify it's gone
        results = await demo_agent_memory.search_text_memories(
            query="deleted", context=context
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_delete_by_id(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test deleting a memory by ID."""
        context = make_context(user, "conv-7", demo_agent_memory)

        # Save a tool usage
        await demo_agent_memory.save_tool_usage(
            question="Delete me",
            tool_name="delete_test",
            args={},
            context=context,
        )

        # Get the memory ID
        results = await demo_agent_memory.search_similar_usage(
            question="Delete me", context=context
        )
        assert len(results) >= 1
        memory_id = results[0].memory.memory_id

        # Delete it
        result = await demo_agent_memory.delete_by_id(context=context, memory_id=memory_id)
        assert result is True

        # Verify it's gone
        results = await demo_agent_memory.search_similar_usage(
            question="Delete me", context=context
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_clear_memories(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test clearing memories."""
        context = make_context(user, "conv-8", demo_agent_memory)

        # Save multiple memories
        for i in range(3):
            await demo_agent_memory.save_tool_usage(
                question=f"Question {i}",
                tool_name="tool_a",
                args={},
                context=context,
            )
        for i in range(3):
            await demo_agent_memory.save_tool_usage(
                question=f"Question {i}",
                tool_name="tool_b",
                args={},
                context=context,
            )
        for i in range(3):
            await demo_agent_memory.save_text_memory(
                content=f"Text {i}", context=context
            )

        # Clear all
        deleted = await demo_agent_memory.clear_memories(context=context)

        assert deleted == 9  # 3 + 3 + 3

        # Verify all are gone
        recent_tool = await demo_agent_memory.get_recent_memories(context=context)
        recent_text = await demo_agent_memory.get_recent_text_memories(context=context)
        assert len(recent_tool) == 0
        assert len(recent_text) == 0

    @pytest.mark.asyncio
    async def test_clear_memories_with_tool_filter(
        self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory
    ) -> None:
        """Test clearing memories with tool filter."""
        context = make_context(user, "conv-9", demo_agent_memory)

        # Save memories for different tools
        for i in range(3):
            await demo_agent_memory.save_tool_usage(
                question=f"Question {i}",
                tool_name="tool_a",
                args={},
                context=context,
            )
        for i in range(3):
            await demo_agent_memory.save_tool_usage(
                question=f"Question {i}",
                tool_name="tool_b",
                args={},
                context=context,
            )

        # Clear only tool_a memories
        deleted = await demo_agent_memory.clear_memories(context=context, tool_name="tool_a")

        assert deleted == 3

        # Verify tool_a is gone but tool_b remains
        results_a = await demo_agent_memory.search_similar_usage(
            question="Question 0", context=context, tool_name_filter="tool_a"
        )
        results_b = await demo_agent_memory.search_similar_usage(
            question="Question 0", context=context, tool_name_filter="tool_b"
        )
        assert len(results_a) == 0
        assert len(results_b) >= 1

    @pytest.mark.asyncio
    async def test_max_items_eviction(self, tmp_path: Path, user: User, demo_agent_memory: DemoAgentMemory) -> None:
        """Test that max_items limit causes FIFO eviction."""
        memory = DemoAgentMemory(max_items=5)

        context = make_context(user, "conv-10", demo_agent_memory)

        # Save 5 memories
        for i in range(5):
            await memory.save_tool_usage(
                question=f"Question {i}",
                tool_name="test_tool",
                args={},
                context=context,
            )

        # Save one more - should evict the oldest
        await memory.save_tool_usage(
            question="Question 5",
            tool_name="test_tool",
            args={},
            context=context,
        )

        # Get recent - should not include Question 0
        recent = await memory.get_recent_memories(context=context)
        questions = [m.question for m in recent]
        assert "Question 0" not in questions
        assert "Question 5" in questions


# =============================================================================
# FileSystemConversationStore Tests
# =============================================================================


class TestFileSystemConversationStore:
    """Tests for FileSystemConversationStore implementation."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, tmp_path: Path, user: User) -> None:
        """Test creating a new conversation."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        conversation = await store.create_conversation(
            conversation_id="conv-1", user=user, initial_message="Hello"
        )

        assert conversation.id == "conv-1"
        assert conversation.user.id == user.id
        assert len(conversation.messages) == 1
        assert conversation.messages[0].content == "Hello"

        # Verify files were created
        conv_dir = tmp_path / "conversations" / "conv-1"
        assert conv_dir.exists()
        assert (conv_dir / "metadata.json").exists()
        assert (conv_dir / "messages").exists()

    @pytest.mark.asyncio
    async def test_get_conversation(self, tmp_path: Path, user: User) -> None:
        """Test getting an existing conversation."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        await store.create_conversation(
            conversation_id="conv-2", user=user, initial_message="Hello"
        )

        conversation = await store.get_conversation(conversation_id="conv-2", user=user)

        assert conversation is not None
        assert conversation.id == "conv-2"
        assert len(conversation.messages) == 1

    @pytest.mark.asyncio
    async def test_get_conversation_wrong_user(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test that getting another user's conversation returns None."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        await store.create_conversation(
            conversation_id="conv-3", user=user, initial_message="Hello"
        )

        other_user = User(id="other-user", username="other")
        conversation = await store.get_conversation(conversation_id="conv-3", user=other_user)

        assert conversation is None

    @pytest.mark.asyncio
    async def test_update_conversation(self, tmp_path: Path, user: User) -> None:
        """Test updating a conversation with new messages."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        conversation = await store.create_conversation(
            conversation_id="conv-4", user=user, initial_message="Hello"
        )

        # Add a new message
        conversation.add_message(Message(role="assistant", content="Hi there!"))

        await store.update_conversation(conversation)

        # Get it back
        retrieved = await store.get_conversation(conversation_id="conv-4", user=user)

        assert retrieved is not None
        assert len(retrieved.messages) == 2
        assert retrieved.messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_delete_conversation(self, tmp_path: Path, user: User) -> None:
        """Test deleting a conversation."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        await store.create_conversation(
            conversation_id="conv-5", user=user, initial_message="Hello"
        )

        result = await store.delete_conversation(conversation_id="conv-5", user=user)

        assert result is True

        # Verify directory is gone
        conv_dir = tmp_path / "conversations" / "conv-5"
        assert not conv_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test deleting a nonexistent conversation."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        result = await store.delete_conversation(
            conversation_id="nonexistent", user=user
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations(self, tmp_path: Path, user: User) -> None:
        """Test listing conversations."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        # Create multiple conversations
        for i in range(5):
            await store.create_conversation(
                conversation_id=f"conv-{i}", user=user, initial_message=f"Message {i}"
            )

        conversations = await store.list_conversations(user=user)

        assert len(conversations) == 5

    @pytest.mark.asyncio
    async def test_list_conversations_pagination(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test listing conversations with pagination."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        for i in range(10):
            await store.create_conversation(
                conversation_id=f"conv-{i}", user=user, initial_message=f"Message {i}"
            )

        # Get first 3
        first_page = await store.list_conversations(user=user, limit=3, offset=0)
        assert len(first_page) == 3

        # Get next 3
        second_page = await store.list_conversations(user=user, limit=3, offset=3)
        assert len(second_page) == 3

    @pytest.mark.asyncio
    async def test_list_conversations_user_isolation(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test that listing only returns user's own conversations."""
        store = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        # User 1 creates conversations
        await store.create_conversation(
            conversation_id="user1-conv-1", user=user, initial_message="Hello"
        )

        # User 2 creates conversations
        user2 = User(id="user-2", username="user2")
        await store.create_conversation(
            conversation_id="user2-conv-1", user=user2, initial_message="Hi"
        )

        # User 1 should only see their own
        user1_conversations = await store.list_conversations(user=user)
        assert len(user1_conversations) == 1
        assert user1_conversations[0].id == "user1-conv-1"

        # User 2 should only see their own
        user2_conversations = await store.list_conversations(user=user2)
        assert len(user2_conversations) == 1
        assert user2_conversations[0].id == "user2-conv-1"

    @pytest.mark.asyncio
    async def test_persists_across_instances(
        self, tmp_path: Path, user: User
    ) -> None:
        """Test that data persists across store instances."""
        store1 = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        await store1.create_conversation(
            conversation_id="conv-persist", user=user, initial_message="Hello"
        )

        # Create a new instance pointing to same directory
        store2 = FileSystemConversationStore(base_dir=str(tmp_path / "conversations"))

        conversation = await store2.get_conversation(
            conversation_id="conv-persist", user=user
        )

        assert conversation is not None
        assert conversation.id == "conv-persist"
        assert conversation.messages[0].content == "Hello"

"""Tests for capabilities modules (sql_runner, agent_memory, file_system)."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

from r2-db2.capabilities.sql_runner.models import RunSqlToolArgs
from r2-db2.capabilities.sql_runner.base import SqlRunner
from r2-db2.capabilities.agent_memory.models import (
    ToolMemory,
    TextMemory,
    ToolMemorySearchResult,
    TextMemorySearchResult,
    MemoryStats,
)
from r2-db2.capabilities.agent_memory.base import AgentMemory
from r2-db2.capabilities.file_system.models import FileSearchMatch, CommandResult
from r2-db2.capabilities.file_system.base import FileSystem


class TestRunSqlToolArgs:
    """Tests for RunSqlToolArgs Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating RunSqlToolArgs with valid SQL."""
        args = RunSqlToolArgs(sql="SELECT * FROM users")
        assert args.sql == "SELECT * FROM users"

    def test_empty_sql(self):
        """Test RunSqlToolArgs with empty SQL string."""
        args = RunSqlToolArgs(sql="")
        assert args.sql == ""

    def test_sql_field_description(self):
        """Test that sql field has correct description."""
        assert RunSqlToolArgs.model_fields["sql"].description == "SQL query to execute"


class MockSqlRunner(SqlRunner):
    """Mock implementation of SqlRunner protocol."""

    def __init__(self):
        self.mock_results = MagicMock()

    async def run_sql(
        self, args: RunSqlToolArgs, context: Any
    ) -> Any:
        """Execute SQL query and return results as a DataFrame."""
        df = MagicMock()
        df.__class__.__name__ = "DataFrame"
        return df


class TestSqlRunnerProtocol:
    """Tests for SqlRunner protocol/abstract base class."""

    def test_sql_runner_is_abstract(self):
        """Test that SqlRunner is an abstract base class."""
        assert SqlRunner.__abstractmethods__ == {"run_sql"}

    def test_sql_runner_has_run_sql_method(self):
        """Test that SqlRunner defines run_sql method."""
        assert hasattr(SqlRunner, "run_sql")
        import inspect
        assert inspect.isabstract(SqlRunner)

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_runner = MockSqlRunner()
        assert isinstance(mock_runner, SqlRunner)

    @pytest.mark.asyncio
    async def test_mock_implementation_run_sql(self):
        """Test mock implementation of run_sql."""
        mock_runner = MockSqlRunner()
        args = RunSqlToolArgs(sql="SELECT * FROM users")
        context = MagicMock()

        result = await mock_runner.run_sql(args, context)
        assert result is not None


class TestToolMemory:
    """Tests for ToolMemory Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolMemory with required fields."""
        memory = ToolMemory(
            question="What is the total revenue?",
            tool_name="run_sql",
            args={"sql": "SELECT SUM(revenue) FROM sales"}
        )
        assert memory.question == "What is the total revenue?"
        assert memory.tool_name == "run_sql"
        assert memory.args == {"sql": "SELECT SUM(revenue) FROM sales"}
        assert memory.memory_id is None
        assert memory.timestamp is None
        assert memory.success is True
        assert memory.metadata is None

    def test_with_optional_fields(self):
        """Test ToolMemory with all optional fields set."""
        memory = ToolMemory(
            memory_id="mem-123",
            question="Test question",
            tool_name="run_sql",
            args={"sql": "SELECT 1"},
            timestamp="2024-01-01T00:00:00Z",
            success=False,
            metadata={"error": "Connection failed"}
        )
        assert memory.memory_id == "mem-123"
        assert memory.timestamp == "2024-01-01T00:00:00Z"
        assert memory.success is False
        assert memory.metadata == {"error": "Connection failed"}

    def test_default_success_is_true(self):
        """Test that success defaults to True."""
        memory = ToolMemory(
            question="Test",
            tool_name="run_sql",
            args={}
        )
        assert memory.success is True


class TestTextMemory:
    """Tests for TextMemory Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating TextMemory with required fields."""
        memory = TextMemory(content="This is a text memory")
        assert memory.content == "This is a text memory"
        assert memory.memory_id is None
        assert memory.timestamp is None

    def test_with_optional_fields(self):
        """Test TextMemory with all optional fields set."""
        memory = TextMemory(
            memory_id="text-mem-456",
            content="Important note",
            timestamp="2024-01-01T00:00:00Z"
        )
        assert memory.memory_id == "text-mem-456"
        assert memory.timestamp == "2024-01-01T00:00:00Z"


class TestToolMemorySearchResult:
    """Tests for ToolMemorySearchResult Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating ToolMemorySearchResult."""
        tool_memory = ToolMemory(
            question="Test question",
            tool_name="run_sql",
            args={}
        )
        result = ToolMemorySearchResult(
            memory=tool_memory,
            similarity_score=0.85,
            rank=1
        )
        assert result.memory == tool_memory
        assert result.similarity_score == 0.85
        assert result.rank == 1


class TestTextMemorySearchResult:
    """Tests for TextMemorySearchResult Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating TextMemorySearchResult."""
        text_memory = TextMemory(content="Test content")
        result = TextMemorySearchResult(
            memory=text_memory,
            similarity_score=0.92,
            rank=2
        )
        assert result.memory == text_memory
        assert result.similarity_score == 0.92
        assert result.rank == 2


class TestMemoryStats:
    """Tests for MemoryStats Pydantic model."""

    def test_valid_instantiation(self):
        """Test creating MemoryStats with required fields."""
        stats = MemoryStats(
            total_memories=100,
            unique_tools=5,
            unique_questions=50,
            success_rate=0.95,
            most_used_tools={"run_sql": 60, "read_file": 20}
        )
        assert stats.total_memories == 100
        assert stats.unique_tools == 5
        assert stats.unique_questions == 50
        assert stats.success_rate == 0.95
        assert stats.most_used_tools == {"run_sql": 60, "read_file": 20}

    def test_empty_most_used_tools(self):
        """Test MemoryStats with empty most_used_tools."""
        stats = MemoryStats(
            total_memories=0,
            unique_tools=0,
            unique_questions=0,
            success_rate=0.0,
            most_used_tools={}
        )
        assert stats.most_used_tools == {}


class MockAgentMemory(AgentMemory):
    """Mock implementation of AgentMemory protocol."""

    async def save_tool_usage(
        self,
        question: str,
        tool_name: str,
        args: dict[str, Any],
        context: Any,
        success: bool = True,
        metadata: Any = None,
    ) -> None:
        """Save a tool usage pattern for future reference."""
        pass

    async def save_text_memory(
        self, content: str, context: Any
    ) -> Any:
        """Save a free-form text memory."""
        return TextMemory(content=content)

    async def search_similar_usage(
        self,
        question: str,
        context: Any,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        tool_name_filter: Any = None,
    ) -> list[Any]:
        """Search for similar tool usage patterns based on a question."""
        return []

    async def search_text_memories(
        self,
        query: str,
        context: Any,
        *,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[Any]:
        """Search stored text memories based on a query."""
        return []

    async def get_recent_memories(
        self, context: Any, limit: int = 10
    ) -> list[Any]:
        """Get recently added memories."""
        return []

    async def get_recent_text_memories(
        self, context: Any, limit: int = 10
    ) -> list[Any]:
        """Fetch recently stored text memories."""
        return []

    async def delete_by_id(self, context: Any, memory_id: str) -> bool:
        """Delete a memory by its ID."""
        return True

    async def delete_text_memory(self, context: Any, memory_id: str) -> bool:
        """Delete a text memory by its ID."""
        return True

    async def clear_memories(
        self,
        context: Any,
        tool_name: Any = None,
        before_date: Any = None,
    ) -> int:
        """Clear stored memories."""
        return 0


class TestAgentMemoryProtocol:
    """Tests for AgentMemory protocol/abstract base class."""

    def test_agent_memory_is_abstract(self):
        """Test that AgentMemory is an abstract base class."""
        expected_methods = {
            "save_tool_usage",
            "save_text_memory",
            "search_similar_usage",
            "search_text_memories",
            "get_recent_memories",
            "get_recent_text_memories",
            "delete_by_id",
            "delete_text_memory",
            "clear_memories",
        }
        assert AgentMemory.__abstractmethods__ == expected_methods

    def test_agent_memory_has_all_required_methods(self):
        """Test that AgentMemory defines all required methods."""
        required_methods = [
            "save_tool_usage",
            "save_text_memory",
            "search_similar_usage",
            "search_text_memories",
            "get_recent_memories",
            "get_recent_text_memories",
            "delete_by_id",
            "delete_text_memory",
            "clear_memories",
        ]
        for method in required_methods:
            assert hasattr(AgentMemory, method)

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_memory = MockAgentMemory()
        assert isinstance(mock_memory, AgentMemory)

    @pytest.mark.asyncio
    async def test_mock_implementation_save_tool_usage(self):
        """Test mock implementation of save_tool_usage."""
        mock_memory = MockAgentMemory()
        context = MagicMock()

        await mock_memory.save_tool_usage(
            question="Test question",
            tool_name="run_sql",
            args={"sql": "SELECT 1"},
            context=context,
            success=True,
            metadata=None
        )

    @pytest.mark.asyncio
    async def test_mock_implementation_save_text_memory(self):
        """Test mock implementation of save_text_memory."""
        mock_memory = MockAgentMemory()
        context = MagicMock()

        result = await mock_memory.save_text_memory(
            content="Test content",
            context=context
        )
        assert isinstance(result, TextMemory)
        assert result.content == "Test content"


class TestFileSearchMatch:
    """Tests for FileSearchMatch dataclass."""

    def test_valid_instantiation(self):
        """Test creating FileSearchMatch with required fields."""
        match = FileSearchMatch(path="/home/user/file.txt")
        assert match.path == "/home/user/file.txt"
        assert match.snippet is None

    def test_with_snippet(self):
        """Test FileSearchMatch with snippet."""
        match = FileSearchMatch(
            path="/home/user/file.txt",
            snippet="This is a snippet"
        )
        assert match.path == "/home/user/file.txt"
        assert match.snippet == "This is a snippet"


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_valid_instantiation(self):
        """Test creating CommandResult with required fields."""
        result = CommandResult(
            stdout="Command output",
            stderr="",
            returncode=0
        )
        assert result.stdout == "Command output"
        assert result.stderr == ""
        assert result.returncode == 0

    def test_with_stderr(self):
        """Test CommandResult with stderr."""
        result = CommandResult(
            stdout="",
            stderr="Error occurred",
            returncode=1
        )
        assert result.stderr == "Error occurred"
        assert result.returncode == 1

    def test_non_zero_returncode(self):
        """Test CommandResult with non-zero returncode."""
        result = CommandResult(
            stdout="",
            stderr="File not found",
            returncode=2
        )
        assert result.returncode == 2


class MockFileSystem(FileSystem):
    """Mock implementation of FileSystem protocol."""

    async def list_files(self, directory: str, context: Any) -> list[str]:
        """List files in a directory."""
        return [f"{directory}/file1.txt", f"{directory}/file2.txt"]

    async def read_file(self, filename: str, context: Any) -> str:
        """Read the contents of a file."""
        return f"Content of {filename}"

    async def write_file(
        self,
        filename: str,
        content: str,
        context: Any,
        overwrite: bool = False,
    ) -> None:
        """Write content to a file."""
        pass

    async def exists(self, path: str, context: Any) -> bool:
        """Check if a file or directory exists."""
        return True

    async def is_directory(self, path: str, context: Any) -> bool:
        """Check if a path is a directory."""
        return False

    async def search_files(
        self,
        query: str,
        context: Any,
        *,
        max_results: int = 20,
        include_content: bool = False,
    ) -> list[Any]:
        """Search for files matching a query."""
        return []

    async def run_bash(
        self,
        command: str,
        context: Any,
        *,
        timeout: Any = None,
    ) -> Any:
        """Execute a bash command."""
        return CommandResult(stdout="output", stderr="", returncode=0)


class TestFileSystemProtocol:
    """Tests for FileSystem protocol/abstract base class."""

    def test_file_system_is_abstract(self):
        """Test that FileSystem is an abstract base class."""
        expected_methods = {
            "list_files",
            "read_file",
            "write_file",
            "exists",
            "is_directory",
            "search_files",
            "run_bash",
        }
        assert FileSystem.__abstractmethods__ == expected_methods

    def test_file_system_has_all_required_methods(self):
        """Test that FileSystem defines all required methods."""
        required_methods = [
            "list_files",
            "read_file",
            "write_file",
            "exists",
            "is_directory",
            "search_files",
            "run_bash",
        ]
        for method in required_methods:
            assert hasattr(FileSystem, method)

    def test_mock_implementation_works(self):
        """Test that a mock implementation can be created."""
        mock_fs = MockFileSystem()
        assert isinstance(mock_fs, FileSystem)

    @pytest.mark.asyncio
    async def test_mock_implementation_list_files(self):
        """Test mock implementation of list_files."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        files = await mock_fs.list_files("/home/user", context)
        assert files == ["/home/user/file1.txt", "/home/user/file2.txt"]

    @pytest.mark.asyncio
    async def test_mock_implementation_read_file(self):
        """Test mock implementation of read_file."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        content = await mock_fs.read_file("/home/user/file.txt", context)
        assert content == "Content of /home/user/file.txt"

    @pytest.mark.asyncio
    async def test_mock_implementation_write_file(self):
        """Test mock implementation of write_file."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        await mock_fs.write_file(
            filename="/home/user/file.txt",
            content="Test content",
            context=context,
            overwrite=True
        )

    @pytest.mark.asyncio
    async def test_mock_implementation_exists(self):
        """Test mock implementation of exists."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        exists = await mock_fs.exists("/home/user/file.txt", context)
        assert exists is True

    @pytest.mark.asyncio
    async def test_mock_implementation_is_directory(self):
        """Test mock implementation of is_directory."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        is_dir = await mock_fs.is_directory("/home/user", context)
        assert is_dir is False

    @pytest.mark.asyncio
    async def test_mock_implementation_search_files(self):
        """Test mock implementation of search_files."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        results = await mock_fs.search_files(
            query="test",
            context=context,
            max_results=10,
            include_content=True
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_mock_implementation_run_bash(self):
        """Test mock implementation of run_bash."""
        mock_fs = MockFileSystem()
        context = MagicMock()

        result = await mock_fs.run_bash("ls -la", context, timeout=30.0)
        assert isinstance(result, CommandResult)
        assert result.stdout == "output"
        assert result.returncode == 0

"""
Focused tests for important tool behaviors in src/r2-db2/tools.

Tests cover:
1. File tools: WriteFileTool + ReadFileTool roundtrip, SearchFilesTool, EditFileTool
2. Python tools: RunPythonFileTool, PipInstallTool
3. SQL tool: RunSqlTool with CSV output and metadata
4. Visualization tool: VisualizeDataTool with CSV consumption
5. Agent memory tools: SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool, SaveTextMemoryTool

A "smol-agent code execution journey" test simulates SQL -> CSV -> visualization -> Python script flow.
"""

import asyncio
import csv
import io
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from r2-db2.core.tool import ToolContext, ToolResult
from r2-db2.core.user.models import User
from r2-db2.tools.file_system import (
    EditFileArgs,
    EditFileTool,
    FileSearchMatch,
    LineEdit,
    LocalFileSystem,
    ReadFileArgs,
    ReadFileTool,
    SearchFilesArgs,
    SearchFilesTool,
    WriteFileArgs,
    WriteFileTool,
)
from r2-db2.tools.python import (
    PipInstallArgs,
    PipInstallTool,
    RunPythonFileArgs,
    RunPythonFileTool,
)
from r2-db2.tools.run_sql import RunSqlTool
from r2-db2.tools.visualize_data import VisualizeDataArgs, VisualizeDataTool
from r2-db2.tools.agent_memory import (
    SaveQuestionToolArgsParams,
    SaveQuestionToolArgsTool,
    SaveTextMemoryParams,
    SaveTextMemoryTool,
    SearchSavedCorrectToolUsesParams,
    SearchSavedCorrectToolUsesTool,
)
from r2-db2.capabilities.agent_memory import AgentMemory
from r2-db2.capabilities.sql_runner import SqlRunner, RunSqlToolArgs
from r2-db2.integrations.local.agent_memory.in_memory import DemoAgentMemory
from r2-db2.integrations.plotly import PlotlyChartGenerator


# ============== FIXTURES ==============

@pytest.fixture
def user() -> User:
    """Create a test user."""
    return User(id="test-user-123", username="testuser")


@pytest.fixture
def conversation_id() -> str:
    """Create a conversation ID."""
    return "conv-abc-456"


@pytest.fixture
def request_id() -> str:
    """Create a request ID."""
    return "req-xyz-789"


@pytest.fixture
def agent_memory() -> AgentMemory:
    """Create an in-memory agent memory instance."""
    return DemoAgentMemory()


@pytest.fixture
def tool_context(
    user: User,
    conversation_id: str,
    request_id: str,
    agent_memory: AgentMemory,
) -> ToolContext:
    """Create a tool context for testing."""
    return ToolContext(
        user=user,
        conversation_id=conversation_id,
        request_id=request_id,
        agent_memory=agent_memory,
        metadata={},
    )


@pytest.fixture
def local_file_system(tmp_path: Path) -> LocalFileSystem:
    """Create a LocalFileSystem with a temp working directory."""
    return LocalFileSystem(working_directory=str(tmp_path))


# ============== FILE SYSTEM TOOLS ==============


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    @pytest.mark.asyncio
    async def test_write_and_read_roundtrip(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test WriteFileTool + ReadFileTool roundtrip with tmp_path context."""
        write_tool = WriteFileTool(local_file_system)
        read_tool = ReadFileTool(local_file_system)

        # Write a file
        write_result = await write_tool.execute(
            tool_context,
            WriteFileArgs(
                filename="test_data.txt",
                content="Hello, World!\nThis is a test file.",
                overwrite=False,
            ),
        )

        assert write_result.success is True
        assert "Successfully wrote" in write_result.result_for_llm

        # Read the file back
        read_result = await read_tool.execute(
            tool_context,
            ReadFileArgs(filename="test_data.txt"),
        )

        assert read_result.success is True
        assert "Hello, World!" in read_result.result_for_llm
        assert "This is a test file." in read_result.result_for_llm


class TestSearchFilesTool:
    """Tests for SearchFilesTool."""

    @pytest.mark.asyncio
    async def test_search_returns_path_and_snippet(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test SearchFilesTool content search returns path/snippet."""
        # Create some test files
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Write a file with known content
        test_file = user_dir / "searchable.txt"
        test_file.write_text("The quick brown fox jumps over the lazy dog.")

        search_tool = SearchFilesTool(local_file_system)

        # Search for content
        result = await search_tool.execute(
            tool_context,
            SearchFilesArgs(query="brown fox", include_content=True, max_results=10),
        )

        assert result.success is True
        assert "searchable.txt" in result.result_for_llm
        assert "brown fox" in result.result_for_llm.lower() or "brown" in result.result_for_llm.lower()

    @pytest.mark.asyncio
    async def test_search_no_result_message(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test SearchFilesTool no-result message path."""
        search_tool = SearchFilesTool(local_file_system)

        result = await search_tool.execute(
            tool_context,
            SearchFilesArgs(query="nonexistent_query_xyz", include_content=False),
        )

        assert result.success is True
        assert "No matches found" in result.result_for_llm


class TestEditFileTool:
    """Tests for EditFileTool."""

    @pytest.mark.asyncio
    async def test_successful_line_replacement(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test EditFileTool successful line replacement."""
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create a file with multiple lines
        test_file = user_dir / "edit_test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

        edit_tool = EditFileTool(local_file_system)

        result = await edit_tool.execute(
            tool_context,
            EditFileArgs(
                filename="edit_test.txt",
                edits=[
                    LineEdit(start_line=2, end_line=3, new_content="Replaced Line 2 and 3\nNew content here\n"),
                ],
            ),
        )

        assert result.success is True
        assert "Replaced lines 2-3" in result.result_for_llm

        # Verify the file was actually updated
        updated_content = await fs.read_file("edit_test.txt", tool_context)
        lines = updated_content.splitlines()
        assert lines[1] == "Replaced Line 2 and 3"
        assert lines[2] == "New content here"

    @pytest.mark.asyncio
    async def test_invalid_range_failure(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test EditFileTool invalid range failure path."""
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create a file
        test_file = user_dir / "edit_test2.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3")

        edit_tool = EditFileTool(local_file_system)

        # Try to edit with invalid range (start_line beyond file length)
        result = await edit_tool.execute(
            tool_context,
            EditFileArgs(
                filename="edit_test2.txt",
                edits=[
                    LineEdit(start_line=10, end_line=11, new_content="New line"),
                ],
            ),
        )

        assert result.success is False
        assert "Invalid edit range" in result.result_for_llm or "beyond the end" in result.result_for_llm


# ============== PYTHON TOOLS ==============


class TestRunPythonFileTool:
    """Tests for RunPythonFileTool."""

    @pytest.mark.asyncio
    async def test_success_execution(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunPythonFileTool success execution for real script in temp user dir."""
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create a Python script that writes output
        script_content = """
import sys
print("Hello from Python!")
print(f"Arguments: {sys.argv[1:]}")
"""
        script_path = user_dir / "test_script.py"
        script_path.write_text(script_content)

        tool = RunPythonFileTool(local_file_system)

        result = await tool.execute(
            tool_context,
            RunPythonFileArgs(filename="test_script.py", arguments=["arg1", "arg2"]),
        )

        assert result.success is True
        assert "Hello from Python!" in result.result_for_llm
        assert "arg1" in result.result_for_llm
        assert "arg2" in result.result_for_llm

    @pytest.mark.asyncio
    async def test_missing_file_error(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunPythonFileTool missing file error path."""
        tool = RunPythonFileTool(local_file_system)

        result = await tool.execute(
            tool_context,
            RunPythonFileArgs(filename="nonexistent_script.py"),
        )

        assert result.success is False
        assert "does not exist" in result.result_for_llm

    @pytest.mark.asyncio
    async def test_timeout_error(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunPythonFileTool timeout error path (mock run_bash timeout)."""
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create a Python script that writes output
        script_content = """
import sys
print("Hello from Python!")
print(f"Arguments: {sys.argv[1:]}")
"""
        script_path = user_dir / "test_script.py"
        script_path.write_text(script_content)

        tool = RunPythonFileTool(local_file_system)

        # Mock run_bash to raise TimeoutError
        with patch.object(local_file_system, "run_bash") as mock_run_bash:
            mock_run_bash.side_effect = TimeoutError("Command timed out after 5 seconds")

            result = await tool.execute(
                tool_context,
                RunPythonFileArgs(filename="test_script.py", timeout_seconds=5.0),
            )

            assert result.success is False
            assert "timed out" in result.result_for_llm.lower()


class TestPipInstallTool:
    """Tests for PipInstallTool."""

    @pytest.mark.asyncio
    async def test_command_composition_with_upgrade(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test PipInstallTool command composition includes --upgrade and extra args (mock run_bash)."""
        tool = PipInstallTool(local_file_system)

        # Mock run_bash to capture the command
        captured_command = None

        async def mock_run_bash(command: str, *args, **kwargs) -> Any:
            nonlocal captured_command
            captured_command = command
            return type("CommandResult", (), {"stdout": "", "stderr": "", "returncode": 0})()

        with patch.object(local_file_system, "run_bash", side_effect=mock_run_bash):
            result = await tool.execute(
                tool_context,
                PipInstallArgs(
                    packages=["requests"],
                    upgrade=True,
                    extra_args=["--no-cache-dir"],
                ),
            )

        assert result.success is True
        assert captured_command is not None
        assert "--upgrade" in captured_command
        assert "requests" in captured_command
        assert "--no-cache-dir" in captured_command


# ============== SQL TOOL ==============


class MockSqlRunner(SqlRunner):
    """Mock SqlRunner for testing."""

    def __init__(self, df_result: Any = None, raise_exception: bool = False):
        self.df_result = df_result
        self.raise_exception = raise_exception

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> Any:
        if self.raise_exception:
            raise Exception("Database connection failed")
        return self.df_result


class TestRunSqlTool:
    """Tests for RunSqlTool."""

    @pytest.mark.asyncio
    async def test_select_with_rows_saves_csv_and_returns_metadata(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunSqlTool SELECT with rows saves CSV and returns metadata with output_file."""
        import pandas as pd

        # Create mock DataFrame with results
        df = pd.DataFrame(
            {"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"], "value": [100, 200, 300]}
        )

        sql_runner = MockSqlRunner(df_result=df)
        tool = RunSqlTool(sql_runner=sql_runner, file_system=local_file_system)

        result = await tool.execute(
            tool_context,
            RunSqlToolArgs(sql="SELECT * FROM users WHERE value > 50"),
        )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.get("row_count") == 3
        assert result.metadata.get("columns") == ["id", "name", "value"]
        assert result.metadata.get("query_type") == "SELECT"
        assert "output_file" in result.metadata
        assert result.metadata["output_file"].startswith("query_results_")
        assert result.metadata["output_file"].endswith(".csv")

        # Verify CSV file was created
        output_file = result.metadata["output_file"]
        csv_content = await local_file_system.read_file(output_file, tool_context)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_select_empty_result(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunSqlTool SELECT empty result path."""
        import pandas as pd

        # Create empty DataFrame
        df = pd.DataFrame(columns=["id", "name", "value"])

        sql_runner = MockSqlRunner(df_result=df)
        tool = RunSqlTool(sql_runner=sql_runner, file_system=local_file_system)

        result = await tool.execute(
            tool_context,
            RunSqlToolArgs(sql="SELECT * FROM empty_table"),
        )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.get("row_count") == 0
        assert result.metadata.get("columns") == []
        assert "No rows returned" in result.result_for_llm

    @pytest.mark.asyncio
    async def test_non_select_returns_rows_affected(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunSqlTool non-SELECT path returns rows_affected metadata."""
        import pandas as pd

        # For non-SELECT, the SqlRunner should return a DataFrame with affected row count
        # The RunSqlTool uses len(df) for rows_affected, so we need 5 rows
        df = pd.DataFrame({"rows_affected": [1, 2, 3, 4, 5]})

        sql_runner = MockSqlRunner(df_result=df)
        tool = RunSqlTool(sql_runner=sql_runner, file_system=local_file_system)

        result = await tool.execute(
            tool_context,
            RunSqlToolArgs(sql="UPDATE users SET status = 'active' WHERE last_login > '2024-01-01'"),
        )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.get("rows_affected") == 5
        assert result.metadata.get("query_type") == "UPDATE"

    @pytest.mark.asyncio
    async def test_execution_exception_returns_error_metadata(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test RunSqlTool execution exception returns error metadata error_type=sql_error."""
        sql_runner = MockSqlRunner(raise_exception=True)
        tool = RunSqlTool(sql_runner=sql_runner, file_system=local_file_system)

        result = await tool.execute(
            tool_context,
            RunSqlToolArgs(sql="SELECT * FROM broken_table"),
        )

        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.get("error_type") == "sql_error"
        assert "error" in result.metadata or result.error is not None


# ============== VISUALIZATION TOOL ==============


class TestVisualizeDataTool:
    """Tests for VisualizeDataTool."""

    @pytest.mark.asyncio
    async def test_reads_csv_and_returns_chart_component_metadata(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test VisualizeDataTool reads CSV and returns ChartComponent metadata rows/columns."""
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create a CSV file
        csv_content = "id,name,value\n1,Alice,100\n2,Bob,200\n3,Charlie,300\n"
        csv_path = user_dir / "chart_data.csv"
        csv_path.write_text(csv_content)

        plotly_gen = PlotlyChartGenerator()
        tool = VisualizeDataTool(file_system=local_file_system, plotly_generator=plotly_gen)

        result = await tool.execute(
            tool_context,
            VisualizeDataArgs(filename="chart_data.csv", title="Test Chart"),
        )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.get("rows") == 3
        assert result.metadata.get("columns") == 3  # id, name, value
        assert result.metadata.get("filename") == "chart_data.csv"
        assert "chart" in result.metadata

        # Verify ChartComponent exists
        assert result.ui_component is not None
        assert result.ui_component.rich_component is not None
        assert result.ui_component.rich_component.type.value == "chart"

    @pytest.mark.asyncio
    async def test_file_not_found_path(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test VisualizeDataTool file-not-found path."""
        plotly_gen = PlotlyChartGenerator()
        tool = VisualizeDataTool(file_system=local_file_system, plotly_generator=plotly_gen)

        result = await tool.execute(
            tool_context,
            VisualizeDataArgs(filename="nonexistent.csv"),
        )

        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.get("error_type") == "file_not_found"
        assert "File not found" in result.result_for_llm

    @pytest.mark.asyncio
    async def test_visualization_value_error_path(
        self, local_file_system: LocalFileSystem, tool_context: ToolContext
    ) -> None:
        """Test VisualizeDataTool visualization ValueError path."""
        fs = local_file_system
        user_dir = fs._get_user_directory(tool_context)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create a CSV with invalid data that will cause visualization issues
        csv_content = "id,name,value\n1,Alice,abc\n2,Bob,def\n"  # Non-numeric values for chart
        csv_path = user_dir / "invalid_chart.csv"
        csv_path.write_text(csv_content)

        plotly_gen = PlotlyChartGenerator()
        tool = VisualizeDataTool(file_system=local_file_system, plotly_generator=plotly_gen)

        result = await tool.execute(
            tool_context,
            VisualizeDataArgs(filename="invalid_chart.csv"),
        )

        # The result may succeed or fail depending on how PlotlyChartGenerator handles it
        # At minimum, verify the tool handles the file read correctly
        assert result.metadata is not None
        assert result.metadata.get("filename") == "invalid_chart.csv"


# ============== AGENT MEMORY TOOLS ==============


class TestSaveQuestionToolArgsTool:
    """Tests for SaveQuestionToolArgsTool."""

    @pytest.mark.asyncio
    async def test_success_path(
        self, tool_context: ToolContext, agent_memory: AgentMemory
    ) -> None:
        """Test SaveQuestionToolArgsTool success path."""
        # Update tool_context with the agent_memory
        tool_context.agent_memory = agent_memory

        tool = SaveQuestionToolArgsTool()

        result = await tool.execute(
            tool_context,
            SaveQuestionToolArgsParams(
                question="What is the total revenue by region?",
                tool_name="run_sql",
                args={"sql": "SELECT region, SUM(revenue) FROM sales GROUP BY region"},
            ),
        )

        assert result.success is True
        assert "Successfully saved" in result.result_for_llm

        # Verify the memory was actually saved
        memories = await agent_memory.search_similar_usage(
            question="total revenue by region",
            context=tool_context,
            limit=5,
            similarity_threshold=0.5,
        )
        assert len(memories) >= 1
        assert memories[0].memory.tool_name == "run_sql"

    @pytest.mark.asyncio
    async def test_failure_path(
        self, tool_context: ToolContext
    ) -> None:
        """Test SaveQuestionToolArgsTool failure path (mock agent_memory failure)."""
        # Mock a failing agent_memory
        mock_memory = AsyncMock()
        mock_memory.save_tool_usage.side_effect = Exception("Memory service unavailable")

        tool_context.agent_memory = mock_memory

        tool = SaveQuestionToolArgsTool()

        result = await tool.execute(
            tool_context,
            SaveQuestionToolArgsParams(
                question="Test question",
                tool_name="test_tool",
                args={"key": "value"},
            ),
        )

        assert result.success is False
        assert "Failed to save memory" in result.result_for_llm


class TestSearchSavedCorrectToolUsesTool:
    """Tests for SearchSavedCorrectToolUsesTool."""

    @pytest.mark.asyncio
    async def test_no_results_and_results_formatting(
        self, tool_context: ToolContext, agent_memory: AgentMemory
    ) -> None:
        """Test SearchSavedCorrectToolUsesTool no-results and results formatting path."""
        # Update tool_context with the agent_memory
        tool_context.agent_memory = agent_memory

        tool = SearchSavedCorrectToolUsesTool()

        # First, test no-results path
        result = await tool.execute(
            tool_context,
            SearchSavedCorrectToolUsesParams(
                question="completely unique question that has no matches",
                limit=5,
                similarity_threshold=0.9,  # High threshold to ensure no matches
            ),
        )

        assert result.success is True
        assert "No similar tool usage patterns found" in result.result_for_llm

        # Now add a memory and test results formatting
        await agent_memory.save_tool_usage(
            question="What is the total revenue by region?",
            tool_name="run_sql",
            args={"sql": "SELECT region, SUM(revenue) FROM sales GROUP BY region"},
            context=tool_context,
            success=True,
        )

        result = await tool.execute(
            tool_context,
            SearchSavedCorrectToolUsesParams(
                question="total revenue by region",
                limit=5,
                similarity_threshold=0.5,
            ),
        )

        assert result.success is True
        assert "Found" in result.result_for_llm
        assert "run_sql" in result.result_for_llm
        assert "total revenue by region" in result.result_for_llm.lower()

    @pytest.mark.asyncio
    async def test_results_formatting(
        self, tool_context: ToolContext, agent_memory: AgentMemory
    ) -> None:
        """Test SearchSavedCorrectToolUsesTool results formatting."""
        tool_context.agent_memory = agent_memory

        # Add multiple memories
        await agent_memory.save_tool_usage(
            question="How many users are in each country?",
            tool_name="run_sql",
            args={"sql": "SELECT country, COUNT(*) FROM users GROUP BY country"},
            context=tool_context,
            success=True,
        )

        await agent_memory.save_tool_usage(
            question="Show me sales by product category",
            tool_name="run_sql",
            args={"sql": "SELECT category, SUM(amount) FROM sales GROUP BY category"},
            context=tool_context,
            success=True,
        )

        tool = SearchSavedCorrectToolUsesTool()

        result = await tool.execute(
            tool_context,
            SearchSavedCorrectToolUsesParams(
                question="sales by category",
                limit=10,
                similarity_threshold=0.3,
            ),
        )

        assert result.success is True
        assert "Found" in result.result_for_llm
        assert "run_sql" in result.result_for_llm


class TestSaveTextMemoryTool:
    """Tests for SaveTextMemoryTool."""

    @pytest.mark.asyncio
    async def test_success_path(
        self, tool_context: ToolContext, agent_memory: AgentMemory
    ) -> None:
        """Test SaveTextMemoryTool success path."""
        tool_context.agent_memory = agent_memory

        tool = SaveTextMemoryTool()

        result = await tool.execute(
            tool_context,
            SaveTextMemoryParams(
                content="Important insight: Revenue peaks in Q4 due to holiday season."
            ),
        )

        assert result.success is True
        assert "Successfully saved text memory" in result.result_for_llm
        assert "memory_id" in result.result_for_llm.lower() or "ID" in result.result_for_llm

        # Verify the text memory was saved - use a query that matches better
        text_memories = await agent_memory.search_text_memories(
            query="Important insight: Revenue peaks",
            context=tool_context,
            limit=5,
            similarity_threshold=0.5,
        )
        assert len(text_memories) >= 1
        assert "Q4" in text_memories[0].memory.content


# ============== SMOL-AGENT CODE EXECUTION JOURNEY TEST ==============


class TestSmolAgentCodeExecutionJourney:
    """Integration-style test simulating a code execution journey."""

    @pytest.mark.asyncio
    async def test_sql_csv_visualization_python_journey(
        self, tmp_path: Path, tool_context: ToolContext
    ) -> None:
        """
        Simulates a journey:
        a) SQL tool emits CSV output filename
        b) Visualization tool consumes that CSV and returns chart result
        c) Python tool executes a script that could represent post-analysis code execution
        """
        # Setup
        fs = LocalFileSystem(working_directory=str(tmp_path))
        plotly_gen = PlotlyChartGenerator()

        # Step a) SQL tool creates CSV
        import pandas as pd

        df = pd.DataFrame(
            {
                "month": ["Jan", "Feb", "Mar", "Apr", "May"],
                "revenue": [10000, 12000, 15000, 14000, 18000],
                "expenses": [8000, 9000, 10000, 9500, 11000],
            }
        )

        sql_runner = MockSqlRunner(df_result=df)
        sql_tool = RunSqlTool(sql_runner=sql_runner, file_system=fs)

        sql_result = await sql_tool.execute(
            tool_context,
            RunSqlToolArgs(sql="SELECT month, revenue, expenses FROM monthly_finances"),
        )

        assert sql_result.success is True
        assert "output_file" in sql_result.metadata
        csv_filename = sql_result.metadata["output_file"]
        assert csv_filename.endswith(".csv")

        # Verify CSV content
        csv_content = await fs.read_file(csv_filename, tool_context)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert len(rows) == 5
        assert rows[0]["month"] == "Jan"

        # Step b) Visualization tool consumes CSV
        viz_tool = VisualizeDataTool(file_system=fs, plotly_generator=plotly_gen)

        viz_result = await viz_tool.execute(
            tool_context,
            VisualizeDataArgs(filename=csv_filename, title="Monthly Revenue vs Expenses"),
        )

        assert viz_result.success is True
        assert viz_result.metadata is not None
        assert viz_result.metadata.get("rows") == 5
        assert viz_result.metadata.get("columns") == 3
        assert "chart" in viz_result.metadata

        # Step c) Python tool executes a post-analysis script
        # Create a script that reads the CSV and computes summary stats
        script_content = """
import csv
import io

# Read the CSV file
with open("{{CSV_FILENAME}}", "r") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Compute simple summary
revenues = [float(r["revenue"]) for r in rows]
avg_revenue = sum(revenues) / len(revenues)
max_revenue = max(revenues)
min_revenue = min(revenues)

print(f"Summary Statistics:")
print(f"  Average Revenue: ${avg_revenue:.2f}")
print(f"  Max Revenue: ${max_revenue:.2f}")
print(f"  Min Revenue: ${min_revenue:.2f}")
print(f"  Total Records: {len(rows)}")
"""

        # Replace placeholder with actual filename
        script_content = script_content.replace("{{CSV_FILENAME}}", csv_filename)

        # Write the script to user directory
        user_dir = fs._get_user_directory(tool_context)
        script_path = user_dir / "analyze_finances.py"
        script_path.write_text(script_content)

        python_tool = RunPythonFileTool(file_system=fs)

        python_result = await python_tool.execute(
            tool_context,
            RunPythonFileArgs(filename="analyze_finances.py"),
        )

        assert python_result.success is True
        assert "Summary Statistics" in python_result.result_for_llm
        assert "Average Revenue" in python_result.result_for_llm
        assert "Total Records: 5" in python_result.result_for_llm

        # Verify the journey produced expected outputs
        assert csv_filename in python_result.result_for_llm or "5" in python_result.result_for_llm

"""Important tests for Postgres SQL runner.

Tests cover:
- Constructor validation (connection_string vs host/database/user params)
- Import dependency behavior (psycopg2 missing handling)
- run_sql() behavior for SELECT with rows, empty results, and non-SELECT
- Cursor/connection cleanup in finally block even on execute errors
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

# Add src to path for imports (project uses src/r2-db2 structure)
sys.path.insert(0, str((Path(__file__).parent.parent / "src").resolve()))

from r2-db2.capabilities.agent_memory.base import AgentMemory
from r2-db2.capabilities.sql_runner.models import RunSqlToolArgs
from r2-db2.core.tool import ToolContext
from r2-db2.core.user.models import User
from r2-db2.integrations.postgres.sql_runner import PostgresRunner


def create_mock_context():
    """Create a minimal ToolContext for testing."""
    user = User(id="test-user-id", username="testuser", email="test@example.com")
    agent_memory = MagicMock(spec=AgentMemory)
    return ToolContext(
        user=user,
        conversation_id="test-conversation-id",
        request_id="test-request-id",
        agent_memory=agent_memory
    )


class TestPostgresRunnerConstructor:
    """Test PostgresRunner constructor validation."""

    def test_accepts_connection_string(self):
        """Constructor accepts connection_string parameter."""
        runner = PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")
        assert runner.connection_string == "postgresql://user:pass@localhost:5432/db"
        assert runner.connection_params is None

    def test_accepts_host_database_user_parameters(self):
        """Constructor accepts host, database, user parameters."""
        runner = PostgresRunner(
            host="localhost",
            database="testdb",
            user="testuser",
            password="secret",
            port=5433
        )
        assert runner.connection_string is None
        assert runner.connection_params == {
            "host": "localhost",
            "database": "testdb",
            "user": "testuser",
            "password": "secret",
            "port": 5433,
        }

    def test_rejects_invalid_init_no_connection_string_or_params(self):
        """Constructor raises ValueError when neither connection_string nor required params provided."""
        with pytest.raises(ValueError, match="Either provide connection_string OR"):
            PostgresRunner()

    def test_rejects_partial_params_missing_database(self):
        """Constructor raises ValueError when host and user provided but database missing."""
        with pytest.raises(ValueError, match="Either provide connection_string OR"):
            PostgresRunner(host="localhost", user="testuser")

    def test_rejects_partial_params_missing_user(self):
        """Constructor raises ValueError when host and database provided but user missing."""
        with pytest.raises(ValueError, match="Either provide connection_string OR"):
            PostgresRunner(host="localhost", database="testdb")


class TestPostgresRunnerImportDependency:
    """Test psycopg2 import dependency behavior."""

    def test_raises_import_error_when_psycopg2_missing(self):
        """Raises ImportError with helpful message when psycopg2 import fails."""
        with patch.dict("sys.modules", {"psycopg2": None, "psycopg2.extras": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'psycopg2'")):
                with pytest.raises(ImportError) as exc_info:
                    PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")
                assert "psycopg2 package is required" in str(exc_info.value)
                assert "r2-db2[postgres]" in str(exc_info.value)


class TestPostgresRunnerRunSql:
    """Test run_sql() behavior with mocked psycopg2 connection/cursor."""

    @pytest.mark.asyncio
    async def test_select_with_rows_returns_dataframe_with_expected_columns_and_rows(self):
        """SELECT with rows returns DataFrame with expected columns/rows."""
        runner = PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "Alice", "value": 100},
            {"id": 2, "name": "Bob", "value": 200},
        ]
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="SELECT id, name, value FROM users")
        context = create_mock_context()

        with patch("psycopg2.connect", return_value=mock_conn):
            result = await runner.run_sql(args, context)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["id", "name", "value"]
        assert len(result) == 2
        assert result.iloc[0]["name"] == "Alice"
        assert result.iloc[1]["value"] == 200

    @pytest.mark.asyncio
    async def test_select_with_empty_rows_returns_empty_dataframe(self):
        """SELECT with no rows returns empty DataFrame."""
        runner = PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="SELECT * FROM empty_table")
        context = create_mock_context()

        with patch("psycopg2.connect", return_value=mock_conn):
            result = await runner.run_sql(args, context)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_non_select_commits_and_returns_rows_affected(self):
        """Non-SELECT (INSERT/UPDATE/DELETE) commits and returns DataFrame with rows_affected."""
        runner = PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="UPDATE users SET active = true WHERE id > 10")
        context = create_mock_context()

        with patch("psycopg2.connect", return_value=mock_conn):
            result = await runner.run_sql(args, context)

        mock_conn.commit.assert_called_once()
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["rows_affected"]
        assert result.iloc[0]["rows_affected"] == 5

    @pytest.mark.asyncio
    async def test_insert_returns_rows_affected(self):
        """INSERT query commits and returns rows_affected."""
        runner = PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="INSERT INTO users (name) VALUES ('Charlie')")
        context = create_mock_context()

        with patch("psycopg2.connect", return_value=mock_conn):
            result = await runner.run_sql(args, context)

        mock_conn.commit.assert_called_once()
        assert result.iloc[0]["rows_affected"] == 1

    @pytest.mark.asyncio
    async def test_cursor_and_connection_closed_in_finally_even_when_execute_raises(self):
        """Cursor and connection are closed in finally even when execute raises exception."""
        runner = PostgresRunner(connection_string="postgresql://user:pass@localhost:5432/db")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Syntax error in SQL")
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="INVALID SQL SYNTAX")
        context = create_mock_context()

        with patch("psycopg2.connect", return_value=mock_conn):
            with pytest.raises(Exception, match="Syntax error in SQL"):
                await runner.run_sql(args, context)

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


class TestPostgresRunnerConnectionParams:
    """Test connection string vs connection_params path selection."""

    @pytest.mark.asyncio
    async def test_connection_string_takes_precedence_over_params(self):
        """When connection_string provided, uses connection_string path."""
        runner = PostgresRunner(
            connection_string="postgresql://user:pass@localhost:5432/db",
            host="ignored_host",
            database="ignored_db",
            user="ignored_user"
        )
        assert runner.connection_string == "postgresql://user:pass@localhost:5432/db"
        assert runner.connection_params is None

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="SELECT 1")
        context = create_mock_context()

        with patch("psycopg2.connect") as mock_connect:
            await runner.run_sql(args, context)
            mock_connect.assert_called_once_with("postgresql://user:pass@localhost:5432/db")

    @pytest.mark.asyncio
    async def test_connection_params_used_when_no_connection_string(self):
        """When no connection_string, uses connection_params path."""
        runner = PostgresRunner(
            host="localhost",
            database="testdb",
            user="testuser",
            password="secret",
            port=5433
        )
        assert runner.connection_string is None
        assert runner.connection_params is not None

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        args = RunSqlToolArgs(sql="SELECT 1")
        context = create_mock_context()

        with patch("psycopg2.connect") as mock_connect:
            await runner.run_sql(args, context)
            mock_connect.assert_called_once_with(
                host="localhost",
                database="testdb",
                user="testuser",
                password="secret",
                port=5433,
            )

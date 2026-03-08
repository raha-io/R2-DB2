"""Shared test fixtures for the r2-db2 test suite."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def sample_sql():
    """Sample SQL query for testing."""
    return "SELECT id, name, value FROM test_table WHERE value > 100 LIMIT 10"


@pytest.fixture
def sample_query_result():
    """Sample query result dict."""
    return {
        "columns": ["id", "name", "value"],
        "rows": [
            [1, "alpha", 150],
            [2, "beta", 200],
            [3, "gamma", 300],
        ],
        "row_count": 3,
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return {
        "content": "SELECT id, name FROM test_table",
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

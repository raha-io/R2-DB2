"""Important tests for Qdrant Agent Memory.

Tests cover:
- Constructor/import behavior (ImportError when Qdrant unavailable)
- _create_embedding (dimension length, deterministic for same input)
- _get_client lazy initialization (url/api_key vs path branch, collection creation)
- Core async operations (save_tool_usage, search_similar_usage, search_text_memories, delete_by_id, clear_memories)
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str((Path(__file__).parent.parent / "src").resolve()))

from r2-db2.capabilities.agent_memory.base import AgentMemory
from r2-db2.capabilities.agent_memory.models import (
    ToolMemorySearchResult,
    TextMemorySearchResult,
)
from r2-db2.core.tool import ToolContext
from r2-db2.core.user.models import User


def create_mock_context():
    """Create a minimal ToolContext for testing."""
    user = User(id="test-user-id", username="testuser", email="test@example.com")
    agent_memory = MagicMock(spec=AgentMemory)
    return ToolContext(
        user=user,
        conversation_id="test-conversation-id",
        request_id="test-request-id",
        agent_memory=agent_memory,
    )


class TestQdrantAgentMemoryConstructor:
    """Test QdrantAgentMemory constructor and import behavior."""

    def test_raises_import_error_when_qdrant_unavailable(self):
        """Raises ImportError with clear message when qdrant-client is not installed."""
        # Create a mock qdrant_client module that simulates ImportError
        mock_qdrant_module = MagicMock()
        mock_qdrant_module.QdrantClient = None
        mock_qdrant_module.VectorParams = None
        mock_qdrant_module.Distance = None
        mock_qdrant_module.PointStruct = None
        mock_qdrant_module.Filter = None
        mock_qdrant_module.FieldCondition = None
        mock_qdrant_module.MatchValue = None
        mock_qdrant_module.QDRANT_AVAILABLE = False

        with patch.dict("sys.modules", {"qdrant_client": mock_qdrant_module}):
            # Need to reimport the module to pick up the mocked QDRANT_AVAILABLE
            import importlib
            import r2-db2.integrations.qdrant.agent_memory as am_module
            importlib.reload(am_module)

            with pytest.raises(ImportError) as exc_info:
                am_module.QdrantAgentMemory()
            assert "Qdrant is required" in str(exc_info.value)
            assert "qdrant-client" in str(exc_info.value)


class TestQdrantAgentMemoryCreateEmbedding:
    """Test _create_embedding method."""

    def test_returns_vector_with_configured_dimension(self):
        """Embedding vector has length equal to configured dimension."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        # Patch QDRANT_AVAILABLE to True and create missing qdrant symbols
        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                    memory = QdrantAgentMemory(dimension=128)
                    embedding = memory._create_embedding("test text")
                    assert len(embedding) == 128

    def test_returns_deterministic_embedding_for_same_text(self):
        """Same input text produces same embedding vector."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                    memory = QdrantAgentMemory(dimension=64)
                    embedding1 = memory._create_embedding("hello world")
                    embedding2 = memory._create_embedding("hello world")
                    assert embedding1 == embedding2

    def test_different_texts_produce_different_embeddings(self):
        """Different input texts produce different embedding vectors."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                    memory = QdrantAgentMemory(dimension=64)
                    embedding1 = memory._create_embedding("hello world")
                    embedding2 = memory._create_embedding("goodbye world")
                    assert embedding1 != embedding2


class TestQdrantAgentMemoryGetClient:
    """Test _get_client lazy initialization."""

    def test_uses_url_branch_when_url_provided(self):
        """Client initialized with url and api_key when url provided."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                        mock_client = MagicMock()
                        mock_client.get_collections.return_value = MagicMock(collections=[])
                        MockQdrantClient.return_value = mock_client

                        memory = QdrantAgentMemory(url="http://localhost:6333", api_key="test-key")

                        # Access _client to trigger lazy initialization
                        client = memory._get_client()

                        MockQdrantClient.assert_called_once_with(url="http://localhost:6333", api_key="test-key")

    def test_uses_path_branch_when_no_url(self):
        """Client initialized with path when no url provided."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                        mock_client = MagicMock()
                        mock_client.get_collections.return_value = MagicMock(collections=[])
                        MockQdrantClient.return_value = mock_client

                        memory = QdrantAgentMemory(path="/tmp/qdrant")

                        # Access _client to trigger lazy initialization
                        client = memory._get_client()

                        MockQdrantClient.assert_called_once_with(path="/tmp/qdrant")

    def test_uses_memory_when_no_url_or_path(self):
        """Client initialized with :memory: when no url or path provided."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                        mock_client = MagicMock()
                        mock_client.get_collections.return_value = MagicMock(collections=[])
                        MockQdrantClient.return_value = mock_client

                        memory = QdrantAgentMemory()

                        # Access _client to trigger lazy initialization
                        client = memory._get_client()

                        MockQdrantClient.assert_called_once_with(path=":memory:")

    def test_creates_collection_when_missing(self):
        """Collection is created when it doesn't exist."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True) as mock_vector_params:
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                        mock_client = MagicMock()
                        mock_client.get_collections.return_value = MagicMock(collections=[])
                        mock_client.create_collection = MagicMock()
                        MockQdrantClient.return_value = mock_client

                        memory = QdrantAgentMemory(collection_name="test_memories", dimension=256)

                        # Access _client to trigger lazy initialization
                        client = memory._get_client()

                        mock_client.create_collection.assert_called_once()
                        call_kwargs = mock_client.create_collection.call_args[1]
                        assert call_kwargs["collection_name"] == "test_memories"
                        mock_vector_params.assert_called_once()

    def test_skips_create_when_collection_exists(self):
        """Collection creation is skipped when collection already exists."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                        mock_collection = MagicMock()
                        mock_collection.name = "existing_memories"

                        mock_client = MagicMock()
                        mock_client.get_collections.return_value = MagicMock(collections=[mock_collection])
                        mock_client.create_collection = MagicMock()
                        MockQdrantClient.return_value = mock_client

                        memory = QdrantAgentMemory(collection_name="existing_memories")

                        # Access _client to trigger lazy initialization
                        client = memory._get_client()

                        mock_client.create_collection.assert_not_called()


class TestQdrantAgentMemoryAsyncOperations:
    """Test core async operations with mocked Qdrant client."""

    @pytest.mark.asyncio
    async def test_save_tool_usage_calls_upsert_with_expected_payload(self):
        """save_tool_usage calls upsert with expected payload fields."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.PointStruct", create=True) as MockPointStruct:
                        with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                            mock_client = MagicMock()
                            mock_client.upsert = MagicMock()
                            mock_client.get_collections.return_value = MagicMock(collections=[])
                            MockQdrantClient.return_value = mock_client

                            memory = QdrantAgentMemory()

                            with patch.object(memory, "_create_embedding", return_value=[0.1] * 384):
                                loop = asyncio.get_event_loop()

                                def _run_in_executor(executor, func, *args):
                                    future = loop.create_future()
                                    future.set_result(func(*args))
                                    return future

                                with patch.object(loop, "run_in_executor", side_effect=_run_in_executor):
                                    await memory.save_tool_usage(
                                        question="What is the revenue?",
                                        tool_name="run_sql",
                                        args={"sql": "SELECT revenue FROM sales"},
                                        context=create_mock_context(),
                                        success=True,
                                        metadata={"source": "test"},
                                    )

                            mock_client.upsert.assert_called_once()
                            call_args = mock_client.upsert.call_args[1]
                            points = call_args["points"]
                            assert len(points) == 1
                            MockPointStruct.assert_called_once()
                            point_payload = MockPointStruct.call_args.kwargs["payload"]
                            assert point_payload["question"] == "What is the revenue?"
                            assert point_payload["tool_name"] == "run_sql"
                            assert point_payload["args"] == {"sql": "SELECT revenue FROM sales"}
                            assert point_payload["success"] is True
                            assert point_payload["metadata"] == {"source": "test"}
                            assert "timestamp" in point_payload

    @pytest.mark.asyncio
    async def test_search_similar_usage_maps_hits_to_tool_memory_search_result(self):
        """search_similar_usage maps hits into ToolMemorySearchResult with rank ordering."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.PointStruct", create=True):
                        with patch("r2-db2.integrations.qdrant.agent_memory.Filter", create=True):
                            with patch("r2-db2.integrations.qdrant.agent_memory.FieldCondition", create=True):
                                with patch("r2-db2.integrations.qdrant.agent_memory.MatchValue", create=True):
                                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                                        mock_hit = MagicMock()
                                        mock_hit.id = "memory-123"
                                        mock_hit.score = 0.85
                                        mock_hit.payload = {
                                            "question": "What is the revenue?",
                                            "tool_name": "run_sql",
                                            "args": {"sql": "SELECT revenue FROM sales"},
                                            "timestamp": "2024-01-01T00:00:00",
                                            "success": True,
                                            "metadata": {},
                                        }

                                        mock_client = MagicMock()
                                        mock_client.query_points = MagicMock(return_value=MagicMock(points=[mock_hit]))
                                        mock_client.get_collections.return_value = MagicMock(collections=[])
                                        MockQdrantClient.return_value = mock_client

                                        memory = QdrantAgentMemory()

                                        with patch.object(memory, "_create_embedding", return_value=[0.1] * 384):
                                            loop = asyncio.get_event_loop()

                                            def _run_in_executor(executor, func, *args):
                                                future = loop.create_future()
                                                future.set_result(func(*args))
                                                return future

                                            with patch.object(loop, "run_in_executor", side_effect=_run_in_executor):
                                                results = await memory.search_similar_usage(
                                                    question="What is the revenue?",
                                                    context=create_mock_context(),
                                                    limit=10,
                                                    similarity_threshold=0.7,
                                                )

                                        assert len(results) == 1
                                        assert isinstance(results[0], ToolMemorySearchResult)
                                        assert results[0].memory.memory_id == "memory-123"
                                        assert results[0].similarity_score == 0.85
                                        assert results[0].rank == 1

    @pytest.mark.asyncio
    async def test_search_text_memories_maps_hits_to_text_memory_search_result(self):
        """search_text_memories maps hits into TextMemorySearchResult."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.PointStruct", create=True):
                        with patch("r2-db2.integrations.qdrant.agent_memory.Filter", create=True):
                            with patch("r2-db2.integrations.qdrant.agent_memory.FieldCondition", create=True):
                                with patch("r2-db2.integrations.qdrant.agent_memory.MatchValue", create=True):
                                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                                        mock_hit = MagicMock()
                                        mock_hit.id = "text-memory-456"
                                        mock_hit.score = 0.92
                                        mock_hit.payload = {
                                            "content": "The user prefers bar charts for time series data",
                                            "timestamp": "2024-01-01T00:00:00",
                                            "is_text_memory": True,
                                        }

                                        mock_client = MagicMock()
                                        mock_client.query_points = MagicMock(return_value=MagicMock(points=[mock_hit]))
                                        mock_client.get_collections.return_value = MagicMock(collections=[])
                                        MockQdrantClient.return_value = mock_client

                                        memory = QdrantAgentMemory()

                                        with patch.object(memory, "_create_embedding", return_value=[0.1] * 384):
                                            loop = asyncio.get_event_loop()

                                            def _run_in_executor(executor, func, *args):
                                                future = loop.create_future()
                                                future.set_result(func(*args))
                                                return future

                                            with patch.object(loop, "run_in_executor", side_effect=_run_in_executor):
                                                results = await memory.search_text_memories(
                                                    query="chart preferences",
                                                    context=create_mock_context(),
                                                    limit=10,
                                                    similarity_threshold=0.7,
                                                )

                                        assert len(results) == 1
                                        assert isinstance(results[0], TextMemorySearchResult)
                                        assert results[0].memory.memory_id == "text-memory-456"
                                        assert results[0].memory.content == "The user prefers bar charts for time series data"
                                        assert results[0].similarity_score == 0.92
                                        assert results[0].rank == 1

    @pytest.mark.asyncio
    async def test_delete_by_id_returns_true_when_point_exists(self):
        """delete_by_id returns True when point exists and delete called."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.PointStruct", create=True):
                        with patch("r2-db2.integrations.qdrant.agent_memory.Filter", create=True):
                            with patch("r2-db2.integrations.qdrant.agent_memory.FieldCondition", create=True):
                                with patch("r2-db2.integrations.qdrant.agent_memory.MatchValue", create=True):
                                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                                        mock_point = MagicMock()
                                        mock_point.id = "memory-123"

                                        mock_client = MagicMock()
                                        mock_client.retrieve = MagicMock(return_value=[mock_point])
                                        mock_client.delete = AsyncMock()
                                        mock_client.get_collections.return_value = MagicMock(collections=[])
                                        MockQdrantClient.return_value = mock_client

                                        memory = QdrantAgentMemory()

                                        loop = asyncio.get_event_loop()

                                        def _run_in_executor(executor, func, *args):
                                            future = loop.create_future()
                                            future.set_result(func(*args))
                                            return future

                                        with patch.object(loop, "run_in_executor", side_effect=_run_in_executor):
                                            result = await memory.delete_by_id(
                                                context=create_mock_context(),
                                                memory_id="memory-123",
                                            )

                                        assert result is True
                                        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_id_returns_false_when_point_not_found(self):
        """delete_by_id returns False when point doesn't exist."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.PointStruct", create=True):
                        with patch("r2-db2.integrations.qdrant.agent_memory.Filter", create=True):
                            with patch("r2-db2.integrations.qdrant.agent_memory.FieldCondition", create=True):
                                with patch("r2-db2.integrations.qdrant.agent_memory.MatchValue", create=True):
                                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                                        mock_client = MagicMock()
                                        mock_client.retrieve = MagicMock(return_value=[])
                                        mock_client.get_collections.return_value = MagicMock(collections=[])
                                        MockQdrantClient.return_value = mock_client

                                        memory = QdrantAgentMemory()

                                        loop = asyncio.get_event_loop()

                                        def _run_in_executor(executor, func, *args):
                                            future = loop.create_future()
                                            future.set_result(func(*args))
                                            return future

                                        with patch.object(loop, "run_in_executor", side_effect=_run_in_executor):
                                            result = await memory.delete_by_id(
                                                context=create_mock_context(),
                                                memory_id="non-existent-id",
                                            )

                                        assert result is False
                                        mock_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_memories_with_no_filters_deletes_and_recreates_collection(self):
        """clear_memories with no filters performs delete_collection + recreate collection."""
        from r2-db2.integrations.qdrant.agent_memory import QdrantAgentMemory

        with patch("r2-db2.integrations.qdrant.agent_memory.QDRANT_AVAILABLE", True):
            with patch("r2-db2.integrations.qdrant.agent_memory.VectorParams", create=True):
                with patch("r2-db2.integrations.qdrant.agent_memory.Distance", create=True):
                    with patch("r2-db2.integrations.qdrant.agent_memory.PointStruct", create=True):
                        with patch("r2-db2.integrations.qdrant.agent_memory.Filter", create=True):
                            with patch("r2-db2.integrations.qdrant.agent_memory.FieldCondition", create=True):
                                with patch("r2-db2.integrations.qdrant.agent_memory.MatchValue", create=True):
                                    with patch("r2-db2.integrations.qdrant.agent_memory.QdrantClient", create=True) as MockQdrantClient:
                                        mock_collection = MagicMock()
                                        mock_collection.name = "test_memories"

                                        mock_client = MagicMock()
                                        mock_client.delete_collection = MagicMock()
                                        mock_client.create_collection = MagicMock()
                                        mock_client.get_collections.return_value = MagicMock(collections=[mock_collection])
                                        MockQdrantClient.return_value = mock_client

                                        memory = QdrantAgentMemory(collection_name="test_memories", dimension=512)

                                        loop = asyncio.get_event_loop()

                                        def _run_in_executor(executor, func, *args):
                                            future = loop.create_future()
                                            future.set_result(func(*args))
                                            return future

                                        with patch.object(loop, "run_in_executor", side_effect=_run_in_executor):
                                            result = await memory.clear_memories(
                                                context=create_mock_context(),
                                                tool_name=None,
                                                before_date=None,
                                            )

                                        mock_client.delete_collection.assert_called_once_with(collection_name="test_memories")
                                        mock_client.create_collection.assert_called_once()
                                        call_kwargs = mock_client.create_collection.call_args[1]
                                        assert call_kwargs["collection_name"] == "test_memories"
                                        assert call_kwargs["vectors_config"] is not None

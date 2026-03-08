"""Tests for FastAPI server routes (graph-native + OpenAI-compatible)."""

from __future__ import annotations

import sys
from pathlib import Path


# Add src to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class TestGraphRoutesImport:
    """Verify graph route modules are importable after legacy cleanup."""

    def test_graph_router_importable(self):
        from r2-db2.servers.fastapi.graph_routes import router

        assert router is not None

    def test_openai_routes_importable(self):
        from r2-db2.servers.fastapi.openai_routes import register_openai_routes

        assert register_openai_routes is not None

    def test_servers_package_exports(self):
        from r2-db2.servers import graph_router, register_openai_routes

        assert graph_router is not None
        assert register_openai_routes is not None

"""FastAPI server adapters for R2-DB2 analytical agent.

Runtime app is created via src/r2-db2/main.py.
Legacy R2-DB2FastAPIServer has been removed.
"""

from r2-db2.servers.fastapi.graph_routes import router as graph_router
from r2-db2.servers.fastapi.openai_routes import register_openai_routes

__all__ = ["graph_router", "register_openai_routes"]

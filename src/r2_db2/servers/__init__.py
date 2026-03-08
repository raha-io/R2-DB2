"""R2-DB2 server adapters.

Runtime server is built via src/r2-db2/main.py using graph routes and OpenAI-compatible routes.
"""

from r2-db2.servers.fastapi.graph_routes import router as graph_router
from r2-db2.servers.fastapi.openai_routes import register_openai_routes

__all__ = ["graph_router", "register_openai_routes"]

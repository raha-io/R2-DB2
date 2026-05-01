"""Server adapters.

Runtime server is built via src/main.py using graph routes and OpenAI-compatible routes.
"""

from .fastapi.graph_routes import router as graph_router
from .fastapi.openai_routes import register_openai_routes

__all__ = ["graph_router", "register_openai_routes"]

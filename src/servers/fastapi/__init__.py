"""FastAPI server adapters for analytical agent.

Runtime app is created via src/main.py.
"""

from .graph_routes import router as graph_router
from .openai_routes import register_openai_routes

__all__ = ["graph_router", "register_openai_routes"]

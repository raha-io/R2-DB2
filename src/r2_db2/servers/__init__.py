"""
Server implementations for the R2-DB2 Agents framework.

This module provides FastAPI server factories for serving
R2-DB2 agents over HTTP with SSE, WebSocket, and polling endpoints.
"""

from .base import ChatHandler, ChatRequest, ChatStreamChunk

__all__ = [
    "ChatHandler",
    "ChatRequest",
    "ChatStreamChunk",
]

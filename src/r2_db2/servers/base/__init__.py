"""
Base server components for the R2-DB2 Agents framework.

This module provides framework-agnostic components for handling chat
requests and responses.
"""

from .chat_handler import ChatHandler
from .models import ChatRequest, ChatStreamChunk, ChatResponse

__all__ = [
    "ChatHandler",
    "ChatRequest",
    "ChatStreamChunk",
    "ChatResponse",
]

"""Base server models.

Legacy ChatHandler has been removed. Only base models remain for backward compatibility.
"""

from r2-db2.servers.base.models import ChatRequest, ChatResponse, ChatStreamChunk

__all__ = ["ChatRequest", "ChatResponse", "ChatStreamChunk"]

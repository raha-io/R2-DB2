"""
Storage domain.

This module provides the core abstractions for conversation storage in the R2-DB2 Agents framework.
"""

from .base import ConversationStore
from .models import Conversation, Message

__all__ = [
    "ConversationStore",
    "Conversation",
    "Message",
]

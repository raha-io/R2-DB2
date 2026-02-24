"""
User domain.

This module provides the core abstractions for user management in the R2-DB2 Agents framework.
"""

from .base import UserService
from .models import User
from .resolver import UserResolver
from .request_context import RequestContext

__all__ = [
    "UserService",
    "User",
    "UserResolver",
    "RequestContext",
]

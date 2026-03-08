"""Core modules for the R2-DB2 analytical agent.

After legacy agent removal, this package contains:
- report/  — Report generation service (used by LangGraph nodes)
- errors.py — Custom exception classes
- _compat.py — Python version compatibility shims
"""

from .errors import (
    AgentError,
    ConversationNotFoundError,
    LlmServiceError,
    PermissionError,
    ToolExecutionError,
    ToolNotFoundError,
    ValidationError,
)
from .report import OutputFormat, ReportOutputService

__all__ = [
    "AgentError",
    "ConversationNotFoundError",
    "LlmServiceError",
    "PermissionError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ValidationError",
    "OutputFormat",
    "ReportOutputService",
]

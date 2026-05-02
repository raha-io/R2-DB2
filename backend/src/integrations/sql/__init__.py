"""SQL integration: dialect-agnostic adapter, registry, and schema catalog."""

from .base import ColumnInfo, QueryResult, SqlAdapter, TableInfo
from .dialect_notes import DIALECT_LABELS, DIALECT_NOTES
from .registry import get_adapter, reset_adapter

__all__ = [
    "ColumnInfo",
    "DIALECT_LABELS",
    "DIALECT_NOTES",
    "QueryResult",
    "SqlAdapter",
    "TableInfo",
    "get_adapter",
    "reset_adapter",
]

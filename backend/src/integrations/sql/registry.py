"""Adapter factory: dispatches on settings.database.type."""

from __future__ import annotations

from typing import Any

from settings import get_settings

from .base import SqlAdapter

_CACHED_ADAPTER: SqlAdapter | None = None


def _build(database: Any) -> SqlAdapter:
    dialect = database.type
    if dialect == "clickhouse":
        from .clickhouse_adapter import ClickHouseAdapter

        return ClickHouseAdapter(database)
    if dialect == "postgres":
        from .postgres_adapter import PostgresAdapter

        return PostgresAdapter(database)
    if dialect == "mysql":
        from .mysql_adapter import MysqlAdapter

        return MysqlAdapter(database)
    raise ValueError(f"Unsupported DATABASE__TYPE: {dialect!r}")


def get_adapter() -> SqlAdapter:
    """Return a process-wide singleton adapter for the configured database."""
    global _CACHED_ADAPTER
    if _CACHED_ADAPTER is None:
        _CACHED_ADAPTER = _build(get_settings().database)
    return _CACHED_ADAPTER


def reset_adapter() -> None:
    """Drop the cached adapter (used by tests and after settings reloads)."""
    global _CACHED_ADAPTER
    if _CACHED_ADAPTER is not None:
        try:
            _CACHED_ADAPTER.close()
        except Exception:
            pass
        _CACHED_ADAPTER = None

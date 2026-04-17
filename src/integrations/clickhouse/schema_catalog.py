"""Schema catalog for ClickHouse.

Introspects the configured database via ``system.columns`` and renders a
Markdown block for use as LLM context during SQL generation. The result is
cached at module level; call :func:`refresh_schema_context` to invalidate.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from settings import ClickHouseSettings, get_settings

logger = logging.getLogger(__name__)


class ColumnInfo(TypedDict):
    name: str
    type: str


class TableInfo(TypedDict):
    name: str
    columns: list[ColumnInfo]


_CACHED_CONTEXT: str | None = None


def _create_client(settings: ClickHouseSettings) -> Any:
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=settings.host,
        port=settings.port,
        username=settings.user,
        password=settings.password,
        database=settings.database,
        secure=settings.secure,
    )


def _introspect(settings: ClickHouseSettings) -> list[TableInfo]:
    client = _create_client(settings)
    try:
        result = client.query(
            "SELECT table, name, type "
            "FROM system.columns "
            "WHERE database = %(db)s "
            "ORDER BY table, position",
            parameters={"db": settings.database},
        )
    finally:
        client.close()

    tables: dict[str, list[ColumnInfo]] = {}
    for table, name, type_ in result.result_rows:
        tables.setdefault(table, []).append({"name": name, "type": type_})

    return [
        {"name": f"{settings.database}.{table}", "columns": cols}
        for table, cols in tables.items()
    ]


def _render(tables: list[TableInfo]) -> str:
    lines: list[str] = ["## Available Tables\n"]
    for table in tables:
        lines.append(f"### {table['name']}\n")
        lines.append("| Column | Type |")
        lines.append("|--------|------|")
        for col in table["columns"]:
            lines.append(f"| {col['name']} | {col['type']} |")
        lines.append("")
    return "\n".join(lines)


def get_schema_context() -> str:
    """Return Markdown-formatted schema context, introspecting on first call."""
    global _CACHED_CONTEXT
    if _CACHED_CONTEXT is not None:
        return _CACHED_CONTEXT

    settings = get_settings().clickhouse
    try:
        tables = _introspect(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ClickHouse schema introspection failed for database=%s: %s",
            settings.database,
            exc,
        )
        return (
            f"## Available Tables\n\n"
            f"_Schema introspection failed for database `{settings.database}`. "
            f"Check ClickHouse connectivity._"
        )

    _CACHED_CONTEXT = _render(tables)
    logger.info(
        "Loaded schema context for database=%s (%d tables)",
        settings.database,
        len(tables),
    )
    return _CACHED_CONTEXT


def refresh_schema_context() -> str:
    """Invalidate the cache and re-introspect on the next call."""
    global _CACHED_CONTEXT
    _CACHED_CONTEXT = None
    return get_schema_context()

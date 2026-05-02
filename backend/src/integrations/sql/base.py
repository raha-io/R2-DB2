"""Adapter Protocol shared by every SQL backend the analytical agent supports."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class ColumnInfo(TypedDict):
    name: str
    type: str


class TableInfo(TypedDict):
    name: str  # qualified, e.g. "schema.table" / "db.table"
    columns: list[ColumnInfo]


class QueryResult(TypedDict):
    columns: list[str]
    rows: list[tuple[Any, ...]]
    row_count: int


@runtime_checkable
class SqlAdapter(Protocol):
    dialect: str

    def list_tables(self) -> list[TableInfo]: ...

    def execute(
        self,
        sql: str,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult: ...

    def close(self) -> None: ...

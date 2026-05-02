"""ClickHouse adapter — wraps ``clickhouse-connect``."""

from __future__ import annotations

from typing import Any

from settings import ClickHouseDb

from .base import ColumnInfo, QueryResult, TableInfo


class ClickHouseAdapter:
    dialect = "clickhouse"

    def __init__(self, settings: ClickHouseDb) -> None:
        self._settings = settings

    def _client(self) -> Any:
        import clickhouse_connect

        s = self._settings
        return clickhouse_connect.get_client(
            host=s.host,
            port=s.port,
            username=s.user,
            password=s.password,
            database=s.database,
            secure=s.secure,
        )

    def list_tables(self) -> list[TableInfo]:
        client = self._client()
        try:
            result = client.query(
                "SELECT table, name, type "
                "FROM system.columns "
                "WHERE database = %(db)s "
                "ORDER BY table, position",
                parameters={"db": self._settings.database},
            )
        finally:
            client.close()

        grouped: dict[str, list[ColumnInfo]] = {}
        for table, name, type_ in result.result_rows:
            grouped.setdefault(table, []).append({"name": name, "type": type_})

        return [
            {"name": f"{self._settings.database}.{table}", "columns": cols}
            for table, cols in grouped.items()
        ]

    def execute(
        self,
        sql: str,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult:
        client = self._client()
        try:
            result = client.query(sql, parameters=parameters or {})
        finally:
            client.close()
        rows = [tuple(row) for row in result.result_rows]
        return {
            "columns": list(result.column_names),
            "rows": rows,
            "row_count": len(rows),
        }

    def close(self) -> None:
        # Connections are opened per call; nothing persistent to release.
        return None

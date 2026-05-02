"""MySQL adapter — uses ``pymysql``."""

from __future__ import annotations

from typing import Any

from settings import MysqlDb

from .base import ColumnInfo, QueryResult, TableInfo


class MysqlAdapter:
    dialect = "mysql"

    def __init__(self, settings: MysqlDb) -> None:
        self._settings = settings

    def _connect(self) -> Any:
        import pymysql

        s = self._settings
        return pymysql.connect(
            host=s.host,
            port=s.port,
            db=s.database,
            user=s.user,
            password=s.password,
        )

    def list_tables(self) -> list[TableInfo]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name, column_name, column_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = %s "
                    "ORDER BY table_name, ordinal_position",
                    (self._settings.database,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        grouped: dict[str, list[ColumnInfo]] = {}
        for table, name, type_ in rows:
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
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, parameters or ())
                columns = (
                    [desc[0] for desc in cur.description] if cur.description else []
                )
                fetched = cur.fetchall() if cur.description else []
        finally:
            conn.close()
        rows = [tuple(r) for r in fetched]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }

    def close(self) -> None:
        return None

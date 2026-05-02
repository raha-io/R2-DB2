"""PostgreSQL adapter — uses ``psycopg`` v3."""

from __future__ import annotations

from typing import Any

from settings import PostgresDb

from .base import ColumnInfo, QueryResult, TableInfo


class PostgresAdapter:
    dialect = "postgres"

    def __init__(self, settings: PostgresDb) -> None:
        self._settings = settings

    def _connect(self) -> Any:
        import psycopg

        s = self._settings
        return psycopg.connect(
            host=s.host,
            port=s.port,
            dbname=s.database,
            user=s.user,
            password=s.password,
            sslmode=s.sslmode,
        )

    def list_tables(self) -> list[TableInfo]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema = %(schema)s "
                "ORDER BY table_name, ordinal_position",
                {"schema": self._settings.db_schema},
            )
            rows = cur.fetchall()

        grouped: dict[str, list[ColumnInfo]] = {}
        for table, name, type_ in rows:
            grouped.setdefault(table, []).append({"name": name, "type": type_})

        return [
            {"name": f"{self._settings.db_schema}.{table}", "columns": cols}
            for table, cols in grouped.items()
        ]

    def execute(
        self,
        sql: str,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> QueryResult:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, parameters or {})
            columns = (
                [desc[0] for desc in cur.description] if cur.description else []
            )
            rows = [tuple(r) for r in cur.fetchall()] if cur.description else []
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }

    def close(self) -> None:
        return None

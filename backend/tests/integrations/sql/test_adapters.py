"""Adapter contract tests with mocked drivers.

Each adapter must:
- issue the documented introspection SQL on ``list_tables()``
- return :class:`QueryResult` with ``columns``, ``rows`` (tuples),
  and ``row_count`` on ``execute()``

The tests avoid any real network — drivers are injected as fake modules so
the suite passes whether or not the driver is installed.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from settings import ClickHouseDb, MysqlDb, PostgresDb


def _inject(name: str, **attrs: object) -> types.ModuleType:
    """Build a fake module and register it in ``sys.modules``."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── ClickHouse ──────────────────────────────────────────────────────────────


@pytest.fixture
def fake_clickhouse(monkeypatch):
    fake_result = MagicMock(
        result_rows=[
            ("orders", "id", "UInt32"),
            ("orders", "amount", "Decimal(12,2)"),
            ("customers", "id", "UInt32"),
        ],
        column_names=("id", "amount"),
    )
    fake_client = MagicMock()
    fake_client.query.return_value = fake_result
    get_client = MagicMock(return_value=fake_client)
    monkeypatch.setitem(
        sys.modules,
        "clickhouse_connect",
        _inject("clickhouse_connect", get_client=get_client),
    )
    return fake_client, get_client, fake_result


def test_clickhouse_list_tables_issues_system_columns_query(fake_clickhouse):
    fake_client, _, _ = fake_clickhouse
    from integrations.sql.clickhouse_adapter import ClickHouseAdapter

    adapter = ClickHouseAdapter(ClickHouseDb(database="analytics"))
    tables = adapter.list_tables()

    fake_client.query.assert_called_once()
    args, kwargs = fake_client.query.call_args
    assert "system.columns" in args[0]
    assert kwargs["parameters"] == {"db": "analytics"}

    assert tables == [
        {
            "name": "analytics.orders",
            "columns": [
                {"name": "id", "type": "UInt32"},
                {"name": "amount", "type": "Decimal(12,2)"},
            ],
        },
        {
            "name": "analytics.customers",
            "columns": [{"name": "id", "type": "UInt32"}],
        },
    ]


def test_clickhouse_execute_returns_query_result(fake_clickhouse):
    fake_client, _, fake_result = fake_clickhouse
    fake_result.column_names = ("id", "amount")
    fake_result.result_rows = [(1, 99.5), (2, 12.0)]

    from integrations.sql.clickhouse_adapter import ClickHouseAdapter

    adapter = ClickHouseAdapter(ClickHouseDb(database="analytics"))
    result = adapter.execute("SELECT id, amount FROM analytics.orders LIMIT 10")

    assert result == {
        "columns": ["id", "amount"],
        "rows": [(1, 99.5), (2, 12.0)],
        "row_count": 2,
    }


# ── PostgreSQL ──────────────────────────────────────────────────────────────


def _fake_psycopg_with(rows, description=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.description = description
    cursor.__enter__ = lambda self: self
    cursor.__exit__ = lambda *a: None

    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = lambda self: self
    conn.__exit__ = lambda *a: None

    connect = MagicMock(return_value=conn)
    return _inject("psycopg", connect=connect), conn, cursor, connect


def test_postgres_list_tables_uses_information_schema(monkeypatch):
    rows = [
        ("orders", "id", "integer"),
        ("orders", "amount", "numeric"),
        ("customers", "id", "integer"),
    ]
    module, conn, cursor, _ = _fake_psycopg_with(rows, description=None)
    monkeypatch.setitem(sys.modules, "psycopg", module)

    from integrations.sql.postgres_adapter import PostgresAdapter

    adapter = PostgresAdapter(PostgresDb(db_schema="public", database="analytics"))
    tables = adapter.list_tables()

    sql, params = cursor.execute.call_args[0]
    assert "information_schema.columns" in sql
    assert "table_schema = %(schema)s" in sql
    assert params == {"schema": "public"}

    assert tables == [
        {
            "name": "public.orders",
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "numeric"},
            ],
        },
        {
            "name": "public.customers",
            "columns": [{"name": "id", "type": "integer"}],
        },
    ]


def test_postgres_execute_returns_query_result(monkeypatch):
    description = [("id",), ("amount",)]
    rows = [(1, 99.5), (2, 12.0)]
    module, _, cursor, _ = _fake_psycopg_with(rows, description=description)
    monkeypatch.setitem(sys.modules, "psycopg", module)
    cursor.fetchall.return_value = rows

    from integrations.sql.postgres_adapter import PostgresAdapter

    adapter = PostgresAdapter(PostgresDb(database="analytics"))
    result = adapter.execute(
        "SELECT id, amount FROM orders LIMIT %(limit)s",
        parameters={"limit": 10},
    )

    sql, params = cursor.execute.call_args[0]
    assert sql.startswith("SELECT")
    assert params == {"limit": 10}
    assert result == {
        "columns": ["id", "amount"],
        "rows": [(1, 99.5), (2, 12.0)],
        "row_count": 2,
    }


# ── MySQL ───────────────────────────────────────────────────────────────────


def _fake_pymysql_with(rows, description=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.description = description
    cursor.__enter__ = lambda self: self
    cursor.__exit__ = lambda *a: None

    conn = MagicMock()
    conn.cursor.return_value = cursor

    connect = MagicMock(return_value=conn)
    return _inject("pymysql", connect=connect), conn, cursor, connect


def test_mysql_list_tables_uses_information_schema(monkeypatch):
    rows = [
        ("orders", "id", "int(11)"),
        ("orders", "amount", "decimal(12,2)"),
    ]
    module, _, cursor, _ = _fake_pymysql_with(rows, description=None)
    monkeypatch.setitem(sys.modules, "pymysql", module)

    from integrations.sql.mysql_adapter import MysqlAdapter

    adapter = MysqlAdapter(MysqlDb(database="analytics"))
    tables = adapter.list_tables()

    sql, params = cursor.execute.call_args[0]
    assert "information_schema.columns" in sql
    assert "table_schema = %s" in sql
    assert params == ("analytics",)

    assert tables == [
        {
            "name": "analytics.orders",
            "columns": [
                {"name": "id", "type": "int(11)"},
                {"name": "amount", "type": "decimal(12,2)"},
            ],
        }
    ]


def test_mysql_execute_returns_query_result(monkeypatch):
    description = [("id",), ("amount",)]
    rows = [(1, 99.5)]
    module, _, cursor, _ = _fake_pymysql_with(rows, description=description)
    monkeypatch.setitem(sys.modules, "pymysql", module)
    cursor.fetchall.return_value = rows

    from integrations.sql.mysql_adapter import MysqlAdapter

    adapter = MysqlAdapter(MysqlDb(database="analytics"))
    result = adapter.execute("SELECT id, amount FROM orders LIMIT 1")

    assert result == {
        "columns": ["id", "amount"],
        "rows": [(1, 99.5)],
        "row_count": 1,
    }

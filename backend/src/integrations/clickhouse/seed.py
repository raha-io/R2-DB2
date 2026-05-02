"""ClickHouse seed orchestrator — ties generation, DDL, and insertion together."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from settings import ClickHouseDb
from .seed_generators import (
    generate_customers,
    generate_orders,
    generate_events,
    NUM_CUSTOMERS,
    NUM_ORDERS,
    NUM_EVENTS,
)
from .seed_schema import ensure_database, ensure_tables
from .seed_insert import (
    insert_customers,
    insert_orders,
    insert_events,
)

logger = logging.getLogger(__name__)


def _create_client(settings: ClickHouseDb) -> Any:
    try:
        import clickhouse_connect
    except ImportError as exc:
        raise ImportError(
            "clickhouse-connect package is required. "
            "Install with: pip install 'r2-db2[clickhouse]'"
        ) from exc

    return clickhouse_connect.get_client(
        host=settings.host,
        port=settings.port,
        username=settings.user,
        password=settings.password,
        database=settings.database,
        secure=settings.secure,
    )


def _table_has_data(client: Any, table: str) -> bool:
    result = client.query(f"SELECT count() FROM {table}")
    count = result.result_rows[0][0]
    return count > 0


def seed_clickhouse_sync(settings: ClickHouseDb) -> None:
    """Seed ClickHouse with fake analytics data."""
    client = _create_client(settings)
    try:
        ensure_database(client, settings.database)
        ensure_tables(client, settings.database)

        if not _table_has_data(client, f"{settings.database}.customers"):
            logger.info("Seeding customers table")
            customers = generate_customers(NUM_CUSTOMERS)
            insert_customers(client, settings.database, customers)
        else:
            logger.info("Customers table already has data, skipping")

        if not _table_has_data(client, f"{settings.database}.orders"):
            logger.info("Seeding orders table")
            orders = generate_orders(NUM_ORDERS)
            insert_orders(client, settings.database, orders)
        else:
            logger.info("Orders table already has data, skipping")

        if not _table_has_data(client, f"{settings.database}.events"):
            logger.info("Seeding events table")
            events = generate_events(NUM_EVENTS)
            insert_events(client, settings.database, events)
        else:
            logger.info("Events table already has data, skipping")
    finally:
        client.close()


async def seed_clickhouse(settings: ClickHouseDb) -> None:
    """Async wrapper for seeding ClickHouse with fake analytics data."""
    await asyncio.to_thread(seed_clickhouse_sync, settings)


__all__ = ["seed_clickhouse", "seed_clickhouse_sync"]

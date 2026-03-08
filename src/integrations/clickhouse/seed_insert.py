"""ClickHouse DML: batch insertion helpers for seed data."""

import logging
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

BATCH_SIZE = 5_000


def chunked(items: Sequence[dict[str, Any]], size: int) -> Iterable[Sequence[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def insert_in_batches(
    client: Any, table: str, columns: Sequence[str], rows: Sequence[dict[str, Any]]
) -> None:
    for batch in chunked(rows, BATCH_SIZE):
        data = [tuple(row[column] for column in columns) for row in batch]
        client.insert(table, data, column_names=list(columns))


def insert_customers(client: Any, database: str, customers: Sequence[dict[str, Any]]) -> None:
    columns = [
        "customer_id",
        "name",
        "email",
        "signup_date",
        "tier",
        "lifetime_value",
        "country",
        "city",
        "age",
        "gender",
    ]
    insert_in_batches(client, f"{database}.customers", columns, customers)


def insert_orders(client: Any, database: str, orders: Sequence[dict[str, Any]]) -> None:
    columns = [
        "customer_id",
        "order_date",
        "order_timestamp",
        "status",
        "total_amount",
        "discount_amount",
        "shipping_cost",
        "payment_method",
        "channel",
        "region",
        "country",
        "city",
    ]
    insert_in_batches(client, f"{database}.orders", columns, orders)


def insert_events(client: Any, database: str, events: Sequence[dict[str, Any]]) -> None:
    columns = [
        "customer_id",
        "event_type",
        "event_timestamp",
        "page_url",
        "device",
        "browser",
        "session_id",
        "duration_seconds",
        "metadata",
    ]
    insert_in_batches(client, f"{database}.events", columns, events)


__all__ = ["insert_customers", "insert_orders", "insert_events", "insert_in_batches", "chunked"]

"""ClickHouse DDL: database and table creation for seed schema."""

from typing import Any


def ensure_database(client: Any, database: str) -> None:
    client.command(f"CREATE DATABASE IF NOT EXISTS {database}")


def ensure_tables(client: Any, database: str) -> None:
    client.command(
        f"""
        CREATE TABLE IF NOT EXISTS {database}.orders (
            order_id UUID DEFAULT generateUUIDv4(),
            customer_id UInt32,
            order_date Date,
            order_timestamp DateTime,
            status Enum8('pending'=1, 'confirmed'=2, 'shipped'=3, 'delivered'=4, 'cancelled'=5, 'returned'=6),
            total_amount Decimal(12, 2),
            discount_amount Decimal(10, 2),
            shipping_cost Decimal(8, 2),
            payment_method Enum8('credit_card'=1, 'debit_card'=2, 'paypal'=3, 'bank_transfer'=4, 'crypto'=5),
            channel Enum8('web'=1, 'mobile'=2, 'in_store'=3, 'marketplace'=4),
            region String,
            country String,
            city String
        ) ENGINE = MergeTree()
        ORDER BY (order_date, customer_id)
        PARTITION BY toYYYYMM(order_date);
        """
    )

    client.command(
        f"""
        CREATE TABLE IF NOT EXISTS {database}.customers (
            customer_id UInt32,
            name String,
            email String,
            signup_date Date,
            tier Enum8('free'=1, 'basic'=2, 'premium'=3, 'enterprise'=4),
            lifetime_value Decimal(12, 2),
            country String,
            city String,
            age UInt8,
            gender Enum8('male'=1, 'female'=2, 'other'=3)
        ) ENGINE = MergeTree()
        ORDER BY customer_id;
        """
    )

    client.command(
        f"""
        CREATE TABLE IF NOT EXISTS {database}.events (
            event_id UUID DEFAULT generateUUIDv4(),
            customer_id UInt32,
            event_type Enum8('page_view'=1, 'add_to_cart'=2, 'checkout_start'=3, 'purchase'=4, 'refund'=5, 'support_ticket'=6),
            event_timestamp DateTime,
            page_url String,
            device Enum8('desktop'=1, 'mobile'=2, 'tablet'=3),
            browser String,
            session_id String,
            duration_seconds UInt32,
            metadata String
        ) ENGINE = MergeTree()
        ORDER BY (event_timestamp, customer_id)
        PARTITION BY toYYYYMM(event_timestamp);
        """
    )


__all__ = ["ensure_database", "ensure_tables"]

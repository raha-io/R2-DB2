"""ClickHouse fake data seeder for analytics tables."""

from __future__ import annotations

import asyncio
import calendar
import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Sequence

from faker import Faker

from r2-db2.config.settings import ClickHouseSettings

logger = logging.getLogger(__name__)

BATCH_SIZE = 5_000


@dataclass(frozen=True)
class RegionInfo:
    region: str
    country: str
    city: str
    weight: float


REGIONS: list[RegionInfo] = [
    RegionInfo("North America", "United States", "New York", 0.22),
    RegionInfo("North America", "United States", "San Francisco", 0.08),
    RegionInfo("North America", "Canada", "Toronto", 0.06),
    RegionInfo("Europe", "United Kingdom", "London", 0.09),
    RegionInfo("Europe", "Germany", "Berlin", 0.07),
    RegionInfo("Europe", "France", "Paris", 0.06),
    RegionInfo("Europe", "Netherlands", "Amsterdam", 0.04),
    RegionInfo("Asia", "India", "Bangalore", 0.09),
    RegionInfo("Asia", "Japan", "Tokyo", 0.06),
    RegionInfo("Asia", "Singapore", "Singapore", 0.04),
    RegionInfo("South America", "Brazil", "Sao Paulo", 0.05),
    RegionInfo("Oceania", "Australia", "Sydney", 0.04),
]

ORDER_STATUSES = [
    "pending",
    "confirmed",
    "shipped",
    "delivered",
    "cancelled",
    "returned",
]

PAYMENT_METHODS = [
    "credit_card",
    "debit_card",
    "paypal",
    "bank_transfer",
    "crypto",
]

CHANNELS = ["web", "mobile", "in_store", "marketplace"]

CUSTOMER_TIERS = ["free", "basic", "premium", "enterprise"]

GENDERS = ["male", "female", "other"]

EVENT_TYPES = [
    "page_view",
    "add_to_cart",
    "checkout_start",
    "purchase",
    "refund",
    "support_ticket",
]

DEVICES = ["desktop", "mobile", "tablet"]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge", "Opera"]

PAGE_URLS = [
    "/",
    "/pricing",
    "/product/alpha",
    "/product/bravo",
    "/product/charlie",
    "/cart",
    "/checkout",
    "/support",
    "/blog/insights",
    "/blog/launch",
]


def seed_clickhouse_sync(settings: ClickHouseSettings) -> None:
    """Seed ClickHouse with fake analytics data."""
    client = _create_client(settings)
    try:
        _ensure_database(client, settings.database)
        _ensure_tables(client, settings.database)

        if not _table_has_data(client, f"{settings.database}.customers"):
            logger.info("Seeding customers table")
            customers = _generate_customers(500)
            _insert_customers(client, settings.database, customers)
        else:
            logger.info("Customers table already has data, skipping")

        if not _table_has_data(client, f"{settings.database}.orders"):
            logger.info("Seeding orders table")
            orders = _generate_orders(50_000)
            _insert_orders(client, settings.database, orders)
        else:
            logger.info("Orders table already has data, skipping")

        if not _table_has_data(client, f"{settings.database}.events"):
            logger.info("Seeding events table")
            events = _generate_events(200_000)
            _insert_events(client, settings.database, events)
        else:
            logger.info("Events table already has data, skipping")
    finally:
        client.close()


async def seed_clickhouse(settings: ClickHouseSettings) -> None:
    """Async wrapper for seeding ClickHouse with fake analytics data."""
    await asyncio.to_thread(seed_clickhouse_sync, settings)


def _create_client(settings: ClickHouseSettings) -> Any:
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


def _ensure_database(client: Any, database: str) -> None:
    client.command(f"CREATE DATABASE IF NOT EXISTS {database}")


def _ensure_tables(client: Any, database: str) -> None:
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


def _table_has_data(client: Any, table: str) -> bool:
    result = client.query(f"SELECT count() FROM {table}")
    count = result.result_rows[0][0]
    return count > 0


def _faker() -> Faker:
    faker = Faker()
    Faker.seed(42)
    return faker


def _random() -> random.Random:
    return random.Random(42)


def _date_range() -> tuple[date, date]:
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 2)
    return start_date, end_date


def _month_weight(month: int) -> float:
    if month in {11, 12}:
        return 1.8
    if month in {6, 7}:
        return 1.2
    return 1.0


def _pick_weighted_month(rng: random.Random) -> tuple[int, int]:
    start_date, end_date = _date_range()
    months: list[tuple[int, int]] = []
    weights: list[float] = []
    current = date(start_date.year, start_date.month, 1)
    while current <= end_date:
        months.append((current.year, current.month))
        weights.append(_month_weight(current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return rng.choices(months, weights=weights, k=1)[0]


def _random_date(rng: random.Random) -> date:
    year, month = _pick_weighted_month(rng)
    days_in_month = calendar.monthrange(year, month)[1]
    day = rng.randint(1, days_in_month)
    return date(year, month, day)


def _random_timestamp(rng: random.Random, on_date: date) -> datetime:
    random_time = time(
        hour=rng.randint(0, 23),
        minute=rng.randint(0, 59),
        second=rng.randint(0, 59),
    )
    return datetime.combine(on_date, random_time)


def _pick_region(rng: random.Random) -> RegionInfo:
    weights = [r.weight for r in REGIONS]
    return rng.choices(REGIONS, weights=weights, k=1)[0]


def _decimal(value: float, places: str) -> Decimal:
    quant = Decimal(places)
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def _generate_customers(count: int) -> list[dict[str, Any]]:
    faker = _faker()
    rng = _random()
    start_date, end_date = _date_range()
    customers: list[dict[str, Any]] = []

    for customer_id in range(1, count + 1):
        tier = rng.choices(CUSTOMER_TIERS, weights=[0.45, 0.35, 0.15, 0.05], k=1)[0]
        signup_date = faker.date_between(start_date=start_date, end_date=end_date)
        region = _pick_region(rng)
        age = rng.randint(18, 70)
        gender = rng.choices(GENDERS, weights=[0.48, 0.48, 0.04], k=1)[0]

        base_value = {
            "free": rng.uniform(20, 120),
            "basic": rng.uniform(100, 800),
            "premium": rng.uniform(600, 3500),
            "enterprise": rng.uniform(3000, 15000),
        }[tier]

        customers.append(
            {
                "customer_id": customer_id,
                "name": faker.name(),
                "email": faker.unique.email(),
                "signup_date": signup_date,
                "tier": tier,
                "lifetime_value": _decimal(base_value, "0.01"),
                "country": region.country,
                "city": region.city,
                "age": age,
                "gender": gender,
            }
        )

    return customers


def _generate_orders(count: int) -> list[dict[str, Any]]:
    faker = _faker()
    rng = _random()
    orders: list[dict[str, Any]] = []

    for _ in range(count):
        customer_id = rng.randint(1, 500)
        order_date = _random_date(rng)
        order_timestamp = _random_timestamp(rng, order_date)
        status = rng.choices(
            ORDER_STATUSES,
            weights=[0.05, 0.1, 0.2, 0.5, 0.1, 0.05],
            k=1,
        )[0]
        payment_method = rng.choices(
            PAYMENT_METHODS,
            weights=[0.55, 0.2, 0.15, 0.07, 0.03],
            k=1,
        )[0]
        channel = rng.choices(CHANNELS, weights=[0.5, 0.3, 0.1, 0.1], k=1)[0]
        region = _pick_region(rng)

        base_amount = rng.uniform(25, 800)
        if channel == "marketplace":
            base_amount *= 0.9
        if status in {"cancelled", "returned"}:
            base_amount *= 0.6

        discount_rate = rng.choices([0.0, 0.05, 0.1, 0.15], weights=[0.55, 0.2, 0.15, 0.1], k=1)[0]
        discount_amount = base_amount * discount_rate
        shipping_cost = rng.uniform(0, 25) if channel != "in_store" else 0.0
        total_amount = max(base_amount - discount_amount + shipping_cost, 5.0)

        orders.append(
            {
                "customer_id": customer_id,
                "order_date": order_date,
                "order_timestamp": order_timestamp,
                "status": status,
                "total_amount": _decimal(total_amount, "0.01"),
                "discount_amount": _decimal(discount_amount, "0.01"),
                "shipping_cost": _decimal(shipping_cost, "0.01"),
                "payment_method": payment_method,
                "channel": channel,
                "region": region.region,
                "country": region.country,
                "city": region.city,
            }
        )

    return orders


def _generate_events(count: int) -> list[dict[str, Any]]:
    faker = _faker()
    rng = _random()
    events: list[dict[str, Any]] = []

    for _ in range(count):
        customer_id = rng.randint(1, 500)
        event_timestamp = _random_timestamp(rng, _random_date(rng))
        event_type = rng.choices(
            EVENT_TYPES,
            weights=[0.55, 0.2, 0.12, 0.08, 0.03, 0.02],
            k=1,
        )[0]
        page_url = rng.choice(PAGE_URLS)
        device = rng.choices(DEVICES, weights=[0.5, 0.4, 0.1], k=1)[0]
        browser = rng.choice(BROWSERS)
        session_id = faker.uuid4()

        if event_type == "page_view":
            duration = rng.randint(5, 180)
        elif event_type == "add_to_cart":
            duration = rng.randint(10, 240)
        elif event_type == "checkout_start":
            duration = rng.randint(20, 400)
        elif event_type == "purchase":
            duration = rng.randint(60, 900)
        elif event_type == "refund":
            duration = rng.randint(30, 600)
        else:
            duration = rng.randint(120, 1200)

        metadata = {
            "referrer": faker.uri_path(),
            "campaign": faker.word(),
            "experiment": faker.word(),
        }

        events.append(
            {
                "customer_id": customer_id,
                "event_type": event_type,
                "event_timestamp": event_timestamp,
                "page_url": page_url,
                "device": device,
                "browser": browser,
                "session_id": session_id,
                "duration_seconds": duration,
                "metadata": str(metadata),
            }
        )

    return events


def _insert_customers(client: Any, database: str, customers: Sequence[dict[str, Any]]) -> None:
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
    _insert_in_batches(client, f"{database}.customers", columns, customers)


def _insert_orders(client: Any, database: str, orders: Sequence[dict[str, Any]]) -> None:
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
    _insert_in_batches(client, f"{database}.orders", columns, orders)


def _insert_events(client: Any, database: str, events: Sequence[dict[str, Any]]) -> None:
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
    _insert_in_batches(client, f"{database}.events", columns, events)


def _insert_in_batches(
    client: Any, table: str, columns: Sequence[str], rows: Sequence[dict[str, Any]]
) -> None:
    for batch in _chunked(rows, BATCH_SIZE):
        data = [tuple(row[column] for column in columns) for row in batch]
        client.insert(table, data, column_names=list(columns))


def _chunked(items: Sequence[dict[str, Any]], size: int) -> Iterable[Sequence[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]

"""Faker-based synthetic data generators for ClickHouse seed tables."""

import calendar
import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Sequence

from faker import Faker

logger = logging.getLogger(__name__)

# Constants
NUM_CUSTOMERS = 500
NUM_ORDERS = 50_000
NUM_EVENTS = 200_000


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

SALES_CHANNELS = ["web", "mobile", "in_store", "marketplace"]

PAYMENT_METHODS = [
    "credit_card",
    "debit_card",
    "paypal",
    "bank_transfer",
    "crypto",
]

EVENT_TYPES = [
    "page_view",
    "add_to_cart",
    "checkout_start",
    "purchase",
    "refund",
    "support_ticket",
]

DEVICE_TYPES = ["desktop", "mobile", "tablet"]

PRODUCT_CATEGORIES = ["alpha", "bravo", "charlie"]

CUSTOMER_TIERS = ["free", "basic", "premium", "enterprise"]

GENDERS = ["male", "female", "other"]

PAGE_URLS = [
    "/",
    "/pricing",
    "/docs",
    "/blog",
    "/features",
    "/checkout",
    "/support",
]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge", "Opera"]


def validate_required_seed_constants() -> None:
    required_constants: tuple[str, ...] = ("GENDERS", "PAGE_URLS", "BROWSERS")
    missing = [name for name in required_constants if name not in globals()]
    if missing:
        logger.error("Seed generator missing constants: %s", ", ".join(missing))
        raise NameError(
            "Missing required constants in seed_generators.py: " + ", ".join(missing)
        )


def faker_instance() -> Faker:
    faker = Faker()
    Faker.seed(42)
    return faker


def random_instance() -> random.Random:
    return random.Random(42)


def date_range() -> tuple[date, date]:
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 2)
    return start_date, end_date


def month_weight(month: int) -> float:
    if month in {11, 12}:
        return 1.8
    if month in {6, 7}:
        return 1.2
    return 1.0


def pick_weighted_month(rng: random.Random) -> tuple[int, int]:
    start_date, end_date = date_range()
    months: list[tuple[int, int]] = []
    weights: list[float] = []
    current = date(start_date.year, start_date.month, 1)
    while current <= end_date:
        months.append((current.year, current.month))
        weights.append(month_weight(current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return rng.choices(months, weights=weights, k=1)[0]


def random_date(rng: random.Random) -> date:
    year, month = pick_weighted_month(rng)
    days_in_month = calendar.monthrange(year, month)[1]
    day = rng.randint(1, days_in_month)
    return date(year, month, day)


def random_timestamp(rng: random.Random, on_date: date) -> datetime:
    random_time = time(
        hour=rng.randint(0, 23),
        minute=rng.randint(0, 59),
        second=rng.randint(0, 59),
    )
    return datetime.combine(on_date, random_time)


def pick_region(rng: random.Random) -> RegionInfo:
    weights = [r.weight for r in REGIONS]
    return rng.choices(REGIONS, weights=weights, k=1)[0]


def decimal_quantize(value: float, places: str) -> Decimal:
    quant = Decimal(places)
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def generate_customers(count: int) -> list[dict[str, Any]]:
    validate_required_seed_constants()
    faker = faker_instance()
    rng = random_instance()
    start_date, end_date = date_range()
    customers: list[dict[str, Any]] = []

    for customer_id in range(1, count + 1):
        tier = rng.choices(CUSTOMER_TIERS, weights=[0.45, 0.35, 0.15, 0.05], k=1)[0]
        signup_date = faker.date_between(start_date=start_date, end_date=end_date)
        region = pick_region(rng)
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
                "lifetime_value": decimal_quantize(base_value, "0.01"),
                "country": region.country,
                "city": region.city,
                "age": age,
                "gender": gender,
            }
        )

    return customers


def generate_orders(count: int) -> list[dict[str, Any]]:
    faker = faker_instance()
    rng = random_instance()
    orders: list[dict[str, Any]] = []

    for _ in range(count):
        customer_id = rng.randint(1, 500)
        order_date = random_date(rng)
        order_timestamp = random_timestamp(rng, order_date)
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
        channel = rng.choices(SALES_CHANNELS, weights=[0.5, 0.3, 0.1, 0.1], k=1)[0]
        region = pick_region(rng)

        base_amount = rng.uniform(25, 800)
        if channel == "marketplace":
            base_amount *= 0.9
        if status in {"cancelled", "returned"}:
            base_amount *= 0.6

        discount_rate = rng.choices(
            [0.0, 0.05, 0.1, 0.15], weights=[0.55, 0.2, 0.15, 0.1], k=1
        )[0]
        discount_amount = base_amount * discount_rate
        shipping_cost = rng.uniform(0, 25) if channel != "in_store" else 0.0
        total_amount = max(base_amount - discount_amount + shipping_cost, 5.0)

        orders.append(
            {
                "customer_id": customer_id,
                "order_date": order_date,
                "order_timestamp": order_timestamp,
                "status": status,
                "total_amount": decimal_quantize(total_amount, "0.01"),
                "discount_amount": decimal_quantize(discount_amount, "0.01"),
                "shipping_cost": decimal_quantize(shipping_cost, "0.01"),
                "payment_method": payment_method,
                "channel": channel,
                "region": region.region,
                "country": region.country,
                "city": region.city,
            }
        )

    return orders


def generate_events(count: int) -> list[dict[str, Any]]:
    validate_required_seed_constants()
    faker = faker_instance()
    rng = random_instance()
    events: list[dict[str, Any]] = []

    for _ in range(count):
        customer_id = rng.randint(1, 500)
        event_timestamp = random_timestamp(rng, random_date(rng))
        event_type = rng.choices(
            EVENT_TYPES,
            weights=[0.55, 0.2, 0.12, 0.08, 0.03, 0.02],
            k=1,
        )[0]
        page_url = rng.choice(PAGE_URLS)
        device = rng.choices(DEVICE_TYPES, weights=[0.5, 0.4, 0.1], k=1)[0]
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


__all__ = [
    "NUM_CUSTOMERS",
    "NUM_ORDERS",
    "NUM_EVENTS",
    "REGIONS",
    "ORDER_STATUSES",
    "SALES_CHANNELS",
    "PAYMENT_METHODS",
    "EVENT_TYPES",
    "DEVICE_TYPES",
    "PRODUCT_CATEGORIES",
    "GENDERS",
    "PAGE_URLS",
    "BROWSERS",
    "RegionInfo",
    "faker_instance",
    "random_instance",
    "date_range",
    "month_weight",
    "pick_weighted_month",
    "random_date",
    "random_timestamp",
    "pick_region",
    "decimal_quantize",
    "generate_customers",
    "generate_orders",
    "generate_events",
]

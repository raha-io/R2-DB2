"""Schema catalog for ClickHouse analytics database.

Provides structured descriptions of tables, columns, and relationships
for use as LLM context during SQL generation.
"""

from __future__ import annotations

from typing import TypedDict


class ColumnInfo(TypedDict):
    name: str
    type: str
    description: str


class TableInfo(TypedDict):
    name: str
    description: str
    columns: list[ColumnInfo]
    row_count_approx: int
    example_queries: list[str]


SCHEMA_CATALOG: list[TableInfo] = [
    {
        "name": "analytics.orders",
        "description": (
            "E-commerce order transactions with payment, shipping, and geographic details. "
            "Each row is one order."
        ),
        "columns": [
            {"name": "order_id", "type": "UUID", "description": "Unique order identifier"},
            {
                "name": "customer_id",
                "type": "UInt32",
                "description": "FK to customers.customer_id",
            },
            {"name": "order_date", "type": "Date", "description": "Date the order was placed"},
            {
                "name": "order_timestamp",
                "type": "DateTime",
                "description": "Exact timestamp of order placement",
            },
            {
                "name": "status",
                "type": "Enum8",
                "description": "Order status: pending, confirmed, shipped, delivered, cancelled, returned",
            },
            {"name": "total_amount", "type": "Decimal(12,2)", "description": "Total order value in USD"},
            {
                "name": "discount_amount",
                "type": "Decimal(10,2)",
                "description": "Discount applied in USD",
            },
            {
                "name": "shipping_cost",
                "type": "Decimal(8,2)",
                "description": "Shipping cost in USD",
            },
            {
                "name": "payment_method",
                "type": "Enum8",
                "description": "Payment method: credit_card, debit_card, paypal, bank_transfer, crypto",
            },
            {
                "name": "channel",
                "type": "Enum8",
                "description": "Sales channel: web, mobile, in_store, marketplace",
            },
            {
                "name": "region",
                "type": "String",
                "description": "Geographic region (e.g., North America, Europe)",
            },
            {"name": "country", "type": "String", "description": "Country name"},
            {"name": "city", "type": "String", "description": "City name"},
        ],
        "row_count_approx": 50_000,
        "example_queries": [
            "SELECT toYYYYMM(order_date) AS month, sum(total_amount) AS revenue FROM analytics.orders GROUP BY month ORDER BY month",
            "SELECT status, count() AS cnt FROM analytics.orders GROUP BY status",
            "SELECT region, avg(total_amount) AS avg_order FROM analytics.orders GROUP BY region ORDER BY avg_order DESC",
        ],
    },
    {
        "name": "analytics.customers",
        "description": (
            "Customer dimension table with signup attributes, tier, and lifetime value. "
            "Each row represents one customer."
        ),
        "columns": [
            {"name": "customer_id", "type": "UInt32", "description": "Primary key for customer"},
            {"name": "name", "type": "String", "description": "Customer full name"},
            {"name": "email", "type": "String", "description": "Customer email address"},
            {
                "name": "signup_date",
                "type": "Date",
                "description": "Date the customer signed up",
            },
            {
                "name": "tier",
                "type": "Enum8",
                "description": "Subscription tier: free, basic, premium, enterprise",
            },
            {
                "name": "lifetime_value",
                "type": "Decimal(12,2)",
                "description": "Estimated customer lifetime value in USD",
            },
            {"name": "country", "type": "String", "description": "Customer country"},
            {"name": "city", "type": "String", "description": "Customer city"},
            {"name": "age", "type": "UInt8", "description": "Customer age"},
            {
                "name": "gender",
                "type": "Enum8",
                "description": "Gender: male, female, other",
            },
        ],
        "row_count_approx": 500,
        "example_queries": [
            "SELECT tier, count() AS customers FROM analytics.customers GROUP BY tier",
            "SELECT country, avg(lifetime_value) AS avg_ltv FROM analytics.customers GROUP BY country ORDER BY avg_ltv DESC",
            "SELECT toYYYYMM(signup_date) AS month, count() FROM analytics.customers GROUP BY month ORDER BY month",
        ],
    },
    {
        "name": "analytics.events",
        "description": (
            "Product analytics event stream capturing user interactions and sessions. "
            "Each row represents a single event."
        ),
        "columns": [
            {"name": "event_id", "type": "UUID", "description": "Unique event identifier"},
            {
                "name": "customer_id",
                "type": "UInt32",
                "description": "FK to customers.customer_id",
            },
            {
                "name": "event_type",
                "type": "Enum8",
                "description": "Event type: page_view, add_to_cart, checkout_start, purchase, refund, support_ticket",
            },
            {
                "name": "event_timestamp",
                "type": "DateTime",
                "description": "Timestamp of event occurrence",
            },
            {"name": "page_url", "type": "String", "description": "Visited page URL"},
            {
                "name": "device",
                "type": "Enum8",
                "description": "Device type: desktop, mobile, tablet",
            },
            {"name": "browser", "type": "String", "description": "Browser name"},
            {"name": "session_id", "type": "String", "description": "Session identifier"},
            {
                "name": "duration_seconds",
                "type": "UInt32",
                "description": "Time spent on the event in seconds",
            },
            {
                "name": "metadata",
                "type": "String",
                "description": "Additional event metadata serialized as text",
            },
        ],
        "row_count_approx": 200_000,
        "example_queries": [
            "SELECT event_type, count() AS events FROM analytics.events GROUP BY event_type ORDER BY events DESC",
            "SELECT toYYYYMM(event_timestamp) AS month, count() AS events FROM analytics.events GROUP BY month ORDER BY month",
            "SELECT device, avg(duration_seconds) AS avg_duration FROM analytics.events GROUP BY device ORDER BY avg_duration DESC",
        ],
    },
]


def get_schema_context() -> str:
    """Format schema catalog as a text block for LLM system prompt."""
    lines: list[str] = ["## Available Tables\n"]
    for table in SCHEMA_CATALOG:
        lines.append(f"### {table['name']}")
        lines.append(f"{table['description']}")
        lines.append(f"Approximate rows: {table['row_count_approx']:,}\n")
        lines.append("| Column | Type | Description |")
        lines.append("|--------|------|-------------|")
        for col in table["columns"]:
            lines.append(f"| {col['name']} | {col['type']} | {col['description']} |")
        lines.append("\nExample queries:")
        for q in table["example_queries"]:
            lines.append(f"```sql\n{q}\n```")
        lines.append("")
    return "\n".join(lines)

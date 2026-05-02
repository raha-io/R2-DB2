"""Per-dialect prompt fragments and display labels."""

from __future__ import annotations

DIALECT_NOTES: dict[str, str] = {
    "clickhouse": (
        "ClickHouse:\n"
        "- Time bucketing: toStartOfDay/toStartOfMonth/toStartOfYear, "
        "dateDiff('day', a, b).\n"
        "- Aggregations: countIf, sumIf, uniq.\n"
        "- LIMIT N (no OFFSET needed for analytics)."
    ),
    "postgres": (
        "PostgreSQL:\n"
        "- Time bucketing: date_trunc('month', col), AGE() for differences.\n"
        "- Double-quote case-sensitive identifiers.\n"
        "- LIMIT N."
    ),
    "mysql": (
        "MySQL 8+:\n"
        "- Time bucketing: DATE_FORMAT(col, '%Y-%m-01') or DATE(col).\n"
        "- Backtick-quote identifiers.\n"
        "- LIMIT N."
    ),
}

DIALECT_LABELS: dict[str, str] = {
    "clickhouse": "ClickHouse",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
}

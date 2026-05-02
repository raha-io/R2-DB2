"""ClickHouse-specific helpers (seeder for the demo dataset).

Schema introspection and the SQL adapter live in
``integrations.sql`` so they can serve any supported dialect.
"""

from .seed import seed_clickhouse, seed_clickhouse_sync

__all__ = ["seed_clickhouse", "seed_clickhouse_sync"]

"""ClickHouse integration for the R2-DB2 analytical agent.

Provides schema catalog for context retrieval and data seeding for development.
"""

from .schema_catalog import get_schema_context

__all__ = ["get_schema_context"]

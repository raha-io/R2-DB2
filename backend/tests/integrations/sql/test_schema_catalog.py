"""Schema catalog renderer/scorer should be dialect-agnostic."""

from __future__ import annotations

import pytest

from integrations.sql import schema_catalog as sc


@pytest.fixture(autouse=True)
def _reset_caches():
    sc._CACHED_TABLES = None
    sc._CACHED_CONTEXT = None
    yield
    sc._CACHED_TABLES = None
    sc._CACHED_CONTEXT = None


def _tables():
    return [
        {
            "name": "analytics.orders",
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "numeric"},
                {"name": "customer_id", "type": "integer"},
            ],
        },
        {
            "name": "analytics.customers",
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "text"},
            ],
        },
        {
            "name": "analytics.events",
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "kind", "type": "text"},
            ],
        },
    ]


def test_render_focused_schema_promotes_keyword_matches():
    output = sc.render_focused_schema(
        keywords={"customer", "customers"}, tables=_tables(), top_k=2
    )
    assert "Most Relevant Tables" in output
    # `customers` should be in full detail (column rows present)
    assert "| name | text |" in output
    # `events` should be collapsed to the name-only index
    assert "events" in output
    assert "| kind | text |" not in output


def test_render_focused_schema_falls_back_to_full_when_no_match():
    output = sc.render_focused_schema(keywords={"unrelated"}, tables=_tables())
    # Falls back to the full rendering — every column appears
    for col in ("id", "amount", "customer_id", "name", "kind"):
        assert f"| {col} |" in output


def test_extract_keywords_drops_stopwords_and_short_tokens():
    keywords = sc.extract_keywords(
        "show me the total revenue per customer for the last month"
    )
    assert "customer" in keywords
    assert "revenue" in keywords
    assert "the" not in keywords
    assert "me" not in keywords

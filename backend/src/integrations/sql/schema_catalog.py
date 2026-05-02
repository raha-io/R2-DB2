"""Dialect-agnostic schema catalog.

Calls the active :class:`SqlAdapter` to introspect the configured analytics
database and renders a Markdown block for use as LLM context during SQL
generation. The raw table list and the rendered full-schema markdown are
both cached at module level; call :func:`refresh_schema_context` to
invalidate.

When an ``intent_spec`` is available the caller can request a focused view
via :func:`render_focused_schema`, which keeps the most-relevant tables in
full and collapses the rest to a name-only index so the SQL LLM doesn't
get drowned in 70+ tables it will never use.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from .base import TableInfo
from .registry import get_adapter

logger = logging.getLogger(__name__)

_CACHED_TABLES: list[TableInfo] | None = None
_CACHED_CONTEXT: str | None = None

_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "for",
    "in",
    "on",
    "by",
    "to",
    "from",
    "and",
    "or",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "show",
    "give",
    "list",
    "get",
    "me",
    "top",
    "best",
    "worst",
    "my",
    "our",
    "their",
    "this",
    "that",
    "these",
    "those",
    "last",
    "past",
    "over",
    "under",
    "how",
    "many",
    "much",
    "what",
    "which",
    "when",
    "where",
    "who",
    "whom",
    "number",
    "count",
    "total",
    "sum",
    "avg",
    "average",
    "mean",
    "median",
    "report",
    "analysis",
    "data",
    "per",
    "each",
    "all",
    "any",
    "some",
    "more",
    "less",
}

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")


def _render_table(table: TableInfo) -> list[str]:
    lines = [f"### {table['name']}\n", "| Column | Type |", "|--------|------|"]
    for col in table["columns"]:
        lines.append(f"| {col['name']} | {col['type']} |")
    lines.append("")
    return lines


def _render_full(tables: list[TableInfo]) -> str:
    lines: list[str] = ["## Available Tables\n"]
    for table in tables:
        lines.extend(_render_table(table))
    return "\n".join(lines)


def get_schema_tables() -> list[TableInfo]:
    """Return the introspected raw table list, caching the first result."""
    global _CACHED_TABLES
    if _CACHED_TABLES is not None:
        return _CACHED_TABLES

    adapter = get_adapter()
    try:
        _CACHED_TABLES = adapter.list_tables()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Schema introspection failed for dialect=%s: %s",
            adapter.dialect,
            exc,
        )
        _CACHED_TABLES = []
    else:
        logger.info(
            "Loaded schema tables for dialect=%s (%d tables)",
            adapter.dialect,
            len(_CACHED_TABLES),
        )
    return _CACHED_TABLES


def get_schema_context() -> str:
    """Return Markdown-formatted full schema context, introspecting on first call."""
    global _CACHED_CONTEXT
    if _CACHED_CONTEXT is not None:
        return _CACHED_CONTEXT

    tables = get_schema_tables()
    if not tables:
        adapter = get_adapter()
        return (
            f"## Available Tables\n\n"
            f"_Schema introspection failed for dialect `{adapter.dialect}`. "
            f"Check database connectivity._"
        )

    _CACHED_CONTEXT = _render_full(tables)
    return _CACHED_CONTEXT


def refresh_schema_context() -> str:
    """Invalidate caches and re-introspect on the next call."""
    global _CACHED_CONTEXT, _CACHED_TABLES
    _CACHED_CONTEXT = None
    _CACHED_TABLES = None
    return get_schema_context()


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text or "")
        if token.lower() not in _STOPWORDS
    }


def extract_keywords(*sources: Any) -> set[str]:
    """Flatten strings/lists into a deduplicated set of scoring keywords."""
    keywords: set[str] = set()
    for source in sources:
        if source is None:
            continue
        if isinstance(source, str):
            keywords |= _tokenize(source)
        elif isinstance(source, Iterable):
            for item in source:
                if isinstance(item, str):
                    keywords |= _tokenize(item)
    return keywords


def _score_table(table: TableInfo, keywords: set[str]) -> int:
    if not keywords:
        return 0
    table_name_tokens = _tokenize(table["name"])
    score = 3 * len(table_name_tokens & keywords)
    column_tokens: set[str] = set()
    for col in table["columns"]:
        column_tokens |= _tokenize(col["name"])
    score += len(column_tokens & keywords)
    return score


def render_focused_schema(
    keywords: set[str],
    *,
    top_k: int = 8,
    tables: list[TableInfo] | None = None,
) -> str:
    """Render schema with the top-scoring tables in full and the rest as a name index.

    Falls back to the full-schema rendering when no keywords are provided or
    when scoring produces no positive matches — we'd rather show everything
    than a misleadingly small slice.
    """
    tables = tables if tables is not None else get_schema_tables()
    if not tables:
        return get_schema_context()
    if not keywords:
        return _render_full(tables)

    scored = sorted(
        ((_score_table(t, keywords), t) for t in tables),
        key=lambda pair: pair[0],
        reverse=True,
    )
    top = [t for score, t in scored if score > 0][:top_k]
    if not top:
        return _render_full(tables)

    top_names = {t["name"] for t in top}
    rest = [t for t in tables if t["name"] not in top_names]

    lines: list[str] = [
        "## Most Relevant Tables\n",
        f"_Ranked by overlap with the user's request: {', '.join(sorted(keywords))}_\n",
    ]
    for table in top:
        lines.extend(_render_table(table))

    if rest:
        lines.append("## Other Tables (names only — ask for details if needed)\n")
        by_db: dict[str, list[str]] = {}
        for table in rest:
            db, _, local = table["name"].partition(".")
            by_db.setdefault(db, []).append(local or table["name"])
        for db in sorted(by_db):
            lines.append(f"### {db}")
            lines.append(", ".join(sorted(by_db[db])))
            lines.append("")

    return "\n".join(lines)

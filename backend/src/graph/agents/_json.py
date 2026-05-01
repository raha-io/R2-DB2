"""Robust JSON extraction from LLM responses.

Models often wrap their JSON in ``` fences or prepend a short preamble even
when told otherwise. This helper strips fences and falls back to extracting
the first top-level ``{...}`` block before parsing.
"""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_object(content: str) -> dict[str, Any] | None:
    """Return the parsed JSON object, or ``None`` if nothing valid is found."""
    stripped = (content or "").strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines[1:]).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(stripped)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None

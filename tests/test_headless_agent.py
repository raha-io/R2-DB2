"""Headless integration test for the R2-DB2 Analytics Agent.
Tests the agent end-to-end without any UI, using the OpenAI-compatible API.

Requires:
- Running backend (docker-compose up app)
- Or: R2_DB2_TEST_URL env var pointing to the backend

Usage:
  uv run pytest tests/test_headless_agent.py -v -s
  R2_DB2_TEST_URL=http://localhost:8000 uv run pytest tests/test_headless_agent.py -v -s
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

BASE_URL = os.environ.get("R2_DB2_TEST_URL", "http://localhost:8000")
STATUS_ONLY_PHRASES = {
    "analyzing",
    "processing",
    "thinking",
    "loading",
    "working",
    "please wait",
}


def _is_meaningful_answer(content: str) -> bool:
    """Return True when the response looks like a substantive assistant answer."""
    normalized = " ".join((content or "").strip().lower().split())
    if len(normalized) < 20:
        return False
    if normalized in STATUS_ONLY_PHRASES:
        return False
    if any(normalized.startswith(prefix) for prefix in STATUS_ONLY_PHRASES):
        # Allow full answers that happen to include status words later in text.
        if len(normalized.split()) < 6:
            return False
    return True


@pytest.mark.asyncio
async def test_health_check() -> None:
    """Test that the backend is reachable."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_completions_non_streaming() -> None:
    """Test non-streaming chat completion returns a response."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "r2-db2-analyst",
                "messages": [
                    {
                        "role": "user",
                        "content": "What tables are available in the database?",
                    }
                ],
                "stream": False,
            },
        )

    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
    data = resp.json()

    assert "choices" in data, f"No choices in response: {data}"
    assert len(data["choices"]) > 0

    content = data["choices"][0]["message"]["content"]
    print(f"\n--- Non-streaming response ---\n{content}\n---")
    assert _is_meaningful_answer(content), f"Not a meaningful answer: {content!r}"


@pytest.mark.asyncio
async def test_chat_completions_streaming() -> None:
    """Test streaming chat completion returns SSE chunks with substantive content."""
    collected_content: list[str] = []
    chunk_count = 0
    saw_done = False

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=300) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "r2-db2-analyst",
                "messages": [
                    {
                        "role": "user",
                        "content": "What tables are available in the database?",
                    }
                ],
                "stream": True,
            },
        ) as resp:
            assert resp.status_code == 200, f"Status {resp.status_code}: {await resp.aread()}"

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]  # Remove "data: " prefix

                if data_str.strip() == "[DONE]":
                    saw_done = True
                    break

                chunk_count += 1
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = payload.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    collected_content.append(content)

    assert chunk_count > 0, "No streaming chunks received"
    assert saw_done, "Streaming response did not terminate with [DONE]"

    full_content = "".join(collected_content).strip()
    print(f"\n--- Streaming response (collected) ---\n{full_content}\n---")

    assert full_content, "No assistant content found in stream"
    assert _is_meaningful_answer(full_content), f"Not a meaningful streaming answer: {full_content!r}"

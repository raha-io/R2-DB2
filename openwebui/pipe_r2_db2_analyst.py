"""
title: R2-DB2 Analytics Agent
description: Pipe function that connects Open WebUI to the R2-DB2 analytical agent backend. Supports streaming, charts, tables, and report downloads.
author: r2-db2-team
version: 0.1.0
license: MIT
"""

import json
import logging
import sys
from typing import AsyncGenerator, Awaitable, Callable, Optional, Union

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Pipe:
    """Open WebUI Pipe that routes chat to R2-DB2 analytical agent."""

    class Valves(BaseModel):
        """User-configurable settings shown in Open WebUI admin."""

        R2_DB2_API_BASE_URL: str = Field(
            default="http://app:8000",
            description="Base URL of the R2-DB2 backend API (Docker service name).",
        )
        R2_DB2_API_KEY: str = Field(
            default="sk-r2-db2-dev-key",
            description="API key for authentication with R2-DB2 backend.",
        )
        R2_DB2_MODEL_ID: str = Field(
            default="r2-db2-analyst",
            description="Model ID exposed by the R2-DB2 backend.",
        )
        REQUEST_TIMEOUT: int = Field(
            default=300,
            description="Request timeout in seconds for R2-DB2 API calls.",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        """Return the list of models this Pipe exposes."""
        return [
            {
                "id": self.valves.R2_DB2_MODEL_ID,
                "name": "R2-DB2 Analytics Agent",
                "description": "ClickHouse analytical agent — ask data questions in natural language.",
            }
        ]

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[..., Awaitable]] = None,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Process a chat completion request.

        Args:
            body: OpenAI-format request body with 'messages', 'stream', etc.
            __user__: Current user info from Open WebUI.
            __event_emitter__: Callback to emit status/citation events.
        """
        messages = body.get("messages", [])
        stream = body.get("stream", False)

        payload = {
            "model": self.valves.R2_DB2_MODEL_ID,
            "messages": messages,
            "stream": stream,
        }

        # Fix URL construction: strip trailing slash and handle /v1 suffix
        base_url = self.valves.R2_DB2_API_BASE_URL.rstrip("/")
        # Check if base_url already ends with /v1 before appending
        if base_url.endswith("/v1"):
            url = f"{base_url}/chat/completions"
        else:
            url = f"{base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.valves.R2_DB2_API_KEY}",
        }

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "🔍 Analyzing your question...", "done": False},
                }
            )

        try:
            if stream:
                return self._stream_response(url, headers, payload, __event_emitter__)
            else:
                return await self._non_stream_response(url, headers, payload, __event_emitter__)
        except aiohttp.ClientError as exc:
            logger.exception("HTTP error calling R2-DB2 backend")
            error_msg = f"❌ Backend connection error: {str(exc)}. Please verify the R2-DB2 backend is running at {base_url}"
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Error connecting to backend", "done": True},
                    }
                )
            return error_msg
        except Exception as exc:
            logger.exception("Unexpected error calling R2-DB2 backend")
            error_msg = f"❌ Unexpected error: {str(exc)}"
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Error connecting to backend", "done": True},
                    }
                )
            return error_msg

    async def _non_stream_response(
        self,
        url: str,
        headers: dict,
        payload: dict,
        __event_emitter__: Optional[Callable[..., Awaitable]],
    ) -> str:
        """Make a non-streaming request to R2-DB2 backend."""
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return f"❌ R2-DB2 API error ({resp.status}): {error_text}"

                data = await resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                if not content:
                    return "⚠️ The analytics backend returned an empty response. Please try rephrasing your question or check backend logs."

                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {"description": "✅ Analysis complete", "done": True},
                        }
                    )

                return content

    async def _stream_response(
        self,
        url: str,
        headers: dict,
        payload: dict,
        __event_emitter__: Optional[Callable[..., Awaitable]],
    ) -> AsyncGenerator[str, None]:
        """Stream response from R2-DB2 backend as SSE."""
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    yield f"❌ R2-DB2 API error ({resp.status}): {error_text}"
                    return

                buffer = ""
                content_received = False
                async for line_bytes in resp.content:
                    line = line_bytes.decode("utf-8", errors="replace")
                    buffer += line

                    while "\n" in buffer:
                        sse_line, buffer = buffer.split("\n", 1)
                        sse_line = sse_line.strip()

                        if not sse_line:
                            continue
                        if sse_line == "data: [DONE]":
                            if not content_received:
                                yield "\n\n⚠️ No response received from the analytics backend. Please check the backend logs."
                            if __event_emitter__:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": "✅ Analysis complete",
                                            "done": True,
                                        },
                                    }
                                )
                            return
                        if sse_line.startswith("data: "):
                            json_str = sse_line[6:]
                            try:
                                chunk_data = json.loads(json_str)
                                delta = (
                                    chunk_data.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content")
                                )
                                if delta:
                                    content_received = True
                                    yield delta
                            except json.JSONDecodeError as jde:
                                print(f"JSON parse error: {jde} - Raw line: {json_str}", file=sys.stderr)
                                continue

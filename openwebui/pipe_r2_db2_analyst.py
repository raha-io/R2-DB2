"""
title: R2-DB2 Analytics Agent
description: Pipe function that connects Open WebUI to the R2-DB2 analytical agent backend. Supports graph-native and OpenAI-compatible APIs with streaming and report links.
author: r2-db2-team
version: 0.2.0
license: MIT
"""

import json
import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional, Union

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
        USE_GRAPH_API: bool = Field(
            default=False,
            description="Use LangGraph-native API endpoints (/api/v1/analyze*) instead of OpenAI-compatible /v1/chat/completions.",
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
        """Process a chat request from Open WebUI."""
        messages = body.get("messages", [])
        stream = bool(body.get("stream", False))
        question = self._extract_last_user_message(messages)
        conversation_id = body.get("conversation_id")
        user_id = (__user__ or {}).get("id", "anonymous")
        headers = self._auth_headers()

        if not question:
            return "⚠️ No user question found in the request payload."

        logger.info(
            "pipe() called: stream=%s, question_len=%d, conversation_id=%s",
            stream, len(question), conversation_id,
        )

        await self._emit_status(
            __event_emitter__, "🔍 Analyzing your question...", done=False
        )

        try:
            if self.valves.USE_GRAPH_API:
                payload = {
                    "question": question,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                }
                if stream:
                    return self._graph_stream_response(
                        self._graph_stream_url(),
                        headers,
                        payload,
                        __event_emitter__,
                    )
                return await self._graph_non_stream_response(
                    self._graph_analyze_url(),
                    headers,
                    payload,
                    __event_emitter__,
                )

            payload = {
                "model": self.valves.R2_DB2_MODEL_ID,
                "messages": messages,
                "stream": stream,
                "conversation_id": conversation_id,
            }
            if stream:
                return self._openai_stream_response(
                    self._openai_chat_completions_url(),
                    headers,
                    payload,
                    __event_emitter__,
                )
            return await self._openai_non_stream_response(
                self._openai_chat_completions_url(),
                headers,
                payload,
                __event_emitter__,
            )
        except aiohttp.ClientError as exc:
            logger.exception("HTTP error calling R2-DB2 backend")
            await self._emit_status(
                __event_emitter__,
                "❌ Error connecting to backend",
                done=True,
            )
            return f"❌ Backend connection error: {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected pipe error")
            await self._emit_status(
                __event_emitter__,
                "❌ Unexpected error while calling backend",
                done=True,
            )
            return f"❌ Unexpected error: {exc}"

    async def _graph_non_stream_response(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        event_emitter: Optional[Callable[..., Awaitable]],
    ) -> str:
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await self._emit_status(event_emitter, "❌ Analysis failed", done=True)
                    return f"❌ R2-DB2 Graph API error ({resp.status}): {error_text}"

                data = await resp.json(content_type=None)
                result_text = self._format_graph_result(data)
                await self._emit_status(event_emitter, "✅ Analysis complete", done=True)
                return result_text

    async def _graph_stream_response(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        event_emitter: Optional[Callable[..., Awaitable]],
    ) -> AsyncGenerator[str, None]:
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await self._emit_status(event_emitter, "❌ Analysis failed", done=True)
                    yield f"❌ R2-DB2 Graph API error ({resp.status}): {error_text}"
                    return

                buffer = ""
                final_result: dict[str, Any] | None = None
                status_emitted = False

                async for line_bytes in resp.content:
                    buffer += line_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        raw_line, buffer = buffer.split("\n", 1)
                        sse_line = raw_line.strip()
                        if not sse_line:
                            continue
                        if sse_line == "data: [DONE]":
                            if final_result is None and not status_emitted:
                                yield "⚠️ Stream ended without a final result event."
                            break
                        if not sse_line.startswith("data: "):
                            continue

                        event_data = self._safe_json_loads(sse_line[6:])
                        if not isinstance(event_data, dict):
                            continue

                        event_type = event_data.get("type")
                        if event_type == "status":
                            node = event_data.get("node", "graph")
                            message = event_data.get("message", f"Processing {node}...")
                            status_emitted = True
                            await self._emit_status(event_emitter, message, done=False)
                            # Status shown via event_emitter only, not as content
                        elif event_type == "result":
                            final_result = event_data

                if final_result is not None:
                    yield self._format_graph_result(final_result)

                await self._emit_status(event_emitter, "✅ Analysis complete", done=True)

    async def _openai_non_stream_response(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        event_emitter: Optional[Callable[..., Awaitable]],
    ) -> str:
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await self._emit_status(event_emitter, "❌ Analysis failed", done=True)
                    return f"❌ R2-DB2 OpenAI API error ({resp.status}): {error_text}"

                data = await resp.json(content_type=None)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    content = "⚠️ The analytics backend returned an empty response."

                await self._emit_status(event_emitter, "✅ Analysis complete", done=True)
                return content

    async def _openai_stream_response(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        event_emitter: Optional[Callable[..., Awaitable]],
    ) -> AsyncGenerator[str, None]:
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await self._emit_status(event_emitter, "❌ Analysis failed", done=True)
                    yield f"❌ R2-DB2 OpenAI API error ({resp.status}): {error_text}"
                    return

                buffer = ""
                content_received = False
                async for line_bytes in resp.content:
                    buffer += line_bytes.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        raw_line, buffer = buffer.split("\n", 1)
                        sse_line = raw_line.strip()

                        if not sse_line:
                            continue
                        if sse_line == "data: [DONE]":
                            if not content_received:
                                yield (
                                    "\n\n⚠️ No response received from the analytics backend. "
                                    "Please check backend logs."
                                )
                            await self._emit_status(
                                event_emitter,
                                "✅ Analysis complete",
                                done=True,
                            )
                            return
                        if not sse_line.startswith("data: "):
                            continue

                        chunk_data = self._safe_json_loads(sse_line[6:])
                        if not isinstance(chunk_data, dict):
                            continue

                        delta = (
                            chunk_data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            content_received = True
                            yield delta

                if not content_received:
                    yield "\n\n⚠️ Stream ended without content from backend."
                await self._emit_status(event_emitter, "✅ Analysis complete", done=True)

    def _format_graph_result(self, data: dict[str, Any]) -> str:
        status = data.get("status")
        if status == "awaiting_approval":
            plan = data.get("plan")
            plan_json = json.dumps(plan, indent=2, ensure_ascii=False) if plan else "{}"
            return (
                "🛑 Plan approval required before execution.\n\n"
                f"Conversation ID: `{data.get('conversation_id', '')}`\n\n"
                "Proposed plan:\n"
                f"```json\n{plan_json}\n```\n\n"
                "Approve this plan in the backend approval flow to continue."
            )

        error = data.get("error")
        if error:
            return f"❌ Analysis failed: {error}"

        response_text = data.get("response") or ""
        report = data.get("report") if isinstance(data.get("report"), dict) else {}
        report_links = self._format_report_links(report)

        if report_links:
            if response_text:
                return f"{response_text}\n\n📥 Report artifacts:\n{report_links}"
            return f"📥 Report artifacts:\n{report_links}"

        return response_text or "⚠️ Analysis completed but no response text was returned."

    def _format_report_links(self, report: dict[str, Any]) -> str:
        if not report:
            return ""

        report_output = (
            report.get("report_output") if isinstance(report.get("report_output"), dict) else {}
        )
        report_id = (
            report.get("id")
            or report_output.get("report_id")
            or report.get("report_id")
        )
        if not report_id:
            return ""

        artifacts: list[dict[str, Any]] = []
        if isinstance(report_output.get("artifacts"), list):
            artifacts.extend(
                item for item in report_output["artifacts"] if isinstance(item, dict)
            )
        if isinstance(report.get("artifacts"), list):
            artifacts.extend(item for item in report["artifacts"] if isinstance(item, dict))

        if not artifacts:
            return ""

        api_root = self._api_root_url()
        lines: list[str] = []
        seen: set[str] = set()

        for artifact in artifacts:
            filename = artifact.get("filename")
            if not filename:
                path_value = artifact.get("path", "")
                if isinstance(path_value, str) and path_value:
                    filename = path_value.rsplit("/", maxsplit=1)[-1]
            if not filename or filename in seen:
                continue
            seen.add(filename)
            download_url = f"{api_root}/api/v1/reports/{report_id}/{filename}"
            lines.append(f"- [{filename}]({download_url})")

        return "\n".join(lines)

    async def _emit_status(
        self,
        event_emitter: Optional[Callable[..., Awaitable]],
        description: str,
        done: bool,
    ) -> None:
        if not event_emitter:
            return
        await event_emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done},
            }
        )

    def _extract_last_user_message(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"])
        return ""

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.valves.R2_DB2_API_KEY}",
        }

    def _api_root_url(self) -> str:
        base_url = self.valves.R2_DB2_API_BASE_URL.rstrip("/")
        if base_url.endswith("/api/v1"):
            return base_url[: -len("/api/v1")]
        if base_url.endswith("/v1"):
            return base_url[: -len("/v1")]
        return base_url

    def _openai_chat_completions_url(self) -> str:
        base_url = self.valves.R2_DB2_API_BASE_URL.rstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    def _graph_analyze_url(self) -> str:
        return f"{self._api_root_url()}/api/v1/analyze"

    def _graph_stream_url(self) -> str:
        return f"{self._api_root_url()}/api/v1/analyze/stream"

    def _safe_json_loads(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed SSE payload: %s", value)
            return None

"""
title: Download Report
description: Tool to list and download generated reports (PDF, CSV, Parquet, JSON, Plotly HTML) from the R2-DB2 analytics backend.
author: r2-db2-team
version: 0.2.0
license: MIT
"""

import json
import logging
from typing import Awaitable, Callable, Optional

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Tools:
    """Open WebUI Tool for downloading R2-DB2 analytics reports."""

    class Valves(BaseModel):
        """Admin-configurable settings."""

        R2_DB2_API_BASE_URL: str = Field(
            default="http://app:8000",
            description="Base URL of the R2-DB2 backend API.",
        )
        R2_DB2_API_KEY: str = Field(
            default="sk-r2-db2-dev-key",
            description="Bearer API key for the R2-DB2 backend API.",
        )
        REQUEST_TIMEOUT: int = Field(
            default=30,
            description="Request timeout in seconds.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def list_report_files(
        self,
        report_id: str,
        __event_emitter__: Optional[Callable[..., Awaitable]] = None,
    ) -> str:
        """List all available files for a given report.

        Use this when the user wants to see what report files are available for download.

        Args:
            report_id: The report ID returned by the analytics agent (e.g. from a previous analysis).

        Returns:
            A markdown-formatted list of available report files with download links.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"📋 Listing files for report {report_id}...",
                        "done": False,
                    },
                }
            )

        base = self.valves.R2_DB2_API_BASE_URL.rstrip("/")
        headers = {"Authorization": f"Bearer {self.valves.R2_DB2_API_KEY}"}
        url = f"{base}/api/v1/reports/{report_id}"
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"❌ Error listing report files ({resp.status}): {error_text}"

                    data = await resp.json()
                    artifacts = data.get("artifacts", [])

                    if not artifacts:
                        return f"No files found for report `{report_id}`."

                    # Build markdown table
                    lines = [
                        f"## 📁 Report Files ({report_id})\n",
                        "| File | Format | Size |",
                        "|------|--------|------|",
                    ]
                    for art in artifacts:
                        filename = art.get("filename", "unknown")
                        fmt = art.get("format", "unknown")
                        size = art.get("size_bytes", 0)
                        size_str = f"{size / 1024:.1f} KB" if size > 0 else "—"
                        download_url = f"{base}/api/v1/reports/{report_id}/{filename}"
                        lines.append(
                            f"| [{filename}]({download_url}) | {fmt} | {size_str} |"
                        )

                    lines.append(
                        f"\n💡 **Tip**: Click a filename to download, or ask me to get a specific file."
                    )

                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": "✅ Report files listed",
                                    "done": True,
                                },
                            }
                        )

                    return "\n".join(lines)

        except Exception as exc:
            logger.exception("Error listing report files")
            return f"❌ Error: {exc}"

    async def download_report_file(
        self,
        report_id: str,
        filename: str,
        __event_emitter__: Optional[Callable[..., Awaitable]] = None,
    ) -> str:
        """Get a download link for a specific report file.

        Use this when the user wants to download a specific file from a report.

        Args:
            report_id: The report ID.
            filename: The filename to download (e.g. "report.pdf", "data.csv").

        Returns:
            A markdown link to download the file.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"📥 Preparing download for {filename}...",
                        "done": False,
                    },
                }
            )

        base = self.valves.R2_DB2_API_BASE_URL.rstrip("/")
        headers = {"Authorization": f"Bearer {self.valves.R2_DB2_API_KEY}"}
        download_url = f"{base}/api/v1/reports/{report_id}/{filename}"

        # Verify the file exists
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(download_url, headers=headers) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("content-type", "unknown")
                        result = (
                            f"## 📥 Download Ready\n\n"
                            f"**File**: `{filename}`\n"
                            f"**Type**: {content_type}\n\n"
                            f"[⬇️ Click here to download]({download_url})"
                        )
                    else:
                        result = f"❌ File `{filename}` not found in report `{report_id}` (HTTP {resp.status})."
        except Exception as exc:
            logger.exception("Error checking report file")
            result = f"❌ Error: {exc}"

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "✅ Done", "done": True},
                }
            )

        return result

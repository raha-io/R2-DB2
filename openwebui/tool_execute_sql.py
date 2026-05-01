"""
title: Execute SQL Query
description: Tool to execute read-only SQL queries against ClickHouse via the R2-DB2 analytics backend and display results as markdown tables.
author: r2-db2-team
version: 0.2.0
license: MIT
"""

import logging
from typing import Awaitable, Callable, Optional

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Tools:
    """Open WebUI Tool for executing SQL queries via R2-DB2 backend."""

    class Valves(BaseModel):
        """Admin-configurable settings."""

        R2_DB2_API_BASE_URL: str = Field(
            default="http://app:8000",
            description="Base URL of the R2-DB2 backend API.",
        )
        R2_DB2_API_KEY: str = Field(
            default="sk-r2-db2-dev-key",
            description="API key used for Authorization header when calling R2-DB2 backend.",
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="Request timeout in seconds for SQL execution.",
        )
        MAX_DISPLAY_ROWS: int = Field(
            default=50,
            description="Maximum rows to display in the markdown table.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def execute_sql(
        self,
        sql_query: str,
        __event_emitter__: Optional[Callable[..., Awaitable]] = None,
    ) -> str:
        """Execute a read-only SQL query against the analytics database and return results as a table.

        Use this when the user asks to run a specific SQL query or wants to see raw query results.
        Only SELECT queries are allowed. DDL/DML statements will be rejected.

        Args:
            sql_query: The SQL SELECT query to execute.

        Returns:
            Query results formatted as a markdown table, or an error message.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "🔄 Executing SQL query...", "done": False},
                }
            )

        # Basic safety check
        sql_upper = sql_query.strip().upper()
        forbidden = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
        ]
        for keyword in forbidden:
            if sql_upper.startswith(keyword):
                return f"❌ **Rejected**: `{keyword}` statements are not allowed. Only SELECT queries are permitted."

        # Call the R2-DB2 graph-native API with the SQL query.
        base_url = self.valves.R2_DB2_API_BASE_URL.rstrip("/")
        url = f"{base_url}/api/v1/analyze"
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT)

        payload = {
            "question": f"Execute this SQL query and show the results:\n```sql\n{sql_query}\n```",
            "user_id": "openwebui-tool",
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.valves.R2_DB2_API_KEY}",
                    },
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"❌ API error ({resp.status}): {error_text}"

                    data = await resp.json()
                    status = data.get("status")
                    if status != "completed":
                        error = data.get("error") or f"Request status is '{status}'"
                        return f"❌ Query execution failed: {error}"

                    content = data.get("response", "")

                    if not content:
                        content = "No results returned."

                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": "✅ Query executed",
                                    "done": True,
                                },
                            }
                        )

                    return content

        except Exception as exc:
            logger.exception("Error executing SQL query")
            return f"❌ Error executing query: {exc}"

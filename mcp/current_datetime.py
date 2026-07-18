"""Provide the date and time function used by the local MCP server."""

from __future__ import annotations

from datetime import datetime as DateTime


def datetime() -> str:
    """Return the server's current local date and time with its UTC offset."""

    return DateTime.now().astimezone().isoformat(timespec="seconds")

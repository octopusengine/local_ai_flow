"""Small shared, non-secret local diagnostic services.

The functions return data only. Presentation and optional context-file logging
remain responsibilities of their CLI or agent adapters.
"""

from __future__ import annotations

from datetime import datetime
import subprocess
import sys
import time
from typing import Any


DEFAULT_PING_HOST = "8.8.8.8"
PING_TIMEOUT_SECONDS = 10.0


def system_datetime() -> str:
    """Return the current local date and time including its UTC offset."""

    return datetime.now().astimezone().isoformat(timespec="seconds")


def network_ping(host: str = DEFAULT_PING_HOST) -> dict[str, Any]:
    """Ping one fixed diagnostic target once and return a concise report."""

    command = ["ping", "-n", "1", host] if sys.platform.startswith("win") else ["ping", "-c", "1", host]
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=PING_TIMEOUT_SECONDS)
    except FileNotFoundError:
        return {
            "host": host,
            "reachable": False,
            "exit_code": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "summary": "ping command is unavailable on this system.",
            "output": "",
        }
    except subprocess.TimeoutExpired:
        return {
            "host": host,
            "reachable": False,
            "exit_code": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "summary": f"ping timed out after {PING_TIMEOUT_SECONDS:g} seconds.",
            "output": "",
        }
    output = result.stdout.strip() or result.stderr.strip()
    return {
        "host": host,
        "reachable": result.returncode == 0,
        "exit_code": result.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "summary": output.splitlines()[-1] if output else f"no response (exit code {result.returncode})",
        "output": output,
    }

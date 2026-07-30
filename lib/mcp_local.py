"""Shared local MCP configuration and safe tool-test catalog.

This module deliberately has no dependency on the MCP Python SDK.  Both the
local MCP server wrapper and the CLI client can therefore use it without
starting a server or importing the installed ``mcp`` package.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


DEFAULT_LOCAL_TOOL_NAME = "rot13"


@dataclass(frozen=True)
class LocalToolSpec:
    """One tool exposed by the project-local MCP server."""

    name: str
    safe_test_arguments: tuple[tuple[str, object], ...]

    def get_safe_test_arguments(self) -> dict[str, object]:
        """Return a fresh argument object suitable for a non-destructive test."""

        return dict(self.safe_test_arguments)


LOCAL_TOOL_SPECS = (
    LocalToolSpec("rot13", (("word", "apple"),)),
    LocalToolSpec("datetime", ()),
    LocalToolSpec("calculate", (("a", 2.0), ("b", 3.0), ("operation", "+"))),
)


def get_local_tool_spec(name: str) -> LocalToolSpec | None:
    """Return the local tool specification with this MCP name, if registered."""

    return next((tool_spec for tool_spec in LOCAL_TOOL_SPECS if tool_spec.name == name), None)


def get_safe_test_arguments(name: str) -> dict[str, object] | None:
    """Return dedicated safe arguments for one local tool, if declared."""

    tool_spec = get_local_tool_spec(name)
    return tool_spec.get_safe_test_arguments() if tool_spec is not None else None


def load_local_mcp_config(config_path: Path) -> dict[str, object]:
    """Load and validate the shared local MCP server configuration."""

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read MCP configuration {config_path}: {error}") from error
    if not isinstance(config, dict):
        raise RuntimeError("MCP configuration must be a JSON object.")
    if not isinstance(config.get("server_name"), str) or not config["server_name"].strip():
        raise RuntimeError("MCP configuration requires a non-empty server_name.")
    if not isinstance(config.get("host"), str) or not config["host"].strip():
        raise RuntimeError("MCP configuration requires a non-empty host.")
    if isinstance(config.get("port"), bool) or not isinstance(config.get("port"), int):
        raise RuntimeError("MCP configuration requires an integer port.")
    if not 1 <= config["port"] <= 65_535:
        raise RuntimeError("MCP configuration port must be between 1 and 65535.")
    if config.get("path") != "/mcp":
        raise RuntimeError("MCP configuration path must be /mcp.")
    if config.get("transport") != "streamable-http":
        raise RuntimeError("MCP configuration transport must be streamable-http.")
    if not isinstance(config.get("ollama_model"), str) or not config["ollama_model"].strip():
        raise RuntimeError("MCP configuration requires a non-empty ollama_model.")
    return config

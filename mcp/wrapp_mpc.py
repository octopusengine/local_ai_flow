"""Run the local MCP server and register all available project tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path


MODULE_DIRECTORY = Path(__file__).resolve().parent
CONFIG_PATH = MODULE_DIRECTORY / "mcp_config.json"

# Keep this directory out of the import search path while loading the installed
# `mcp` package. The directory is also named "mcp", so leaving it in place can
# make Python resolve the local project directory instead of the library.
module_directory_text = str(MODULE_DIRECTORY)
original_module_paths = [
    path
    for path in sys.path
    if Path(path or ".").resolve() == MODULE_DIRECTORY
]
sys.path = [
    path
    for path in sys.path
    if Path(path or ".").resolve() != MODULE_DIRECTORY
]
from mcp.server.fastmcp import FastMCP

sys.path[:0] = original_module_paths or [module_directory_text]
from calculate import calculate
from current_datetime import datetime
from rot13 import rot13


def load_config() -> dict[str, object]:
    """Load and validate the local MCP server configuration."""

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read MCP configuration {CONFIG_PATH}: {error}") from error

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
    return config


CONFIG = load_config()
mcp = FastMCP(
    CONFIG["server_name"],
    host=CONFIG["host"],
    port=CONFIG["port"],
    streamable_http_path=CONFIG["path"],
    stateless_http=True,
    json_response=True,
)

mcp.tool()(rot13)
mcp.tool()(datetime)
mcp.tool()(calculate)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

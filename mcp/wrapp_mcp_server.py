"""Run the local MCP server and register all available project tools."""

from __future__ import annotations

import sys
from pathlib import Path


__version__ = "0.26.01"

MODULE_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIRECTORY.parent
CONFIG_PATH = MODULE_DIRECTORY / "mcp_config.json"

# Import the shared project catalog before hiding the local ``mcp`` directory
# from Python's search path.  Keeping the catalog SDK-free lets cli_mcp.py use
# the same declarations without importing this runnable server module.
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)
    remove_project_root_after_import = True
else:
    remove_project_root_after_import = False
from lib.mcp_local import LOCAL_TOOL_SPECS, load_local_mcp_config
from lib.mcp_obt import (
    obt_get_address,
    obt_get_balance,
    obt_get_block,
    obt_get_blocks,
    obt_get_last_block,
    obt_get_tx,
    obt_get_tx_raw,
    obt_get_utxo,
)
if remove_project_root_after_import:
    sys.path.remove(project_root_text)

# Keep the local MCP directory and project root out of the import search path
# while loading the installed `mcp` package. Both can expose the local `mcp`
# directory and make Python resolve it instead of the SDK.
local_import_roots = {MODULE_DIRECTORY, PROJECT_ROOT}
original_local_paths = [
    path
    for path in sys.path
    if Path(path or ".").resolve() in local_import_roots
]
sys.path = [
    path
    for path in sys.path
    if Path(path or ".").resolve() not in local_import_roots
]
from mcp.server.fastmcp import FastMCP

restored_local_paths = [str(MODULE_DIRECTORY), *original_local_paths]
sys.path[:0] = list(dict.fromkeys(restored_local_paths))
from calculate import calculate
from current_datetime import datetime
from rot13 import rot13


def load_config() -> dict[str, object]:
    """Load and validate the local MCP server configuration."""

    return load_local_mcp_config(CONFIG_PATH)


CONFIG = load_config()
mcp = FastMCP(
    CONFIG["server_name"],
    host=CONFIG["host"],
    port=CONFIG["port"],
    streamable_http_path=CONFIG["path"],
    stateless_http=True,
    json_response=True,
)

LOCAL_TOOL_IMPLEMENTATIONS = {
    "rot13": rot13,
    "datetime": datetime,
    "calculate": calculate,
}


def register_local_tools() -> None:
    """Register every catalogued project-local tool with the MCP server."""

    for tool_spec in LOCAL_TOOL_SPECS:
        implementation = LOCAL_TOOL_IMPLEMENTATIONS.get(tool_spec.name)
        if implementation is None:
            raise RuntimeError(f"No implementation is registered for local MCP tool {tool_spec.name!r}.")
        mcp.tool()(implementation)

    for implementation in (
        obt_get_address,
        obt_get_utxo,
        obt_get_balance,
        obt_get_last_block,
        obt_get_block,
        obt_get_blocks,
        obt_get_tx_raw,
        obt_get_tx,
    ):
        mcp.tool()(implementation)


register_local_tools()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

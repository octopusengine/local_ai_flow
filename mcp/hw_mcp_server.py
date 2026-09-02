"""Expose configured local hardware as a small, safe stdio MCP server."""

from __future__ import annotations

import sys
from pathlib import Path


MODULE_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIRECTORY.parent

# Import project code before hiding the local ``mcp`` directory.  The project
# contains that directory for server scripts, while the installed MCP SDK also
# uses the name ``mcp``.
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)
    remove_project_root_after_import = True
else:
    remove_project_root_after_import = False
from lib.hw_mcp import list_hardware_devices, run_hardware_action
if remove_project_root_after_import:
    sys.path.remove(project_root_text)

local_import_roots = {MODULE_DIRECTORY, PROJECT_ROOT}
original_local_paths = [
    path for path in sys.path if Path(path or ".").resolve() in local_import_roots
]
sys.path = [
    path for path in sys.path if Path(path or ".").resolve() not in local_import_roots
]
from mcp.server.fastmcp import FastMCP

sys.path[:0] = list(dict.fromkeys([str(MODULE_DIRECTORY), *original_local_paths]))


mcp = FastMCP("Local external hardware")


@mcp.tool()
def hardware_list_devices() -> dict[str, object]:
    """List configured hardware and its allowed named actions without connecting."""

    return list_hardware_devices()


@mcp.tool()
async def hardware_run_action(
    device_id: str, action_id: str, timeout_seconds: float = 15.0
) -> dict[str, object]:
    """Run one configured BLE hardware action; raw commands and UUIDs are unavailable."""

    return await run_hardware_action(device_id, action_id, timeout_seconds)


if __name__ == "__main__":
    mcp.run(transport="stdio")

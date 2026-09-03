"""Expose local, policy-guarded Nostr operations through stdio MCP."""

from __future__ import annotations

import sys
from pathlib import Path


MODULE_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIRECTORY.parent
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)
    remove_project_root_after_import = True
else:
    remove_project_root_after_import = False
from lib import nostr_mcp
if remove_project_root_after_import:
    sys.path.remove(project_root_text)

local_import_roots = {MODULE_DIRECTORY, PROJECT_ROOT}
original_local_paths = [path for path in sys.path if Path(path or ".").resolve() in local_import_roots]
sys.path = [path for path in sys.path if Path(path or ".").resolve() not in local_import_roots]
from mcp.server.fastmcp import FastMCP
sys.path[:0] = list(dict.fromkeys([str(MODULE_DIRECTORY), *original_local_paths]))


mcp = FastMCP("Local Nostr agent")


@mcp.tool()
def nostr_status() -> dict[str, object]: return nostr_mcp.nostr_status()

@mcp.tool()
def nostr_doctor() -> dict[str, object]: return nostr_mcp.nostr_doctor()

@mcp.tool()
def nostr_list_relays(probe: bool = False) -> dict[str, object]: return nostr_mcp.nostr_list_relays(probe)

@mcp.tool()
def nostr_list_messages(limit: int | None = None, pending_only: bool = True) -> dict[str, object]: return nostr_mcp.nostr_list_messages(limit, pending_only)

@mcp.tool()
def nostr_get_message(message_id: int) -> dict[str, object]: return nostr_mcp.nostr_get_message(message_id)

@mcp.tool()
def nostr_sync(timeout_seconds: float = 30.0) -> dict[str, object]: return nostr_mcp.nostr_sync(timeout_seconds)

@mcp.tool()
def nostr_mark_handled(message_id: int, report: str) -> dict[str, object]: return nostr_mcp.nostr_mark_handled(message_id, report)

@mcp.tool()
def nostr_reply(message_id: int, text: str) -> dict[str, object]: return nostr_mcp.nostr_reply(message_id, text)


if __name__ == "__main__":
    mcp.run(transport="stdio")

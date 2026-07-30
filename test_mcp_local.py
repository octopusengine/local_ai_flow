"""Tests for shared local MCP configuration and tool catalog."""

from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

from lib.mcp_local import (
    DEFAULT_LOCAL_TOOL_NAME,
    LOCAL_TOOL_SPECS,
    get_safe_test_arguments,
    load_local_mcp_config,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "mcp" / "mcp_config.json"
SERVER_PATH = PROJECT_ROOT / "mcp" / "wrapp_mcp_server.py"


class LocalMcpCatalogTests(unittest.TestCase):
    def test_catalog_declares_the_default_and_safe_arguments(self) -> None:
        self.assertEqual(DEFAULT_LOCAL_TOOL_NAME, "rot13")
        self.assertEqual([tool_spec.name for tool_spec in LOCAL_TOOL_SPECS], ["rot13", "datetime", "calculate"])
        self.assertEqual(get_safe_test_arguments("rot13"), {"word": "apple"})
        self.assertEqual(get_safe_test_arguments("datetime"), {})
        self.assertEqual(get_safe_test_arguments("calculate"), {"a": 2.0, "b": 3.0, "operation": "+"})
        self.assertIsNone(get_safe_test_arguments("unknown"))

    def test_safe_arguments_are_returned_as_a_fresh_object(self) -> None:
        arguments = get_safe_test_arguments("rot13")
        assert arguments is not None
        arguments["word"] = "changed"

        self.assertEqual(get_safe_test_arguments("rot13"), {"word": "apple"})

    def test_shared_configuration_is_validated(self) -> None:
        config = load_local_mcp_config(CONFIG_PATH)

        self.assertEqual(config["path"], "/mcp")
        self.assertEqual(config["transport"], "streamable-http")

    def test_shared_configuration_rejects_a_missing_model(self) -> None:
        config = load_local_mcp_config(CONFIG_PATH)
        config.pop("ollama_model")
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "mcp_config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ollama_model"):
                load_local_mcp_config(config_path)

    def test_server_registers_the_tools_declared_by_the_catalog(self) -> None:
        registered_tools: list[str] = []

        class FakeMCP:
            def __init__(self, *_arguments: object, **_keywords: object) -> None:
                pass

            def tool(self):
                def register(function):
                    registered_tools.append(function.__name__)
                    return function

                return register

        fake_mcp_module = types.ModuleType("mcp")
        fake_server_module = types.ModuleType("mcp.server")
        fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fake_fastmcp_module.FastMCP = FakeMCP
        original_sys_path = sys.path.copy()
        try:
            with patch.dict(
                sys.modules,
                {
                    "mcp": fake_mcp_module,
                    "mcp.server": fake_server_module,
                    "mcp.server.fastmcp": fake_fastmcp_module,
                },
            ):
                runpy.run_path(str(SERVER_PATH), run_name="mcp_wrapper_test")
        finally:
            sys.path[:] = original_sys_path

        self.assertEqual(registered_tools, [tool_spec.name for tool_spec in LOCAL_TOOL_SPECS])


if __name__ == "__main__":
    unittest.main()

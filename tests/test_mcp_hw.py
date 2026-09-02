"""Unit tests for the allowlisted external-hardware MCP layer."""

from __future__ import annotations

import asyncio
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

import cli_mcp
from lib import device_runner
from lib import hw_mcp


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = PROJECT_ROOT / "mcp" / "hw_mcp_server.py"
SERVER_CONFIG_PATH = PROJECT_ROOT / "mcp" / "hw_server.json"


class HardwareMcpTests(unittest.TestCase):
    def test_public_catalog_excludes_transport_and_authentication_details(self) -> None:
        result = hw_mcp.list_hardware_devices()
        serialized = repr(result)

        self.assertIn("test-led", serialized)
        self.assertIn("temperature-read", serialized)
        self.assertNotIn("KEY1", serialized)
        self.assertNotIn("48:31:B7:33:D0:36", serialized)
        self.assertNotIn("!B516", serialized)
        self.assertNotIn("nordic-uart", serialized)

    def test_non_utf8_values_keep_hex_without_fabricated_text(self) -> None:
        self.assertEqual(hw_mcp._value_as_json(b"\xff\x00"), {"text": None, "hex": "ff 00"})

    def test_unknown_action_is_rejected_without_running_hardware(self) -> None:
        with patch.object(hw_mcp.device_runner, "run_device_tool", new_callable=AsyncMock) as run_tool:
            result = asyncio.run(hw_mcp.run_hardware_action("test-led", "not-configured"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], {"kind": "validation", "message": "action_id is not configured for this device."})
        run_tool.assert_not_awaited()

    def test_manual_only_toggle_is_rejected_without_running_hardware(self) -> None:
        with patch.object(hw_mcp.device_runner, "run_device_tool", new_callable=AsyncMock) as run_tool:
            result = asyncio.run(hw_mcp.run_hardware_action("test-led", "led-toggle"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], {"kind": "validation", "message": "action_id is not enabled for agent hardware access."})
        run_tool.assert_not_awaited()

    def test_runner_result_is_serialized_without_authentication_value(self) -> None:
        result_from_runner = device_runner.DeviceToolResult(
            device_id="test-led",
            tool_id="esp-hi",
            description="Send a greeting",
            address="48:31:B7:33:D0:36",
            address_source="advertised_name",
            connected=True,
            authentication_sent=True,
            sent=(device_runner.SentValue("nus-rx", b"hi"),),
            notifications=(device_runner.NotificationValue("nus-tx", "15", b"hello"),),
            duration_ms=123,
        )
        with patch.object(
            hw_mcp.device_runner, "run_device_tool", new=AsyncMock(return_value=result_from_runner)
        ):
            result = asyncio.run(hw_mcp.run_hardware_action("test-led", "esp-hi"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["sent"], [{"characteristic": "nus-rx", "text": "hi", "hex": "68 69"}])
        self.assertEqual(
            result["notifications"],
            [{"characteristic": "nus-tx", "sender": "15", "text": "hello", "hex": "68 65 6c 6c 6f"}],
        )
        self.assertNotIn("address", result)
        self.assertNotIn("KEY1", repr(result))

    def test_stdio_configuration_uses_the_project_root_as_working_directory(self) -> None:
        class FakeStdioServerParameters:
            def __init__(self, **keywords: object) -> None:
                self.command = keywords["command"]
                self.args = keywords["args"]
                self.cwd = keywords["cwd"]
                self.env = keywords["env"]

        with patch.object(cli_mcp, "StdioServerParameters", FakeStdioServerParameters):
            config = cli_mcp.load_external_server_config(SERVER_CONFIG_PATH)

        self.assertEqual(config.transport, "stdio")
        assert config.stdio_parameters is not None
        self.assertEqual(config.stdio_parameters.command, "python")
        self.assertEqual(config.stdio_parameters.args, ["mcp/hw_mcp_server.py"])
        self.assertEqual(Path(config.stdio_parameters.cwd), PROJECT_ROOT)

    def test_server_registers_only_the_two_hardware_tools(self) -> None:
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
                runpy.run_path(str(SERVER_PATH), run_name="hardware_mcp_server_test")
        finally:
            sys.path[:] = original_sys_path

        self.assertEqual(registered_tools, ["hardware_list_devices", "hardware_run_action"])


if __name__ == "__main__":
    unittest.main()

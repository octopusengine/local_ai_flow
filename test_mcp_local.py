"""Tests for shared local MCP configuration and tool catalog."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

import cli_mcp
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

        self.assertEqual(
            registered_tools,
            [tool_spec.name for tool_spec in LOCAL_TOOL_SPECS]
            + [
                "obt_get_address",
                "obt_get_utxo",
                "obt_get_balance",
                "obt_get_last_block",
                "obt_get_block",
                "obt_get_blocks",
                "obt_get_tx_raw",
                "obt_get_tx",
                "obt_build_transaction",
                "obt_send_transaction",
            ],
        )

    def test_remote_streamable_http_configuration_is_loaded_without_the_sdk(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "remote_server.json"
            config_path.write_text(
                json.dumps(
                    {
                        "transport": "streamable-http",
                        "url": "https://mcp.specification.website/mcp",
                        "headers": {"User-Agent": "local-ai-flow/1.0"},
                    }
                ),
                encoding="utf-8",
            )
            config = cli_mcp.load_external_server_config(config_path)

        self.assertEqual(config.transport, "streamable-http")
        self.assertEqual(config.endpoint, "https://mcp.specification.website/mcp")
        self.assertIsNone(config.stdio_parameters)
        self.assertEqual(config.headers, {"User-Agent": "local-ai-flow/1.0"})

    def test_remote_streamable_http_configuration_rejects_a_relative_url(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "remote_server.json"
            config_path.write_text(
                json.dumps({"transport": "streamable-http", "url": "/mcp"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "absolute"):
                cli_mcp.load_external_server_config(config_path)

    def test_remote_client_passes_configured_headers_to_httpx(self) -> None:
        created_clients: list[object] = []
        observed_connection: dict[str, object] = {}

        class FakeAsyncClient:
            def __init__(self, **keywords: object) -> None:
                self.keywords = keywords
                created_clients.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, _type, _value, _traceback) -> None:
                return None

        class FakeHttpx:
            AsyncClient = FakeAsyncClient

        async def fake_external_test(connection, *_arguments: object, **_keywords: object) -> bool:
            observed_connection["value"] = connection
            return True

        sentinel_connection = object()
        with (
            patch.object(cli_mcp, "httpx", FakeHttpx),
            patch.object(
                cli_mcp,
                "streamable_http_client",
                side_effect=lambda endpoint, http_client: (
                    observed_connection.update({"endpoint": endpoint, "client": http_client})
                    or sentinel_connection
                ),
            ),
            patch.object(cli_mcp, "run_external_session_test", side_effect=fake_external_test),
        ):
            result = asyncio.run(
                cli_mcp.run_remote_http_test(
                    "https://example.test/mcp",
                    {"User-Agent": "local-ai-flow/1.0"},
                    CONFIG_PATH,
                    "unused-model",
                    "unused-tool",
                    "apple",
                    2.0,
                    3.0,
                    "+",
                    list_tools_only=False,
                    provided_tool_arguments=None,
                    output_path=None,
                    db_enabled=False,
                    db_selector="",
                    project_directory=PROJECT_ROOT,
                    mcp_timeout_seconds=12.0,
                )
            )

        self.assertTrue(result)
        self.assertEqual(len(created_clients), 1)
        self.assertEqual(created_clients[0].keywords, {"headers": {"User-Agent": "local-ai-flow/1.0"}, "timeout": 12.0})
        self.assertEqual(observed_connection["endpoint"], "https://example.test/mcp")
        self.assertIs(observed_connection["value"], sentinel_connection)


if __name__ == "__main__":
    unittest.main()

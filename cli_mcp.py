"""Run a verbose MCP tool and Ollama tool-calling integration test.

Usage:
    python cli_mcp.py
    python cli_mcp.py --model qwen3.5:latest --function rot13 --word apple
    python cli_mcp.py --model qwen3.5:latest --function datetime
    python cli_mcp.py --model qwen3.5:latest --function calculate --a 8 --b 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from lib.wrapp_cli_log import load_project_directory, project_log, read_log_enabled
from lib.wrapp_ollama import ollama_api


PROJECT_ROOT = Path(__file__).resolve().parent
CLI_CONFIG_PATH = PROJECT_ROOT / "cli_mcp.json"
MCP_CONFIG_PATH = PROJECT_ROOT / "mcp" / "mcp_config.json"
SERVER_PATH = PROJECT_ROOT / "mcp" / "wrapp_mpc.py"
OLLAMA_CONFIG_PATH = PROJECT_ROOT / "lib" / "config.json"

REPORT_STARTED_AT = time.monotonic()


def report(message: str, *, error: bool = False) -> None:
    """Print a timestamped progress message immediately to terminal and project log."""

    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    elapsed_seconds = time.monotonic() - REPORT_STARTED_AT
    prefix = f"[{timestamp} +{elapsed_seconds:7.1f}s]"
    print(f"{prefix} {message}", file=sys.stderr if error else sys.stdout, flush=True)


def load_mcp_config() -> dict[str, object]:
    """Load MCP test settings from mcp/mcp_config.json."""

    try:
        config = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read MCP configuration {MCP_CONFIG_PATH}: {error}") from error
    if not isinstance(config, dict):
        raise RuntimeError("MCP configuration must be a JSON object.")
    return config


def parse_arguments(config: dict[str, object]) -> argparse.Namespace:
    """Read an optional model, tool name, and source word."""

    default_model = config.get("ollama_model")
    if not isinstance(default_model, str) or not default_model.strip():
        raise ValueError("MCP configuration requires a non-empty ollama_model.")
    parser = argparse.ArgumentParser(
        description="Test MCP tool discovery, parameter passing, and Ollama tool calling."
    )
    parser.add_argument("--model", default=default_model, help=f"Ollama model (default: {default_model})")
    parser.add_argument(
        "--function",
        default="rot13",
        help="MCP function to test (default: rot13)",
    )
    parser.add_argument("--word", default="apple", help="ASCII word to pass to the tool (default: apple)")
    parser.add_argument("--a", type=float, default=2.0, help="First calculator number (default: 2)")
    parser.add_argument("--b", type=float, default=3.0, help="Second calculator number (default: 3)")
    parser.add_argument(
        "--operation",
        choices=("+", "-", "*", "/"),
        default="+",
        help="Calculator operation (default: +)",
    )
    return parser.parse_args()


def tool_schema(tool: Any) -> dict[str, object]:
    """Convert MCP tool metadata to the schema expected by Ollama chat."""

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or f"Execute the {tool.name} MCP tool.",
            "parameters": tool.inputSchema,
        },
    }


def get_text_result(result: object, function_name: str) -> str:
    """Return the first text item from an MCP CallToolResult."""

    if getattr(result, "isError", False):
        raise RuntimeError(f"The MCP {function_name} tool returned an error.")
    for item in getattr(result, "content", []):
        if isinstance(item, types.TextContent):
            return item.text
    raise RuntimeError(f"The MCP {function_name} tool did not return text content.")


def build_tool_arguments(
    tool: Any,
    word: str,
    number_a: float,
    number_b: float,
    operation: str,
) -> dict[str, object]:
    """Build test arguments for the MCP tools supported by this CLI."""

    schema = tool.inputSchema
    if not isinstance(schema, dict):
        raise RuntimeError(f"The MCP {tool.name} tool has an invalid input schema.")

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise RuntimeError(f"The MCP {tool.name} tool has an invalid input schema.")
    if "word" in properties:
        return {"word": word}
    if {"a", "b"}.issubset(properties):
        arguments: dict[str, object] = {"a": number_a, "b": number_b}
        if "operation" in properties:
            arguments["operation"] = operation
        return arguments
    if not required:
        return {}
    raise RuntimeError(
        f"The CLI does not know how to prepare required arguments for MCP function "
        f"{tool.name!r}: {', '.join(str(name) for name in required)}."
    )


def port_is_open(host: str, port: int) -> bool:
    """Return whether a TCP listener is already available."""

    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_for_port(
    host: str,
    port: int,
    server: subprocess.Popen[bytes],
    timeout_seconds: float = 15.0,
) -> None:
    """Wait until the newly started MCP server accepts TCP connections."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(
                f"MCP server exited before opening {host}:{port} "
                f"(exit code {server.returncode})."
            )
        if port_is_open(host, port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"MCP server did not start at {host}:{port}.")


def call_ollama_chat(
    api: ollama_api, model: str, messages: list[dict[str, object]], tools: list[dict[str, object]] | None
) -> dict[str, object]:
    """Call Ollama chat using the existing project's Ollama API configuration."""

    payload: dict[str, object] = {"model": model, "messages": messages, "stream": False}
    if tools is not None:
        payload["tools"] = tools
    response = requests.post(
        f"{api.base_url}/api/chat",
        json=payload,
        timeout=(10, api.read_timeout_seconds),
    )
    if response.status_code == 404:
        raise RuntimeError(
            "Ollama does not expose /api/chat. Update Ollama to a version that supports "
            "tool calling, then use a tool-capable model."
        )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Ollama chat response must be a JSON object.")
    return data


async def call_ollama_chat_with_progress(
    api: ollama_api,
    model: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]] | None,
    *,
    stage: str,
) -> dict[str, object]:
    """Call Ollama without leaving long-running requests silent in the progress log."""

    started_at = time.monotonic()
    request_task = asyncio.create_task(
        asyncio.to_thread(call_ollama_chat, api, model, messages, tools)
    )
    report(
        f"{stage}: request sent; waiting for Ollama "
        f"(timeout {api.read_timeout_seconds:g} s)..."
    )
    while True:
        try:
            response = await asyncio.wait_for(asyncio.shield(request_task), timeout=15)
        except TimeoutError:
            elapsed_seconds = time.monotonic() - started_at
            report(
                f"{stage}: still waiting after {elapsed_seconds:.0f} s "
                f"(timeout {api.read_timeout_seconds:g} s)."
            )
            continue
        elapsed_seconds = time.monotonic() - started_at
        report(f"{stage}: Ollama response received in {elapsed_seconds:.1f} s.")
        return response


async def run_test(
    config: dict[str, object],
    model: str,
    function_name: str,
    word: str,
    number_a: float,
    number_b: float,
    operation: str,
) -> bool:
    """Verify MCP communication, then let Ollama request the selected MCP tool."""

    host, port, path = config.get("host"), config.get("port"), config.get("path")
    if not isinstance(host, str) or not isinstance(port, int) or not isinstance(path, str):
        raise ValueError("MCP configuration requires host, port, and path.")

    endpoint = f"http://{host}:{port}{path}"
    report("Starting MCP integration test.")
    report(f"MCP configuration: {MCP_CONFIG_PATH}")
    report(f"MCP endpoint: {endpoint}")
    report(f"MCP function: {function_name}")
    report(f"Ollama model: {model}")
    if port_is_open(host, port):
        raise RuntimeError(
            f"Port {host}:{port} is already occupied. Stop the existing server "
            "or change the port in mcp/mcp_config.json."
        )
    report(f"Starting local MCP server: {SERVER_PATH}")
    server = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        report(f"Waiting for MCP server on {host}:{port}...")
        wait_for_port(host, port, server)
        report("MCP server port: ready")
        api = ollama_api(config_path=OLLAMA_CONFIG_PATH)
        report(f"Ollama response timeout: {api.read_timeout_seconds:g} s")
        report("Opening MCP HTTP session...")
        async with streamable_http_client(endpoint) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                report("Sending MCP initialize request...")
                await session.initialize()
                report("MCP handshake: OK")

                report("Requesting MCP tool list...")
                tools_response = await session.list_tools()
                available_tools = ", ".join(tool.name for tool in tools_response.tools)
                report(f"MCP tools: {available_tools}")
                selected_tool = next(
                    (tool for tool in tools_response.tools if tool.name == function_name), None
                )
                if selected_tool is None:
                    report(
                        f"ERROR: MCP function {function_name!r} is unavailable. "
                        f"Available functions: {available_tools}.",
                        error=True,
                    )
                    return False

                arguments = build_tool_arguments(
                    selected_tool,
                    word,
                    number_a,
                    number_b,
                    operation,
                )
                report(f"Calling MCP {function_name} with arguments: {arguments}")
                direct_result = get_text_result(
                    await session.call_tool(function_name, arguments), function_name
                )
                if "word" in arguments:
                    report(f"MCP parameter test result: {word.upper()} -> {direct_result}")
                elif {"a", "b"}.issubset(arguments):
                    report(
                        f"MCP calculation test result: {arguments['a']} "
                        f"{arguments.get('operation', '+')} {arguments['b']} = {direct_result}"
                    )
                else:
                    report(f"MCP parameterless test result: {direct_result}")

                ollama_tools = [tool_schema(selected_tool)]
                if arguments:
                    task_description = (
                        f"Call it with exactly these arguments: "
                        f"{json.dumps(arguments, ensure_ascii=False)}."
                    )
                else:
                    task_description = "Call it without arguments."
                messages: list[dict[str, object]] = [{
                    "role": "user",
                    "content": (
                        f"Use the {function_name} tool. {task_description} "
                        "Do not perform the operation yourself. Return the tool result exactly."
                    ),
                }]
                report("Sending MCP tool schema to Ollama /api/chat...")
                try:
                    first_response = await call_ollama_chat_with_progress(
                        api,
                        model,
                        messages,
                        ollama_tools,
                        stage="Ollama tool-call request",
                    )
                except (RuntimeError, requests.RequestException) as error:
                    report(f"ERROR: Ollama tool-calling test could not start: {error}", error=True)
                    return False

                assistant_message = first_response.get("message")
                if not isinstance(assistant_message, dict):
                    raise RuntimeError("Ollama did not return an assistant message.")
                tool_calls = assistant_message.get("tool_calls")
                if not isinstance(tool_calls, list) or not tool_calls:
                    raise RuntimeError("The model did not request a tool. Use a tool-capable Ollama model.")
                report(f"Ollama requested {len(tool_calls)} tool call(s).")

                messages.append(assistant_message)
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        raise RuntimeError("Ollama returned an invalid tool call.")
                    function = tool_call.get("function")
                    if not isinstance(function, dict) or function.get("name") != function_name:
                        raise RuntimeError("Ollama requested an unexpected tool.")
                    call_arguments = function.get("arguments")
                    if not isinstance(call_arguments, dict):
                        raise RuntimeError("Ollama did not provide tool-call arguments.")
                    report(f"Forwarding Ollama arguments to MCP {function_name}: {call_arguments}")
                    mcp_result = get_text_result(
                        await session.call_tool(function_name, call_arguments), function_name
                    )
                    report(f"MCP result returned to Ollama: {mcp_result}")
                    messages.append(
                        {"role": "tool", "tool_name": function_name, "content": mcp_result}
                    )

                report("Sending MCP result back to Ollama /api/chat...")
                try:
                    final_response = await call_ollama_chat_with_progress(
                        api,
                        model,
                        messages,
                        ollama_tools,
                        stage="Ollama final-response request",
                    )
                except (RuntimeError, requests.RequestException) as error:
                    report(f"ERROR: Ollama tool-calling test could not finish: {error}", error=True)
                    return False
                final_message = final_response.get("message")
                if not isinstance(final_message, dict) or not isinstance(final_message.get("content"), str):
                    raise RuntimeError("Ollama did not return final text after the MCP tool result.")
                report(f"Final model response: {final_message['content']}")
                report("MCP and Ollama tool-calling test: PASSED")
                return True
    finally:
        report("Stopping local MCP server...")
        if server.poll() is None:
            server.terminate()
        try:
            server_stdout, server_stderr = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            report("MCP server did not stop in time; terminating it.")
            server.kill()
            server_stdout, server_stderr = server.communicate()
        report("Local MCP server stopped.")
        if server_stdout.strip():
            report(f"MCP server stdout:\n{server_stdout.strip()}")
        if server_stderr.strip():
            report(f"MCP server stderr:\n{server_stderr.strip()}", error=True)


def main() -> int:
    """Run the end-to-end MCP and Ollama tool-calling test."""

    try:
        config = load_mcp_config()
        arguments = parse_arguments(config)
        project_directory = load_project_directory(PROJECT_ROOT)
        log_enabled = read_log_enabled(CLI_CONFIG_PATH)
    except (OSError, RuntimeError, ValueError) as error:
        report(f"ERROR: {error}", error=True)
        return 1

    with project_log(project_directory, "cli_mcp.py", log_enabled):
        try:
            return 0 if asyncio.run(
                run_test(
                    config,
                    arguments.model,
                    arguments.function,
                    arguments.word,
                    arguments.a,
                    arguments.b,
                    arguments.operation,
                )
            ) else 1
        except (OSError, RuntimeError, ValueError, requests.RequestException) as error:
            report(f"ERROR: {error}", error=True)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

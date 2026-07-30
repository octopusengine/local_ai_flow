"""Run an MCP tool and Ollama tool-calling integration test.

Usage:
    python cli_mcp.py
    python cli_mcp.py --list
    python cli_mcp.py --list --out tools.txt
    python cli_mcp.py --server-config mcp/memory_server.json --list
    python cli_mcp.py --server-config mcp/filesystem_server.json --function list_allowed_directories
    python cli_mcp.py --model qwen3.5:latest --function rot13 --word apple
    python cli_mcp.py --ollama --model qwen3.5:latest --function rot13 --word apple
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

from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_project_config,
    read_debug_enabled,
    read_log_enabled,
)
from lib.wrapp_ollama import ollama_api
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent
MCP_CONFIG_PATH = PROJECT_ROOT / "mcp" / "mcp_config.json"
SERVER_PATH = PROJECT_ROOT / "mcp" / "wrapp_mcp.py"
OLLAMA_CONFIG_PATH = PROJECT_ROOT / "lib" / "ollama.json"

REPORT_STARTED_AT = time.monotonic()
REPORT_DEBUG_ENABLED = False
requests: Any = None
ClientSession: Any = None
types: Any = None
StdioServerParameters: Any = None
stdio_client: Any = None
streamable_http_client: Any = None


def report(message: str, *, error: bool = False, debug: bool = False) -> None:
    """Print an important message, or a timestamped diagnostic in debug mode."""

    if debug and not REPORT_DEBUG_ENABLED:
        return
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    elapsed_seconds = time.monotonic() - REPORT_STARTED_AT
    prefix = f"[{timestamp} +{elapsed_seconds:7.1f}s] "
    print(f"{prefix}{message}", file=sys.stderr if error else sys.stdout, flush=True)


def report_error_context(
    stage: str,
    error: BaseException,
    *,
    server_config_path: Path | None = None,
    server_command: str | None = None,
) -> None:
    """Print concise, actionable diagnostics for a CLI failure."""

    report(f"ERROR: cli_mcp.py failed during {stage}.", error=True)
    report(f"Reason: {format_exception_message(error)}", error=True)
    report(f"Python executable: {sys.executable}", error=True)
    report(f"Python version: {sys.version.split()[0]}", error=True)
    report(f"Working directory: {Path.cwd()}", error=True)
    report(f"Project root: {PROJECT_ROOT}", error=True)
    report(f"Local MCP configuration: {MCP_CONFIG_PATH}", error=True)
    if server_config_path is not None:
        report(f"External MCP configuration: {server_config_path}", error=True)
    if server_command is not None:
        report(f"External MCP command: {server_command}", error=True)


def load_mcp_dependencies() -> None:
    """Load the MCP SDK only after argparse has handled --help and --version."""

    global ClientSession, StdioServerParameters, stdio_client, streamable_http_client, types
    if ClientSession is not None:
        return
    module_location = "not imported"
    module_version = "not reported"
    try:
        import mcp as mcp_module

        module_location = str(getattr(mcp_module, "__file__", None) or "namespace package (no __file__)")
        module_version = str(getattr(mcp_module, "__version__", "not reported"))
        from mcp import ClientSession as client_session
        from mcp import types as mcp_types
        from mcp.client.stdio import StdioServerParameters as stdio_server_parameters
        from mcp.client.stdio import stdio_client as mcp_stdio_client
        from mcp.client.streamable_http import streamable_http_client as mcp_http_client
    except (ImportError, AttributeError) as error:
        raise RuntimeError(
            "Could not import the MCP Python SDK. Install or upgrade the 'mcp' package "
            "in the active virtual environment; it must provide ClientSession and the "
            "stdio and streamable_http clients. "
            f"Detected mcp module: {module_location}; version: {module_version}. "
            f"Import details: {error}. Install command: "
            f"\"{sys.executable}\" -m pip install -r \"{PROJECT_ROOT / 'requirements.txt'}\""
        ) from error
    ClientSession = client_session
    types = mcp_types
    StdioServerParameters = stdio_server_parameters
    stdio_client = mcp_stdio_client
    streamable_http_client = mcp_http_client


def load_requests_dependency() -> None:
    """Load requests only for the optional Ollama verification path."""

    global requests
    if requests is not None:
        return
    try:
        import requests as http_requests
    except ImportError as error:
        raise RuntimeError(
            "The optional --ollama verification requires the 'requests' package in the "
            "active virtual environment."
        ) from error
    requests = http_requests


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
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="list MCP tools and exit without calling Ollama",
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="save the result in a file in the active project directory",
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="also verify that Ollama requests and uses the MCP tool",
    )
    parser.add_argument(
        "--server-config",
        metavar="FILE",
        help="use a stdio MCP server defined by a JSON configuration file inside this project",
    )
    parser.add_argument(
        "--args",
        metavar="JSON",
        help="JSON object passed directly as the selected MCP tool's arguments",
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
    arguments = parser.parse_args()
    if arguments.list and arguments.ollama:
        parser.error("--ollama cannot be combined with --list")
    if arguments.server_config and arguments.ollama:
        parser.error("--ollama is currently available only with the local MCP server")
    if arguments.list and arguments.args:
        parser.error("--args cannot be combined with --list")
    if arguments.args:
        try:
            parsed_tool_arguments = json.loads(arguments.args)
        except json.JSONDecodeError as error:
            parser.error(f"--args must be a JSON object: {error.msg}")
        if not isinstance(parsed_tool_arguments, dict):
            parser.error("--args must be a JSON object")
        arguments.tool_arguments = parsed_tool_arguments
    else:
        arguments.tool_arguments = None
    return arguments


def resolve_server_config_path(filename: str) -> Path:
    """Resolve a server configuration path while keeping it inside this project."""

    candidate = Path(filename)
    config_path = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    try:
        config_path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"The MCP server configuration must be inside {PROJECT_ROOT}.") from error
    if not config_path.is_file():
        raise ValueError(f"MCP server configuration was not found: {config_path}")
    return config_path


def load_stdio_server_parameters(config_path: Path) -> Any:
    """Load one safe project-local stdio MCP server configuration."""

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read MCP server configuration {config_path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError("MCP server configuration must be a JSON object.")
    if config.get("transport") != "stdio":
        raise ValueError("MCP server configuration currently supports only transport 'stdio'.")
    command = config.get("command")
    raw_arguments = config.get("args", [])
    raw_cwd = config.get("cwd", ".")
    create_cwd = config.get("create_cwd", False)
    if not isinstance(command, str) or not command.strip():
        raise ValueError("MCP server configuration requires a non-empty command.")
    if not isinstance(raw_arguments, list) or not all(isinstance(value, str) for value in raw_arguments):
        raise ValueError("MCP server configuration field 'args' must be an array of strings.")
    if not isinstance(raw_cwd, str) or not raw_cwd.strip():
        raise ValueError("MCP server configuration field 'cwd' must be non-empty text.")
    if not isinstance(create_cwd, bool):
        raise ValueError("MCP server configuration field 'create_cwd' must be true or false.")

    cwd_candidate = Path(raw_cwd)
    cwd = cwd_candidate.resolve() if cwd_candidate.is_absolute() else (PROJECT_ROOT / cwd_candidate).resolve()
    try:
        cwd.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("MCP server configuration 'cwd' must be inside this project.") from error
    if not cwd.exists() and create_cwd:
        cwd.mkdir(parents=True, exist_ok=True)
        report(f"Created MCP server working directory: {cwd}")
    if not cwd.is_dir():
        raise ValueError(f"MCP server configuration working directory does not exist: {cwd}")
    return StdioServerParameters(command=command, args=raw_arguments, cwd=cwd)


def resolve_output_file(filename: str, project_directory: Path) -> Path:
    """Resolve an output file directly inside the active project directory."""

    resolved_directory = project_directory.resolve()
    candidate = Path(filename)
    output_path = candidate.resolve() if candidate.is_absolute() else (resolved_directory / candidate).resolve()
    try:
        output_path.relative_to(resolved_directory)
    except ValueError as error:
        raise ValueError(f"The output file must be inside {resolved_directory}.") from error
    if output_path.parent != resolved_directory:
        raise ValueError(f"The output file must be directly in {resolved_directory}.")
    return output_path


def save_output(output_path: Path, content: str) -> None:
    """Save a CLI result using the project's UTF-8-with-BOM text convention."""

    output_path.write_text(content, encoding="utf-8-sig")
    report(f"Output saved to: {output_path}")


def record_mcp_answer(
    *,
    project_directory: Path,
    selector: str,
    model: str,
    function_name: str,
    endpoint: str,
    arguments: dict[str, object],
    answer: str,
    output_path: Path | None,
) -> bool:
    """Record one completed MCP integration test in the shared task database."""

    try:
        from lib.wrapp_db import (
            DEFAULT_TASKS_DATABASE_PATH,
            DEFAULT_TASKS_SCHEMA_PATH,
            record_task_output,
        )

        parameters: dict[str, object] = {
            "mcp_endpoint": endpoint,
            "mcp_function": function_name,
            "mcp_arguments": arguments,
        }
        if output_path is not None:
            parameters["output_file"] = str(output_path.relative_to(project_directory))
        uid = record_task_output(
            PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH,
            PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
            project=str(project_directory.resolve().relative_to(PROJECT_ROOT.resolve())),
            selector=selector,
            task=f"mcp/{function_name}",
            model=model,
            parameters=parameters,
            prompt=f"Call MCP {function_name} with {json.dumps(arguments, ensure_ascii=False)}.",
            instruction="End-to-end MCP and Ollama tool-calling test.",
            answer=answer,
        )
    except (OSError, ValueError) as error:
        report(f"ERROR: Completed MCP test could not be recorded in data/tasks.db: {error}", error=True)
        return False
    report(f"Task recorded in data/tasks.db: {uid}")
    return True


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
        error_text = " ".join(
            item.text
            for item in getattr(result, "content", [])
            if isinstance(item, types.TextContent)
        )
        detail = f": {error_text}" if error_text else ""
        raise RuntimeError(f"The MCP {function_name} tool returned an error{detail}")
    for item in getattr(result, "content", []):
        if isinstance(item, types.TextContent):
            return item.text
    raise RuntimeError(f"The MCP {function_name} tool did not return text content.")


def format_exception_message(error: BaseException) -> str:
    """Flatten an exception group into a compact, user-facing error message."""

    nested_errors = getattr(error, "exceptions", None)
    if isinstance(nested_errors, tuple):
        messages = [format_exception_message(nested_error) for nested_error in nested_errors]
        return "; ".join(message for message in messages if message) or error.__class__.__name__
    return str(error) or error.__class__.__name__


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
        f"{tool.name!r}: {', '.join(str(name) for name in required)}. Use --args JSON."
    )


async def run_stdio_test(
    server_parameters: Any,
    server_config_path: Path,
    model: str,
    function_name: str,
    word: str,
    number_a: float,
    number_b: float,
    operation: str,
    *,
    list_tools_only: bool,
    provided_tool_arguments: dict[str, object] | None,
    output_path: Path | None,
    db_enabled: bool,
    db_selector: str,
    project_directory: Path,
) -> bool:
    """Run a direct MCP test against an external stdio server configuration."""

    config_label = str(server_config_path.relative_to(PROJECT_ROOT))
    endpoint = f"stdio configuration: {config_label}"
    if list_tools_only:
        report(f"MCP tool list from {config_label}.")
    else:
        report(f"MCP stdio tool test: {function_name} ({config_label}).")
    report(f"Starting stdio MCP server: {server_parameters.command}", debug=True)
    try:
        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                available_tools = ", ".join(tool.name for tool in tools_response.tools)
                report(f"MCP tools: {available_tools}", debug=True)
                if list_tools_only:
                    if tools_response.tools:
                        output_lines: list[str] = []
                        for tool in tools_response.tools:
                            description = tool.description or "No description."
                            report(f"{tool.name}: {description}")
                            output_lines.append(f"{tool.name}: {description}")
                    else:
                        report("No MCP tools are available.")
                        output_lines = ["No MCP tools are available."]
                    if output_path:
                        save_output(output_path, "\n".join(output_lines) + "\n")
                    return True

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
                tool_arguments = (
                    provided_tool_arguments
                    if provided_tool_arguments is not None
                    else build_tool_arguments(selected_tool, word, number_a, number_b, operation)
                )
                report(f"Calling MCP {function_name} with arguments: {tool_arguments}", debug=True)
                direct_result = get_text_result(
                    await session.call_tool(function_name, tool_arguments), function_name
                )
                report(f"MCP tool result: {direct_result}")
                if output_path:
                    save_output(output_path, direct_result)
                Terminal().g(direct_result)
                if db_enabled and not record_mcp_answer(
                    project_directory=project_directory,
                    selector=db_selector,
                    model=model,
                    function_name=function_name,
                    endpoint=endpoint,
                    arguments=tool_arguments,
                    answer=direct_result,
                    output_path=output_path,
                ):
                    return False
                report("MCP stdio tool test: PASSED")
                return True
    except Exception as error:
        report_error_context(
            "stdio MCP tool test",
            error,
            server_config_path=server_config_path,
            server_command=server_parameters.command,
        )
        return False


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
        f"(timeout {api.read_timeout_seconds:g} s)...",
        debug=True,
    )
    next_normal_progress_seconds = 60
    while True:
        try:
            response = await asyncio.wait_for(asyncio.shield(request_task), timeout=15)
        except TimeoutError:
            elapsed_seconds = time.monotonic() - started_at
            if REPORT_DEBUG_ENABLED or elapsed_seconds >= next_normal_progress_seconds:
                report(
                    f"{stage}: still waiting after {elapsed_seconds:.0f} s "
                    f"(timeout {api.read_timeout_seconds:g} s)."
                )
                next_normal_progress_seconds += 60
            continue
        elapsed_seconds = time.monotonic() - started_at
        report(f"{stage}: Ollama response received in {elapsed_seconds:.1f} s.", debug=True)
        return response


async def run_test(
    config: dict[str, object],
    model: str,
    function_name: str,
    word: str,
    number_a: float,
    number_b: float,
    operation: str,
    *,
    list_tools_only: bool = False,
    verify_with_ollama: bool = False,
    provided_tool_arguments: dict[str, object] | None = None,
    output_path: Path | None = None,
    db_enabled: bool = False,
    db_selector: str = "",
    project_directory: Path | None = None,
) -> bool:
    """Run an MCP tool test, optionally followed by an Ollama tool-call test."""

    host, port, path = config.get("host"), config.get("port"), config.get("path")
    if not isinstance(host, str) or not isinstance(port, int) or not isinstance(path, str):
        raise ValueError("MCP configuration requires host, port, and path.")

    endpoint = f"http://{host}:{port}{path}"
    if list_tools_only:
        report("MCP tool list.")
    elif verify_with_ollama:
        report(f"MCP and Ollama integration test: {function_name} with {model}.")
    else:
        report(f"MCP tool test: {function_name}.")
    report(f"MCP configuration: {MCP_CONFIG_PATH}", debug=True)
    report(f"MCP endpoint: {endpoint}", debug=True)
    report(f"MCP function: {function_name}", debug=True)
    report(f"Ollama model: {model}", debug=True)
    if port_is_open(host, port):
        raise RuntimeError(
            f"Port {host}:{port} is already occupied. Stop the existing server "
            "or change the port in mcp/mcp_config.json."
        )
    report(f"Starting local MCP server: {SERVER_PATH}", debug=True)
    server = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        report(f"Waiting for MCP server on {host}:{port}...", debug=True)
        wait_for_port(host, port, server)
        report("MCP server port: ready", debug=True)
        report("Opening MCP HTTP session...", debug=True)
        async with streamable_http_client(endpoint) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                report("Sending MCP initialize request...", debug=True)
                await session.initialize()
                report("MCP handshake: OK", debug=True)

                report("Requesting MCP tool list...", debug=True)
                tools_response = await session.list_tools()
                available_tools = ", ".join(tool.name for tool in tools_response.tools)
                report(f"MCP tools: {available_tools}", debug=True)
                if list_tools_only:
                    if tools_response.tools:
                        output_lines: list[str] = []
                        for tool in tools_response.tools:
                            description = tool.description or "No description."
                            report(f"{tool.name}: {description}")
                            output_lines.append(f"{tool.name}: {description}")
                    else:
                        report("No MCP tools are available.")
                        output_lines = ["No MCP tools are available."]
                    if output_path:
                        save_output(output_path, "\n".join(output_lines) + "\n")
                    return True
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

                arguments = (
                    provided_tool_arguments
                    if provided_tool_arguments is not None
                    else build_tool_arguments(
                        selected_tool,
                        word,
                        number_a,
                        number_b,
                        operation,
                    )
                )
                report(f"Calling MCP {function_name} with arguments: {arguments}", debug=True)
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
                if output_path:
                    save_output(output_path, direct_result)
                if not verify_with_ollama:
                    Terminal().g(direct_result)
                    if db_enabled:
                        if project_directory is None:
                            raise RuntimeError("MCP database recording requires a project directory.")
                        if not record_mcp_answer(
                            project_directory=project_directory,
                            selector=db_selector,
                            model=model,
                            function_name=function_name,
                            endpoint=endpoint,
                            arguments=arguments,
                            answer=direct_result,
                            output_path=output_path,
                        ):
                            return False
                    report("MCP tool test: PASSED")
                    return True

                api = ollama_api(config_path=OLLAMA_CONFIG_PATH, debug_enabled=REPORT_DEBUG_ENABLED)
                report(f"Ollama response timeout: {api.read_timeout_seconds:g} s", debug=True)
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
                report("Sending MCP tool schema to Ollama /api/chat...", debug=True)
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
                report(f"Ollama requested {len(tool_calls)} tool call(s).", debug=True)

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
                    report(
                        f"Forwarding Ollama arguments to MCP {function_name}: {call_arguments}",
                        debug=True,
                    )
                    mcp_result = get_text_result(
                        await session.call_tool(function_name, call_arguments), function_name
                    )
                    report(f"MCP result returned to Ollama: {mcp_result}", debug=True)
                    messages.append(
                        {"role": "tool", "tool_name": function_name, "content": mcp_result}
                    )

                report("Sending MCP result back to Ollama /api/chat...", debug=True)
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
                Terminal().g(direct_result)
                if db_enabled:
                    if project_directory is None:
                        raise RuntimeError("MCP database recording requires a project directory.")
                    if not record_mcp_answer(
                        project_directory=project_directory,
                        selector=db_selector,
                        model=model,
                        function_name=function_name,
                        endpoint=endpoint,
                        arguments=arguments,
                        answer=direct_result,
                        output_path=output_path,
                    ):
                        return False
                report("MCP and Ollama tool-calling test: PASSED")
                return True
    finally:
        report("Stopping local MCP server...", debug=True)
        if server.poll() is None:
            server.terminate()
        try:
            server_stdout, server_stderr = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            report("MCP server did not stop in time; terminating it.", debug=True)
            server.kill()
            server_stdout, server_stderr = server.communicate()
        report("Local MCP server stopped.", debug=True)
        if server_stdout.strip():
            report(f"MCP server stdout:\n{server_stdout.strip()}", debug=True)
        if server_stderr.strip():
            report(f"MCP server stderr:\n{server_stderr.strip()}", debug=True)


def main() -> int:
    """Run the end-to-end MCP and Ollama tool-calling test."""

    global REPORT_DEBUG_ENABLED, REPORT_STARTED_AT
    server_config_path: Path | None = None
    startup_stage = "loading local MCP configuration"
    try:
        config = load_mcp_config()
        startup_stage = "parsing command-line arguments"
        arguments = parse_arguments(config)
        startup_stage = "loading the MCP Python SDK"
        load_mcp_dependencies()
        if arguments.ollama:
            startup_stage = "loading the optional Ollama HTTP dependency"
            load_requests_dependency()
        startup_stage = "loading the external MCP server configuration"
        server_config_path = (
            resolve_server_config_path(arguments.server_config) if arguments.server_config else None
        )
        server_parameters = (
            load_stdio_server_parameters(server_config_path) if server_config_path else None
        )
        startup_stage = "loading project configuration"
        project_config = load_project_config(PROJECT_ROOT)
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        output_path = (
            resolve_output_file(arguments.out, project_directory) if arguments.out else None
        )
        log_enabled = read_log_enabled(PROJECT_ROOT / "project.json")
        REPORT_DEBUG_ENABLED = read_debug_enabled(PROJECT_ROOT / "project.json") is True
        if arguments.list:
            db_enabled, db_selector = False, ""
        else:
            from lib.wrapp_db import read_db_enabled, read_db_selector

            db_enabled = read_db_enabled(project_config)
            db_selector = read_db_selector(project_config)
        REPORT_STARTED_AT = time.monotonic()
    except (OSError, RuntimeError, ValueError) as error:
        report_error_context(startup_stage, error, server_config_path=server_config_path)
        return 1

    with console_log(project_directory, "cli_mcp.py", log_enabled):
        try:
            if server_parameters and server_config_path:
                run_result = asyncio.run(
                    run_stdio_test(
                        server_parameters,
                        server_config_path,
                        arguments.model,
                        arguments.function,
                        arguments.word,
                        arguments.a,
                        arguments.b,
                        arguments.operation,
                        list_tools_only=arguments.list,
                        provided_tool_arguments=arguments.tool_arguments,
                        output_path=output_path,
                        db_enabled=db_enabled,
                        db_selector=db_selector,
                        project_directory=project_directory,
                    )
                )
            else:
                run_result = asyncio.run(
                    run_test(
                        config,
                        arguments.model,
                        arguments.function,
                        arguments.word,
                        arguments.a,
                        arguments.b,
                        arguments.operation,
                        list_tools_only=arguments.list,
                        verify_with_ollama=arguments.ollama,
                        provided_tool_arguments=arguments.tool_arguments,
                        output_path=output_path,
                        db_enabled=db_enabled,
                        db_selector=db_selector,
                        project_directory=project_directory,
                    )
                )
            return 0 if run_result else 1
        except (OSError, RuntimeError, ValueError) as error:
            report_error_context(
                "running the MCP command",
                error,
                server_config_path=server_config_path,
                server_command=server_parameters.command if server_parameters else None,
            )
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

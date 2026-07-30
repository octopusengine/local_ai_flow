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
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_project_config,
    read_debug_enabled,
    read_log_enabled,
)
from lib.wrapp_ollama import ollama_api
from lib.wrapp_terminal import Terminal
from lib.mcp_local import DEFAULT_LOCAL_TOOL_NAME, get_safe_test_arguments, load_local_mcp_config


PROJECT_ROOT = Path(__file__).resolve().parent
MCP_CONFIG_PATH = PROJECT_ROOT / "mcp" / "mcp_config.json"
SERVER_PATH = PROJECT_ROOT / "mcp" / "wrapp_mcp_server.py"
OLLAMA_CONFIG_PATH = PROJECT_ROOT / "lib" / "ollama.json"

REPORT_STARTED_AT = time.monotonic()
REPORT_DEBUG_ENABLED = False
REPORT_JSON_ENABLED = False
JSON_RESULT: dict[str, object] | None = None
LAST_ERROR: str | None = None
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
    print(
        f"{prefix}{message}",
        file=sys.stderr if error or REPORT_JSON_ENABLED else sys.stdout,
        flush=True,
    )


@dataclass(frozen=True)
class ToolTestResult:
    """One completed direct MCP tool call for human and JSON reporting."""

    tool: str
    arguments: dict[str, object]
    result: str
    duration_seconds: float

    def as_json(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "duration_seconds": round(self.duration_seconds, 3),
            "status": "passed",
        }


@dataclass(frozen=True)
class ExternalMcpServerConfig:
    """One project-local configuration for an external MCP server."""

    transport: str
    endpoint: str
    stdio_parameters: Any | None = None


def set_json_result(result: dict[str, object]) -> None:
    """Store the final machine-readable command result until main() emits it."""

    global JSON_RESULT
    JSON_RESULT = result


def emit_json_result(
    *,
    passed: bool,
    function_name: str,
    arguments: dict[str, object] | None,
    started_at: float,
) -> None:
    """Emit exactly one JSON document for the --json command mode."""

    if not REPORT_JSON_ENABLED:
        return
    result = JSON_RESULT or {
        "tool": function_name,
        "arguments": arguments,
        "result": None,
        "status": "passed" if passed else "failed",
    }
    result.setdefault("duration_seconds", round(time.monotonic() - started_at, 3))
    if not passed and LAST_ERROR:
        result.setdefault("error", LAST_ERROR)
    print(json.dumps(result, ensure_ascii=False), flush=True)


def report_error_context(
    stage: str,
    error: BaseException,
    *,
    server_config_path: Path | None = None,
    server_command: str | None = None,
) -> None:
    """Print concise, actionable diagnostics for a CLI failure."""

    global LAST_ERROR
    LAST_ERROR = format_exception_message(error)
    report(f"ERROR: cli_mcp.py failed during {stage}.", error=True)
    report(f"Reason: {LAST_ERROR}", error=True)
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

    return load_local_mcp_config(MCP_CONFIG_PATH)


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
        default=DEFAULT_LOCAL_TOOL_NAME,
        help=f"MCP function to test (default: {DEFAULT_LOCAL_TOOL_NAME})",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="list MCP tools and exit without calling Ollama",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="directly test every local MCP tool with built-in safe arguments",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="do not record a completed tool result in data/tasks.db",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="write one machine-readable JSON result to stdout",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        metavar="SECONDS",
        help="limit each MCP wait and each Ollama response to this many seconds",
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
    if arguments.all and arguments.list:
        parser.error("--all cannot be combined with --list")
    if arguments.all and arguments.ollama:
        parser.error("--all cannot be combined with --ollama")
    if arguments.all and arguments.server_config:
        parser.error("--all is currently available only with the local MCP server")
    if arguments.all and arguments.args:
        parser.error("--all cannot be combined with --args")
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
    if arguments.timeout is not None and arguments.timeout <= 0:
        parser.error("--timeout must be greater than zero")
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


def expand_project_root_placeholder(value: str) -> str:
    """Expand the portable project-root placeholder used by server configurations."""

    return value.replace("${PROJECT_ROOT}", str(PROJECT_ROOT.resolve()))


def load_external_server_config(config_path: Path) -> ExternalMcpServerConfig:
    """Load one project-local stdio or Streamable HTTP MCP configuration."""

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read MCP server configuration {config_path}: {error}") from error
    if not isinstance(config, dict):
        raise ValueError("MCP server configuration must be a JSON object.")
    transport = config.get("transport")
    if transport == "streamable-http":
        endpoint = config.get("url")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("Streamable HTTP MCP configuration requires a non-empty url.")
        parsed_endpoint = urlparse(endpoint)
        if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
            raise ValueError("Streamable HTTP MCP configuration url must be an absolute http or https URL.")
        if parsed_endpoint.fragment:
            raise ValueError("Streamable HTTP MCP configuration url must not contain a fragment.")
        return ExternalMcpServerConfig(transport=transport, endpoint=endpoint)
    if transport != "stdio":
        raise ValueError("MCP server configuration transport must be 'stdio' or 'streamable-http'.")
    command = config.get("command")
    raw_arguments = config.get("args", [])
    raw_cwd = config.get("cwd", ".")
    create_cwd = config.get("create_cwd", False)
    raw_environment = config.get("env", {})
    if not isinstance(command, str) or not command.strip():
        raise ValueError("MCP server configuration requires a non-empty command.")
    if not isinstance(raw_arguments, list) or not all(isinstance(value, str) for value in raw_arguments):
        raise ValueError("MCP server configuration field 'args' must be an array of strings.")
    if not isinstance(raw_cwd, str) or not raw_cwd.strip():
        raise ValueError("MCP server configuration field 'cwd' must be non-empty text.")
    if not isinstance(create_cwd, bool):
        raise ValueError("MCP server configuration field 'create_cwd' must be true or false.")
    if not isinstance(raw_environment, dict) or not all(
        isinstance(name, str) and name and isinstance(value, str)
        for name, value in raw_environment.items()
    ):
        raise ValueError("MCP server configuration field 'env' must be an object of non-empty string names and string values.")

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
    environment = {
        name: expand_project_root_placeholder(value) for name, value in raw_environment.items()
    }
    parameters = StdioServerParameters(command=command, args=raw_arguments, cwd=cwd, env=environment or None)
    return ExternalMcpServerConfig(
        transport=transport,
        endpoint=f"stdio configuration: {config_path.relative_to(PROJECT_ROOT)}",
        stdio_parameters=parameters,
    )


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


def build_safe_all_tool_arguments(tool: Any) -> dict[str, object]:
    """Return the explicitly declared safe arguments for one local --all tool."""

    tool_arguments = get_safe_test_arguments(tool.name)
    if tool_arguments is None:
        raise RuntimeError(
            f"Local MCP tool {tool.name!r} has no safe --all arguments in lib/mcp_local.py."
        )
    return tool_arguments


async def wait_for_mcp_response(
    awaitable: Any,
    *,
    timeout_seconds: float,
    stage: str,
) -> Any:
    """Await one MCP operation with a clear, user-selected timeout."""

    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError as error:
        raise RuntimeError(f"{stage} timed out after {timeout_seconds:g} s.") from error


def emit_direct_result(result: str) -> None:
    """Show a successful direct result unless stdout is reserved for JSON."""

    if not REPORT_JSON_ENABLED:
        Terminal().g(result)


async def run_external_session_test(
    connection: Any,
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
    mcp_timeout_seconds: float,
    endpoint: str,
    test_label: str,
    connection_detail: str,
    server_command: str | None = None,
) -> bool:
    """Run a direct MCP test through one external server connection."""

    config_label = str(server_config_path.relative_to(PROJECT_ROOT))
    if list_tools_only:
        report(f"MCP tool list from {config_label}.")
    else:
        report(f"{test_label}: {function_name} ({config_label}).")
    report(connection_detail, debug=True)
    try:
        async with connection as connection_streams:
            read_stream, write_stream = connection_streams[:2]
            async with ClientSession(read_stream, write_stream) as session:
                await wait_for_mcp_response(
                    session.initialize(),
                    timeout_seconds=mcp_timeout_seconds,
                    stage="MCP initialize request",
                )
                tools_response = await wait_for_mcp_response(
                    session.list_tools(),
                    timeout_seconds=mcp_timeout_seconds,
                    stage="MCP tool-list request",
                )
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
                    set_json_result(
                        {
                            "tool": "list",
                            "arguments": {},
                            "result": [
                                {
                                    "tool": tool.name,
                                    "description": tool.description or "No description.",
                                }
                                for tool in tools_response.tools
                            ],
                            "status": "passed",
                        }
                    )
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
                call_started_at = time.monotonic()
                direct_result = get_text_result(
                    await wait_for_mcp_response(
                        session.call_tool(function_name, tool_arguments),
                        timeout_seconds=mcp_timeout_seconds,
                        stage=f"MCP tool response for {function_name}",
                    ),
                    function_name,
                )
                report(f"MCP tool result: {direct_result}")
                if output_path:
                    save_output(output_path, direct_result)
                emit_direct_result(direct_result)
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
                set_json_result(
                    ToolTestResult(
                        tool=function_name,
                        arguments=tool_arguments,
                        result=direct_result,
                        duration_seconds=time.monotonic() - call_started_at,
                    ).as_json()
                )
                report(f"{test_label}: PASSED")
                return True
    except Exception as error:
        report_error_context(
            test_label.lower(),
            error,
            server_config_path=server_config_path,
            server_command=server_command,
        )
        return False


async def run_stdio_test(
    server_parameters: Any,
    server_config_path: Path,
    model: str,
    function_name: str,
    word: str,
    number_a: float,
    number_b: float,
    operation: str,
    **keywords: Any,
) -> bool:
    """Run a direct MCP test against an external stdio server configuration."""

    config_label = str(server_config_path.relative_to(PROJECT_ROOT))
    return await run_external_session_test(
        stdio_client(server_parameters),
        server_config_path,
        model,
        function_name,
        word,
        number_a,
        number_b,
        operation,
        endpoint=f"stdio configuration: {config_label}",
        test_label="MCP stdio tool test",
        connection_detail=f"Starting stdio MCP server: {server_parameters.command}",
        server_command=server_parameters.command,
        **keywords,
    )


async def run_remote_http_test(
    endpoint: str,
    server_config_path: Path,
    model: str,
    function_name: str,
    word: str,
    number_a: float,
    number_b: float,
    operation: str,
    **keywords: Any,
) -> bool:
    """Run a direct MCP test against an external Streamable HTTP endpoint."""

    return await run_external_session_test(
        streamable_http_client(endpoint),
        server_config_path,
        model,
        function_name,
        word,
        number_a,
        number_b,
        operation,
        endpoint=f"remote Streamable HTTP: {endpoint}",
        test_label="MCP remote HTTP tool test",
        connection_detail=f"Opening remote Streamable HTTP MCP endpoint: {endpoint}",
        **keywords,
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
    api: ollama_api,
    model: str,
    messages: list[dict[str, object]],
    tools: list[dict[str, object]] | None,
    timeout_seconds: float,
) -> dict[str, object]:
    """Call Ollama chat using the existing project's Ollama API configuration."""

    payload: dict[str, object] = {"model": model, "messages": messages, "stream": False}
    if tools is not None:
        payload["tools"] = tools
    response = requests.post(
        f"{api.base_url}/api/chat",
        json=payload,
        timeout=(min(10, timeout_seconds), timeout_seconds),
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
    timeout_seconds: float,
) -> dict[str, object]:
    """Call Ollama without leaving long-running requests silent in the progress log."""

    started_at = time.monotonic()
    request_task = asyncio.create_task(
        asyncio.to_thread(call_ollama_chat, api, model, messages, tools, timeout_seconds)
    )
    report(
        f"{stage}: request sent; waiting for Ollama "
        f"(timeout {timeout_seconds:g} s)...",
        debug=True,
    )
    next_normal_progress_seconds = 60
    while True:
        elapsed_seconds = time.monotonic() - started_at
        remaining_seconds = timeout_seconds - elapsed_seconds
        if remaining_seconds <= 0:
            request_task.cancel()
            raise RuntimeError(f"{stage} timed out after {timeout_seconds:g} s.")
        try:
            response = await asyncio.wait_for(
                asyncio.shield(request_task), timeout=min(15, remaining_seconds)
            )
        except TimeoutError:
            elapsed_seconds = time.monotonic() - started_at
            if elapsed_seconds >= timeout_seconds:
                request_task.cancel()
                raise RuntimeError(f"{stage} timed out after {timeout_seconds:g} s.")
            if REPORT_DEBUG_ENABLED or elapsed_seconds >= next_normal_progress_seconds:
                report(
                    f"{stage}: still waiting after {elapsed_seconds:.0f} s "
                    f"(timeout {timeout_seconds:g} s)."
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
    test_all_tools: bool = False,
    mcp_timeout_seconds: float = 15.0,
    ollama_timeout_seconds: float | None = None,
) -> bool:
    """Run an MCP tool test, optionally followed by an Ollama tool-call test."""

    host, port, path = config.get("host"), config.get("port"), config.get("path")
    if not isinstance(host, str) or not isinstance(port, int) or not isinstance(path, str):
        raise ValueError("MCP configuration requires host, port, and path.")

    endpoint = f"http://{host}:{port}{path}"
    if list_tools_only:
        report("MCP tool list.")
    elif test_all_tools:
        report("MCP direct test for all tools.")
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
        wait_for_port(host, port, server, timeout_seconds=mcp_timeout_seconds)
        report("MCP server port: ready", debug=True)
        report("Opening MCP HTTP session...", debug=True)
        async with streamable_http_client(endpoint) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                report("Sending MCP initialize request...", debug=True)
                await wait_for_mcp_response(
                    session.initialize(),
                    timeout_seconds=mcp_timeout_seconds,
                    stage="MCP initialize request",
                )
                report("MCP handshake: OK", debug=True)

                report("Requesting MCP tool list...", debug=True)
                tools_response = await wait_for_mcp_response(
                    session.list_tools(),
                    timeout_seconds=mcp_timeout_seconds,
                    stage="MCP tool-list request",
                )
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
                    set_json_result(
                        {
                            "tool": "list",
                            "arguments": {},
                            "result": [
                                {
                                    "tool": tool.name,
                                    "description": tool.description or "No description.",
                                }
                                for tool in tools_response.tools
                            ],
                            "status": "passed",
                        }
                    )
                    return True
                if test_all_tools:
                    tool_results: list[ToolTestResult] = []
                    for selected_tool in tools_response.tools:
                        tool_arguments = build_safe_all_tool_arguments(selected_tool)
                        report(
                            f"Calling MCP {selected_tool.name} with arguments: {tool_arguments}",
                            debug=True,
                        )
                        call_started_at = time.monotonic()
                        direct_result = get_text_result(
                            await wait_for_mcp_response(
                                session.call_tool(selected_tool.name, tool_arguments),
                                timeout_seconds=mcp_timeout_seconds,
                                stage=f"MCP tool response for {selected_tool.name}",
                            ),
                            selected_tool.name,
                        )
                        tool_result = ToolTestResult(
                            tool=selected_tool.name,
                            arguments=tool_arguments,
                            result=direct_result,
                            duration_seconds=time.monotonic() - call_started_at,
                        )
                        tool_results.append(tool_result)
                        report(f"MCP {selected_tool.name} result: {direct_result}")
                        emit_direct_result(direct_result)
                        if db_enabled:
                            if project_directory is None:
                                raise RuntimeError("MCP database recording requires a project directory.")
                            if not record_mcp_answer(
                                project_directory=project_directory,
                                selector=db_selector,
                                model=model,
                                function_name=selected_tool.name,
                                endpoint=endpoint,
                                arguments=tool_arguments,
                                answer=direct_result,
                                output_path=output_path,
                            ):
                                return False
                    if output_path:
                        save_output(
                            output_path,
                            "\n".join(
                                f"{tool_result.tool}: {tool_result.result}"
                                for tool_result in tool_results
                            ) + "\n",
                        )
                    set_json_result(
                        {
                            "tool": "all",
                            "arguments": {},
                            "result": [tool_result.as_json() for tool_result in tool_results],
                            "status": "passed",
                        }
                    )
                    report("MCP all-tools test: PASSED")
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
                call_started_at = time.monotonic()
                direct_result = get_text_result(
                    await wait_for_mcp_response(
                        session.call_tool(function_name, arguments),
                        timeout_seconds=mcp_timeout_seconds,
                        stage=f"MCP tool response for {function_name}",
                    ),
                    function_name,
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
                    emit_direct_result(direct_result)
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
                    set_json_result(
                        ToolTestResult(
                            tool=function_name,
                            arguments=arguments,
                            result=direct_result,
                            duration_seconds=time.monotonic() - call_started_at,
                        ).as_json()
                    )
                    report("MCP tool test: PASSED")
                    return True

                api = ollama_api(config_path=OLLAMA_CONFIG_PATH, debug_enabled=REPORT_DEBUG_ENABLED)
                effective_ollama_timeout = ollama_timeout_seconds or api.read_timeout_seconds
                report(f"Ollama response timeout: {effective_ollama_timeout:g} s", debug=True)
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
                        timeout_seconds=effective_ollama_timeout,
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
                        await wait_for_mcp_response(
                            session.call_tool(function_name, call_arguments),
                            timeout_seconds=mcp_timeout_seconds,
                            stage=f"MCP tool response for {function_name}",
                        ),
                        function_name,
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
                        timeout_seconds=effective_ollama_timeout,
                    )
                except (RuntimeError, requests.RequestException) as error:
                    report(f"ERROR: Ollama tool-calling test could not finish: {error}", error=True)
                    return False
                final_message = final_response.get("message")
                if not isinstance(final_message, dict) or not isinstance(final_message.get("content"), str):
                    raise RuntimeError("Ollama did not return final text after the MCP tool result.")
                report(f"Final model response: {final_message['content']}")
                emit_direct_result(direct_result)
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
                set_json_result(
                    ToolTestResult(
                        tool=function_name,
                        arguments=arguments,
                        result=direct_result,
                        duration_seconds=time.monotonic() - call_started_at,
                    ).as_json()
                )
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

    global LAST_ERROR, REPORT_DEBUG_ENABLED, REPORT_JSON_ENABLED, REPORT_STARTED_AT
    server_config_path: Path | None = None
    external_server_config: ExternalMcpServerConfig | None = None
    command_started_at = time.monotonic()
    startup_stage = "loading local MCP configuration"
    try:
        config = load_mcp_config()
        startup_stage = "parsing command-line arguments"
        arguments = parse_arguments(config)
        REPORT_JSON_ENABLED = arguments.json
        startup_stage = "loading the MCP Python SDK"
        load_mcp_dependencies()
        if arguments.ollama:
            startup_stage = "loading the optional Ollama HTTP dependency"
            load_requests_dependency()
        startup_stage = "loading the external MCP server configuration"
        server_config_path = (
            resolve_server_config_path(arguments.server_config) if arguments.server_config else None
        )
        external_server_config = (
            load_external_server_config(server_config_path) if server_config_path else None
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

            db_enabled = read_db_enabled(project_config) and not arguments.no_db
            db_selector = read_db_selector(project_config)
        mcp_timeout_seconds = arguments.timeout or 15.0
        REPORT_STARTED_AT = time.monotonic()
    except (OSError, RuntimeError, ValueError) as error:
        report_error_context(startup_stage, error, server_config_path=server_config_path)
        emit_json_result(
            passed=False,
            function_name="unknown",
            arguments=None,
            started_at=command_started_at,
        )
        return 1

    with console_log(project_directory, "cli_mcp.py", log_enabled):
        try:
            if external_server_config and server_config_path:
                if external_server_config.transport == "stdio":
                    if external_server_config.stdio_parameters is None:
                        raise RuntimeError("The stdio MCP configuration has no server parameters.")
                    run_result = asyncio.run(
                        run_stdio_test(
                            external_server_config.stdio_parameters,
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
                            mcp_timeout_seconds=mcp_timeout_seconds,
                        )
                    )
                else:
                    run_result = asyncio.run(
                        run_remote_http_test(
                            external_server_config.endpoint,
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
                            mcp_timeout_seconds=mcp_timeout_seconds,
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
                        test_all_tools=arguments.all,
                        mcp_timeout_seconds=mcp_timeout_seconds,
                        ollama_timeout_seconds=arguments.timeout,
                    )
                )
            emit_json_result(
                passed=run_result,
                function_name="all" if arguments.all else ("list" if arguments.list else arguments.function),
                arguments=arguments.tool_arguments,
                started_at=command_started_at,
            )
            return 0 if run_result else 1
        except (OSError, RuntimeError, ValueError) as error:
            report_error_context(
                "running the MCP command",
                error,
                server_config_path=server_config_path,
                server_command=(
                    external_server_config.stdio_parameters.command
                    if external_server_config and external_server_config.stdio_parameters is not None
                    else None
                ),
            )
            emit_json_result(
                passed=False,
                function_name="all" if arguments.all else arguments.function,
                arguments=arguments.tool_arguments,
                started_at=command_started_at,
            )
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

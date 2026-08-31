"""Reusable local Ollama agent engine and project-scoped file tools.

``assistant/tools`` intentionally contains only declarative tool data.  This
module binds that data to implementations that are constrained to one active
project directory, so both the CLI and a future Cowork UI use the same rules.
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import fnmatch
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import re
from typing import Callable, Iterable
from urllib.parse import urlparse
import threading

import requests

from lib.wrapp_ollama import INTEGER_OPTIONS, OPTION_NAMES, ollama_api


DEFAULT_MAX_STEPS = 24
DEFAULT_PYTHON_TIMEOUT_SECONDS = 30
MAX_PYTHON_TIMEOUT_SECONDS = 120
MAX_PYTHON_REPORT_CHARACTERS = 12_000
REVIEW_MAX_STEPS = 8
MAX_SEARCH_FILE_BYTES = 1_000_000
MAX_SEARCHED_FILES = 2_000
SEARCH_EXCLUDED_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", "node_modules"}
UNIFIED_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
LOCAL_WEB_HOSTS = {"127.0.0.1", "localhost", "::1"}
WEB_BROWSER_COMMANDS = ("msedge", "google-chrome", "chrome", "chromium", "chromium-browser", "firefox")
INCOMPLETE_FINAL_RE = re.compile(
    r"\b(?:napíšu|vytvořím|ověřím|spustím|přidám|upravím|implementuji|"
    r"i(?:'ll| will)|i need to|let me|next(?:,| i))\b",
    re.IGNORECASE,
)
AUTO_CONTINUE_PROMPT = (
    "Continue the task now. Your previous reply described unfinished work in the future. "
    "Do not return another plan: use the necessary tools, verify the result when practical, "
    "and give a final answer only after the requested work is complete."
)
REVIEW_SYSTEM_PROMPT = """You are a read-only reviewer for a local coding-agent run.
Inspect the supplied artifacts and the reported tool/test output. You may use
only the provided read-only tools. Never write files, apply patches, start
servers, run commands, or suggest that you performed a modification. Return a
concise verdict headed PASS, ISSUES, or INCONCLUSIVE, with concrete evidence
and next steps when needed."""
REVIEW_TOOL_NAMES = frozenset({"list_files", "read_file", "find_text", "file_info", "python_runtime_info", "web_runtime_info", "browser_test"})


def resolve_agent_options(default_options: dict[str, object], overrides: object) -> dict[str, int | float]:
    """Validate Code-specific Ollama overrides and merge them over common defaults."""
    if not isinstance(overrides, dict):
        raise ValueError("'options' must be a JSON object in cli_agent.json.")
    unknown = sorted(set(overrides).difference(OPTION_NAMES))
    if unknown:
        raise ValueError(f"Unsupported Code option(s) in cli_agent.json: {', '.join(unknown)}")
    parsed: dict[str, int | float] = {}
    for name, value in overrides.items():
        if name in INTEGER_OPTIONS:
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if not valid:
            raise ValueError(f"Code option '{name}' in cli_agent.json must be a number.")
        parsed[name] = value
    return dict(default_options) | parsed


class _QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Serve project files without mixing every HTTP request into agent output."""

    def log_message(self, _format: str, *_args: object) -> None:
        return


@dataclass
class _ProjectWebServer:
    directory: Path
    server: ThreadingHTTPServer
    thread: threading.Thread

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/"


_WEB_SERVERS: dict[int, _ProjectWebServer] = {}
_WEB_SERVERS_LOCK = threading.Lock()


def shutdown_web_servers() -> None:
    """Stop all local servers created by this agent process."""
    with _WEB_SERVERS_LOCK:
        running_servers = list(_WEB_SERVERS.values())
        _WEB_SERVERS.clear()
    for item in running_servers:
        item.server.shutdown()
        item.server.server_close()


atexit.register(shutdown_web_servers)


def _start_web_server(directory: Path, port: int) -> _ProjectWebServer:
    """Start or reuse one daemonized localhost server for a project directory."""
    with _WEB_SERVERS_LOCK:
        for item in _WEB_SERVERS.values():
            if item.directory == directory and (port == 0 or item.server.server_address[1] == port):
                return item
        if port and port in _WEB_SERVERS:
            raise ValueError(f"Localhost port {port} is already used by another agent project server.")
        handler = partial(_QuietHTTPRequestHandler, directory=str(directory))
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as error:
            raise ValueError(f"Could not start a localhost server: {error}") from error
        thread = threading.Thread(target=server.serve_forever, name="agent-project-server", daemon=True)
        item = _ProjectWebServer(directory, server, thread)
        _WEB_SERVERS[server.server_address[1]] = item
        thread.start()
        return item


def _registered_local_server(url: str) -> _ProjectWebServer:
    """Validate that a URL belongs to a server explicitly started by this agent."""
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as error:
        raise ValueError("browser_test URL must contain a valid localhost port.") from error
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_WEB_HOSTS or port is None:
        raise ValueError("browser_test accepts only an http://localhost URL returned by serve_project.")
    with _WEB_SERVERS_LOCK:
        server = _WEB_SERVERS.get(port)
    if server is None:
        raise ValueError("browser_test URL was not started by serve_project in this agent process.")
    return server


def _web_browser_paths() -> dict[str, str]:
    """Return PATH-visible and standard Windows browser paths without launching them."""
    found: dict[str, str] = {}
    for command in WEB_BROWSER_COMMANDS:
        path = shutil.which(command)
        if path:
            found[command] = path
    if os.name == "nt":
        windows_locations = {
            "msedge": ("Microsoft", "Edge", "Application", "msedge.exe"),
            "google-chrome": ("Google", "Chrome", "Application", "chrome.exe"),
        }
        roots = [Path(value) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if (value := os.environ.get(name))]
        for command, parts in windows_locations.items():
            if command in found:
                continue
            candidate = next((root.joinpath(*parts) for root in roots if root.joinpath(*parts).is_file()), None)
            if candidate is not None:
                found[command] = str(candidate)
    return found
SYSTEM_PROMPT = """You are a careful local coding agent.
Work only in the current project supplied by the file tools. Use the provided
tools to inspect, create, and verify files. Before overwriting an existing
file, read it first. Do not claim that a file or command succeeded unless its
tool result confirms it. A command result always includes an exit code.
For a request that asks for an artifact or program, do not stop at a plan or
say what you will do. Call the needed tools and finish the requested work
before giving the final answer.
Use ``find_text`` and line ranges in ``read_file`` to inspect an existing
project efficiently. Use ``file_info`` before reading an unfamiliar or large
file. Prefer ``apply_patch`` for a small edit to an existing file; use
``write_file`` for new files or deliberate full replacements.

The user will often ask you to build a small playable game. For such requests,
create the game files in the current project, explain how to start the game,
and run a lightweight verification step when practical. If that verification
returns a non-zero exit code, an exception, or output indicating an error,
inspect the relevant file, improve it, and run the verification again. Stop
only after it succeeds, the user declines a command, or the step limit is
reached. Keep your final answer concise and state which files you created or
changed. To verify an interactive program, use the optional ``stdin`` argument
of ``run_command`` with safe sample values instead of waiting for manual input.
Before compiling C, C++, or Rust, call ``toolchain_info`` and use a compiler it
reports as available. Do not install packages or toolchains unless the user
explicitly asks for it.

For Python projects, call ``python_runtime_info`` before relying on third-party
packages such as pygame. Use ``run_python`` to prefer the project's existing
``.venv`` or ``venv``. Do not create virtual environments or run pip commands:
the user manages those manually in this first version.

When the user asks about the active Code session or requests runtime details
for the final report, call ``session_info`` before answering.

For a local HTML or JavaScript project, call ``web_runtime_info`` before
assuming Node.js or a browser is available. ``serve_project`` starts only a
project-local localhost server; ``browser_test`` may inspect only that server's
rendered DOM and must never submit a form or visit an external URL.
"""


class ToolPolicy(str, Enum):
    """Approval policy for tools which can change the active project."""

    OBSERVE = "observe"
    DRAFT = "draft"
    CODE = "code"


class ProjectToolScope:
    """Resolve file paths safely below one project directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError(f"Project directory does not exist: {self.root}")

    def resolve(self, path: str) -> Path:
        """Return a project-relative path, refusing absolute and escaping paths."""
        candidate = Path(path)
        if candidate.is_absolute():
            raise ValueError("Absolute paths are not allowed.")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise ValueError("Path must stay inside the active project.") from error
        return resolved

    def display_path(self, path: Path) -> str:
        """Return the stable project-relative representation of a resolved path."""
        return path.relative_to(self.root).as_posix() or "."


Confirm = Callable[[str], bool]
ToolFunction = Callable[..., str]


@dataclass(frozen=True)
class AgentTool:
    """One model-visible tool and its local implementation."""

    name: str
    function: ToolFunction
    safety: str


@dataclass
class AgentToolCall:
    """A compact record of a single tool call in an agent run."""

    step: int
    name: str
    arguments: dict[str, object]
    status: str
    result: str


@dataclass
class AgentRun:
    """In-memory record of one request and the model's tool activity."""

    model: str
    project_directory: Path
    policy: ToolPolicy
    prompt: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    status: str = "running"
    tool_calls: list[AgentToolCall] = field(default_factory=list)
    artifacts: set[str] = field(default_factory=set)
    final_answer: str | None = None
    review: str | None = None
    review_error: str | None = None
    error: str | None = None
    duration_seconds: float | None = None

    def summary(self) -> str:
        """Return a short, human-readable report suitable for a UI."""
        lines = [
            "AGENT RUN REPORT",
            f"Model: {self.model}",
            f"Project: {self.project_directory}",
            f"Policy: {self.policy.value}",
            f"Status: {self.status}",
            f"Tools: {len(self.tool_calls)} call(s)",
        ]
        if self.artifacts:
            lines.append("Artifacts: " + ", ".join(sorted(self.artifacts)))
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.review:
            lines.append("Review: completed")
        if self.review_error:
            lines.append(f"Review error: {self.review_error}")
        return "\n".join(lines)


def format_session_info(
    run: AgentRun,
    *,
    schema_profile: str,
    options: dict[str, int | float],
    max_steps: int,
    run_confirm: bool,
    auto_continue: bool,
    review_enabled: bool,
) -> str:
    """Return live, non-sensitive metadata that a model can cite in its final reply."""
    elapsed = max(0.0, (datetime.now() - run.started_at).total_seconds())
    return "\n".join(
        [
            "SESSION INFO",
            f"Model: {run.model}",
            f"Project: {run.project_directory}",
            f"Tool policy: {run.policy.value}",
            f"Schema profile: {schema_profile}",
            f"Options: {json.dumps(options, ensure_ascii=False, sort_keys=True)}",
            f"Run confirmation: {run_confirm}",
            f"Auto continue: {auto_continue}",
            f"Reviewer enabled: {review_enabled}",
            f"Started: {run.started_at.astimezone().isoformat(timespec='seconds')}",
            f"Elapsed: {elapsed:.1f} s",
            f"Tool calls so far: {len(run.tool_calls)} / {max_steps} step limit",
        ]
    )


def database_tool_call(call: AgentToolCall) -> dict[str, object]:
    """Return a compact tool record without the full contents of written files."""
    arguments = dict(call.arguments)
    for field_name in ("content", "stdin", "patch"):
        field_value = arguments.pop(field_name, None)
        if isinstance(field_value, str):
            arguments[f"{field_name}_characters"] = len(field_value)
    return {
        "step": call.step,
        "name": call.name,
        "arguments": arguments,
        "status": call.status,
        "result_summary": call.result.replace("\r\n", "\n")[:1000],
    }


def record_agent_run(
    run: AgentRun,
    *,
    database_path: Path,
    schema_path: Path,
    project_root: Path,
    selector: str,
    instruction: str,
    run_confirm: bool,
    task: str = "cli_agent",
) -> int:
    """Store one completed run through the shared task-database contract."""
    if run.status != "completed" or run.final_answer is None:
        raise ValueError("Only completed agent runs with a final answer can be recorded.")
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError("Agent-run selector must be non-empty text.")
    if not isinstance(instruction, str):
        raise ValueError("Agent-run instruction must be text.")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("Agent-run task must be non-empty text.")
    from lib.wrapp_db import record_task_output

    try:
        project_label = str(run.project_directory.resolve().relative_to(project_root.resolve()))
    except ValueError as error:
        raise ValueError("Agent-run project must stay inside the project root.") from error
    duration = run.duration_seconds if run.duration_seconds is not None else 0.0
    parameters = {
        "agent_policy": run.policy.value,
        "status": run.status,
        "started_at": run.started_at.astimezone().isoformat(timespec="seconds"),
        "tool_calls": [database_tool_call(call) for call in run.tool_calls],
        "artifacts": sorted(run.artifacts),
        "review": run.review,
        "review_error": run.review_error,
        "run_confirm": run_confirm,
    }
    return record_task_output(
        database_path,
        schema_path,
        project=project_label,
        selector=selector,
        task=task,
        model=run.model,
        parameters=parameters,
        prompt=run.prompt,
        instruction=instruction,
        answer=run.final_answer,
        key1=f"{duration:.1f}",
    )


@dataclass
class AgentCallbacks:
    """Optional presentation hooks; the engine never writes to the terminal."""

    on_status: Callable[[str], None] | None = None
    on_thinking: Callable[[str], None] | None = None
    on_content: Callable[[str], None] | None = None
    on_tool_call: Callable[[str, dict[str, object]], None] | None = None
    on_tool_result: Callable[[str, str], None] | None = None


def load_tool_schema(path: Path, profile: str = "extended") -> list[dict[str, object]]:
    """Load one named profile from the declarative Ollama tool schema file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Cannot read tool schema {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Tool schema is not valid JSON: {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Tool schema must contain a JSON object: {path}")
    tools = data.get("tools")
    profiles = data.get("profiles")
    if not isinstance(tools, dict) or not tools:
        raise ValueError(f"Tool schema requires a non-empty 'tools' object: {path}")
    if not isinstance(profiles, dict):
        raise ValueError(f"Tool schema requires a 'profiles' object: {path}")
    names = profiles.get(profile)
    if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
        raise ValueError(f"Tool schema profile '{profile}' must contain a non-empty name list: {path}")

    selected: list[dict[str, object]] = []
    unknown = [name for name in names if name not in tools]
    if unknown:
        raise ValueError(f"Tool schema profile '{profile}' references unknown tool(s): {', '.join(unknown)}")
    for name in names:
        tool = tools[name]
        if not isinstance(tool, dict) or not isinstance(tool.get("function"), dict):
            raise ValueError(f"Tool schema tool '{name}' must contain a function object.")
        function = tool["function"]
        if function.get("name") != name:
            raise ValueError(f"Tool schema tool '{name}' must have the same function name.")
        selected.append(tool)
    return selected


def schema_tool_names(schema: Iterable[dict[str, object]]) -> set[str]:
    """Extract names from a validated Ollama tool schema."""
    names: set[str] = set()
    for tool in schema:
        function = tool.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            raise ValueError("Every tool schema function must have a string name.")
        names.add(function["name"])
    return names


def tools_for_schema(schema: Iterable[dict[str, object]], available_tools: dict[str, AgentTool]) -> dict[str, AgentTool]:
    """Select exactly the implementations exposed by one declarative tool schema."""
    names = schema_tool_names(schema)
    missing = sorted(names.difference(available_tools))
    if missing:
        raise ValueError(f"Tool schema references unavailable implementation(s): {', '.join(missing)}")
    return {name: available_tools[name] for name in names}


def _confirm_or_decline(confirm: Confirm, message: str) -> bool:
    try:
        return bool(confirm(message))
    except (EOFError, KeyboardInterrupt):
        return False


def apply_unified_patch(original: str, patch: str) -> str:
    """Apply standard unified-diff hunks, rejecting stale or malformed context."""
    if not isinstance(patch, str) or not patch.strip():
        raise ValueError("Patch must be non-empty text.")
    original_lines = original.splitlines()
    patch_lines = patch.splitlines()
    output: list[str] = []
    source_index = 0
    index = 0
    applied_hunks = 0
    while index < len(patch_lines):
        line = patch_lines[index]
        if line.startswith("--- ") or line.startswith("+++ ") or line == "\\ No newline at end of file":
            index += 1
            continue
        match = UNIFIED_HUNK_RE.match(line)
        if match is None:
            raise ValueError(f"Expected a unified-diff hunk header, got: {line!r}")
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_count = int(match.group(4) or "1")
        hunk_source_index = 0 if old_start == 0 else old_start - 1
        if hunk_source_index < source_index or hunk_source_index > len(original_lines):
            raise ValueError("Patch hunk location is outside the source file or overlaps a previous hunk.")
        output.extend(original_lines[source_index:hunk_source_index])
        source_index = hunk_source_index
        index += 1
        old_seen = 0
        new_seen = 0
        while index < len(patch_lines) and not patch_lines[index].startswith("@@ "):
            body_line = patch_lines[index]
            if body_line == "\\ No newline at end of file":
                index += 1
                continue
            if not body_line or body_line[0] not in {" ", "+", "-"}:
                raise ValueError(f"Invalid unified-diff line: {body_line!r}")
            operation, value = body_line[0], body_line[1:]
            if operation in {" ", "-"}:
                if source_index >= len(original_lines) or original_lines[source_index] != value:
                    raise ValueError("Patch context does not match the current file.")
                source_index += 1
                old_seen += 1
            if operation in {" ", "+"}:
                output.append(value)
                new_seen += 1
            index += 1
        if old_seen != old_count or new_seen != new_count:
            raise ValueError("Patch hunk line counts do not match its header.")
        applied_hunks += 1
    if not applied_hunks:
        raise ValueError("Patch contains no unified-diff hunks.")
    output.extend(original_lines[source_index:])
    rendered = "\n".join(output)
    return rendered + ("\n" if original.endswith("\n") and rendered else "")


def build_file_tools(
    scope: ProjectToolScope,
    policy: ToolPolicy = ToolPolicy.CODE,
    *,
    confirm: Confirm | None = None,
    run_confirm: Confirm | None = None,
    on_artifact: Callable[[str], None] | None = None,
    session_info_provider: Callable[[], str] | None = None,
) -> dict[str, AgentTool]:
    """Create project-scoped implementations for the tools in ``tool_schema.json``."""
    ask = confirm or (lambda message: input(f"{message} [y/N] ").strip().lower() == "y")
    ask_run = run_confirm or ask

    def list_files(path: str = ".") -> str:
        directory = scope.resolve(path)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {scope.display_path(directory)}")
        entries = [entry.name + ("/" if entry.is_dir() else "") for entry in directory.iterdir()]
        return "\n".join(sorted(entries)) or "(empty directory)"

    def session_info() -> str:
        """Return live session metadata without reading or changing project files."""
        return session_info_provider() if session_info_provider is not None else "Session information is unavailable for this tool call."

    def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Read a complete UTF-8 file or an inclusive, one-based line range."""
        file_path = scope.resolve(path)
        if not file_path.is_file():
            raise ValueError(f"Not a file: {scope.display_path(file_path)}")
        if start_line is not None and (isinstance(start_line, bool) or not isinstance(start_line, int) or start_line < 1):
            raise ValueError("Tool argument 'start_line' must be a positive whole number.")
        if end_line is not None and (isinstance(end_line, bool) or not isinstance(end_line, int) or end_line < 1):
            raise ValueError("Tool argument 'end_line' must be a positive whole number.")
        if start_line is not None and end_line is not None and end_line < start_line:
            raise ValueError("'end_line' must not be before 'start_line'.")
        content = file_path.read_text(encoding="utf-8")
        if start_line is None and end_line is None:
            return content
        lines = content.splitlines(keepends=True)
        first = (start_line or 1) - 1
        last = end_line if end_line is not None else len(lines)
        if first >= len(lines):
            raise ValueError(f"Start line {first + 1} is beyond the end of {scope.display_path(file_path)}.")
        return "".join(lines[first:last])

    def find_text(
        query: str,
        path: str = ".",
        glob: str = "*",
        case_sensitive: bool = False,
        max_results: int = 50,
    ) -> str:
        """Search bounded project text files and return matching file-and-line locations."""
        if not isinstance(query, str) or not query:
            raise ValueError("Tool argument 'query' must be non-empty text.")
        if not isinstance(glob, str) or not glob or Path(glob).is_absolute() or ".." in Path(glob).parts:
            raise ValueError("Tool argument 'glob' must be a relative file pattern.")
        if not isinstance(case_sensitive, bool):
            raise ValueError("Tool argument 'case_sensitive' must be true or false.")
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 200:
            raise ValueError("Tool argument 'max_results' must be a whole number from 1 through 200.")
        search_path = scope.resolve(path)
        if not search_path.exists():
            raise ValueError(f"Search path does not exist: {scope.display_path(search_path)}")
        if not search_path.is_dir() and not search_path.is_file():
            raise ValueError(f"Search path is not a file or directory: {scope.display_path(search_path)}")

        def file_paths() -> Iterable[Path]:
            if search_path.is_file():
                yield search_path
                return
            scanned = 0
            for directory_name, directory_names, filenames in os.walk(search_path, followlinks=False):
                directory_names[:] = [name for name in directory_names if name not in SEARCH_EXCLUDED_DIRECTORIES]
                for filename in filenames:
                    scanned += 1
                    if scanned > MAX_SEARCHED_FILES:
                        return
                    candidate = Path(directory_name, filename)
                    try:
                        resolved = candidate.resolve()
                        resolved.relative_to(scope.root)
                        relative = resolved.relative_to(search_path)
                    except ValueError:
                        continue
                    if fnmatch.fnmatch(relative.as_posix(), glob) or fnmatch.fnmatch(resolved.name, glob):
                        yield resolved

        needle = query if case_sensitive else query.casefold()
        matches: list[str] = []
        skipped_large = 0
        for file_path in file_paths():
            try:
                if file_path.stat().st_size > MAX_SEARCH_FILE_BYTES:
                    skipped_large += 1
                    continue
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            for line_number, line in enumerate(content.splitlines(), start=1):
                haystack = line if case_sensitive else line.casefold()
                if needle in haystack:
                    preview = line.strip()
                    if len(preview) > 300:
                        preview = preview[:297] + "..."
                    matches.append(f"{scope.display_path(file_path)}:{line_number}: {preview}")
                    if len(matches) >= max_results:
                        summary = f"{len(matches)} result(s); limit reached"
                        if skipped_large:
                            summary += f"; skipped {skipped_large} large file(s)"
                        return summary + "\n" + "\n".join(matches)
        if not matches:
            return "(no matches)"
        summary = f"{len(matches)} result(s)"
        if skipped_large:
            summary += f"; skipped {skipped_large} large file(s)"
        return summary + "\n" + "\n".join(matches)

    def file_info(path: str) -> str:
        """Return non-content metadata for one scoped file or directory."""
        target = scope.resolve(path)
        if not target.exists():
            raise ValueError(f"Path does not exist: {scope.display_path(target)}")
        stat = target.stat()
        kind = "directory" if target.is_dir() else "file" if target.is_file() else "other"
        lines = [
            f"Path: {scope.display_path(target)}",
            f"Type: {kind}",
            f"Size: {stat.st_size} bytes",
            f"Modified: {datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec='seconds')}",
        ]
        if target.is_file():
            lines.append(f"Extension: {target.suffix.casefold() or '(none)'}")
        elif target.is_dir():
            try:
                lines.append(f"Direct entries: {sum(1 for _ in target.iterdir())}")
            except OSError:
                lines.append("Direct entries: unavailable")
        return "\n".join(lines)

    def write_file(path: str, content: str) -> str:
        if policy is ToolPolicy.OBSERVE:
            return "The current observe policy does not allow writing files."
        file_path = scope.resolve(path)
        relative_path = scope.display_path(file_path)
        if policy is ToolPolicy.DRAFT and not _confirm_or_decline(ask, f"Write '{relative_path}'?"):
            return "The user declined to write this file."
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        if on_artifact is not None:
            on_artifact(relative_path)
        return f"Saved {relative_path} ({len(content)} characters)"

    def apply_patch(path: str, patch: str) -> str:
        """Apply a verified small unified diff to an existing UTF-8 project file."""
        if policy is ToolPolicy.OBSERVE:
            return "The current observe policy does not allow modifying files."
        file_path = scope.resolve(path)
        if not file_path.is_file():
            raise ValueError(f"Not a file: {scope.display_path(file_path)}")
        relative_path = scope.display_path(file_path)
        if policy is ToolPolicy.DRAFT and not _confirm_or_decline(ask, f"Apply patch to '{relative_path}'?"):
            return "The user declined to apply this patch."
        original = file_path.read_text(encoding="utf-8")
        updated = apply_unified_patch(original, patch)
        if updated == original:
            return f"No changes applied to {relative_path}."
        file_path.write_text(updated, encoding="utf-8")
        if on_artifact is not None:
            on_artifact(relative_path)
        return f"Patched {relative_path} ({len(updated)} characters)"

    def run_command(command: str, stdin: str | None = None) -> str:
        """Run a project-local shell command, optionally supplying text on stdin."""
        if policy is ToolPolicy.OBSERVE:
            return "The current observe policy does not allow running commands."
        if stdin is not None and not isinstance(stdin, str):
            raise ValueError("Tool argument 'stdin' must be text or null.")
        suffix = " with supplied stdin" if stdin is not None else ""
        if not _confirm_or_decline(ask_run, f"Run '{command}'{suffix}?"):
            return "The user declined to run this command."
        result = subprocess.run(
            command,
            shell=True,
            cwd=scope.root,
            capture_output=True,
            text=True,
            input=stdin,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        status = f"(exit code {result.returncode})"
        return f"{output}\n{status}" if output else status

    def toolchain_info() -> str:
        """Report compiler commands visible in PATH without running or modifying them."""
        candidates = {
            "C": ("cc", "gcc", "clang", "cl"),
            "C++": ("c++", "g++", "clang++", "cl"),
            "Rust": ("rustc", "cargo"),
        }
        lines = [f"System: {platform.system()} {platform.release()}"]
        for language, commands in candidates.items():
            available = [f"{command}: {path}" for command in commands if (path := shutil.which(command))]
            lines.append(f"{language}: " + ("; ".join(available) if available else "not found in PATH"))
        lines.append("Note: Microsoft cl.exe may require a Visual Studio Developer Command Prompt.")
        return "\n".join(lines)

    def project_python() -> tuple[Path, str]:
        """Return the project virtual-environment interpreter, or this Python."""
        interpreter_location = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
        for environment_name in (".venv", "venv"):
            candidate = scope.root / environment_name / interpreter_location[0] / interpreter_location[1]
            if candidate.is_file():
                return candidate, environment_name
        return Path(sys.executable), "current Python"

    def python_runtime_info() -> str:
        """Report the selected interpreter and pygame metadata without installing anything."""
        interpreter, source = project_python()
        probe = (
            "from importlib.metadata import PackageNotFoundError, version; "
            "\ntry: print(version('pygame'))\nexcept PackageNotFoundError: print('not installed')"
        )
        try:
            result = subprocess.run(
                [str(interpreter), "-c", probe],
                cwd=scope.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            pygame_status = result.stdout.strip() if result.returncode == 0 else "could not query"
        except OSError as error:
            pygame_status = f"could not query ({error})"
        lines = [
            f"Interpreter: {interpreter}",
            f"Source: {source}",
            f"Python: {sys.version.split()[0] if source == 'current Python' else 'project environment'}",
            f"pygame: {pygame_status or 'not installed'}",
            "Virtual environments and packages are managed manually in this version.",
        ]
        return "\n".join(lines)

    def run_python(
        path: str,
        args: list[str] | None = None,
        stdin: str | None = None,
        timeout_seconds: int = DEFAULT_PYTHON_TIMEOUT_SECONDS,
    ) -> str:
        """Run one scoped Python file through the selected project interpreter."""
        if policy is ToolPolicy.OBSERVE:
            return "The current observe policy does not allow running programs."
        file_path = scope.resolve(path)
        if file_path.suffix.casefold() != ".py" or not file_path.is_file():
            raise ValueError(f"Python source file not found: {scope.display_path(file_path)}")
        if args is not None and (not isinstance(args, list) or not all(isinstance(value, str) for value in args)):
            raise ValueError("Tool argument 'args' must be an array of text values.")
        if stdin is not None and not isinstance(stdin, str):
            raise ValueError("Tool argument 'stdin' must be text or null.")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_PYTHON_TIMEOUT_SECONDS:
            raise ValueError(f"Tool argument 'timeout_seconds' must be a whole number from 1 through {MAX_PYTHON_TIMEOUT_SECONDS}.")
        interpreter, source = project_python()
        relative_path = scope.display_path(file_path)
        suffix = " with supplied stdin" if stdin is not None else ""
        if not _confirm_or_decline(ask_run, f"Run Python '{relative_path}' using {source}{suffix}?"):
            return "The user declined to run this Python program."
        command = [str(interpreter), relative_path, *(args or [])]
        try:
            result = subprocess.run(
                command,
                cwd=scope.root,
                capture_output=True,
                text=True,
                input=stdin,
                timeout=timeout_seconds,
            )
            outcome = "completed" if result.returncode == 0 else "failed"
            exit_code = str(result.returncode)
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            outcome = "timed out"
            exit_code = "unavailable"
            stdout = error.stdout or ""
            stderr = error.stderr or ""
        output = (str(stdout) + str(stderr)).strip()
        if len(output) > MAX_PYTHON_REPORT_CHARACTERS:
            output = output[:MAX_PYTHON_REPORT_CHARACTERS] + "\n[Python output truncated.]"
        lines = [
            "PYTHON RUN REPORT",
            f"Path: {relative_path}",
            f"Interpreter: {interpreter}",
            f"Source: {source}",
            f"Timeout: {timeout_seconds} s",
            f"Outcome: {outcome}",
            f"Exit code: {exit_code}",
        ]
        if output:
            lines.extend(["Output:", output])
        return "\n".join(lines)

    def web_runtime_info() -> str:
        """Report Node.js and PATH-visible browsers without launching them."""
        node_path = shutil.which("node")
        browsers = _web_browser_paths()
        lines = [f"Node.js: {node_path or 'not found in PATH'}"]
        if browsers:
            lines.append("Browsers: " + "; ".join(f"{name}: {path}" for name, path in browsers.items()))
        else:
            lines.append("Browsers: not found in PATH")
        lines.append("browser_test currently supports Chromium-family browsers (Edge, Chrome, or Chromium).")
        return "\n".join(lines)

    def serve_project(path: str = ".", port: int = 0) -> str:
        """Serve a scoped directory on a daemonized local HTTP server."""
        if policy is ToolPolicy.OBSERVE:
            return "The current observe policy does not allow starting a local server."
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("Tool argument 'port' must be a whole number from 0 through 65535.")
        directory = scope.resolve(path)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {scope.display_path(directory)}")
        relative_path = scope.display_path(directory)
        if not _confirm_or_decline(ask_run, f"Serve '{relative_path}' on localhost?"):
            return "The user declined to start a local server."
        server = _start_web_server(directory, port)
        return f"Serving {relative_path} at {server.url} (ends with the agent host process)"

    def browser_test(url: str, expected_text: str | None = None) -> str:
        """Inspect local rendered DOM text using a temporary headless Chromium profile."""
        if not isinstance(url, str) or not url:
            raise ValueError("Tool argument 'url' must be non-empty text.")
        if expected_text is not None and (not isinstance(expected_text, str) or not expected_text):
            raise ValueError("Tool argument 'expected_text' must be non-empty text or null.")
        _registered_local_server(url)
        browsers = _web_browser_paths()
        executable = next((browsers[name] for name in ("msedge", "google-chrome", "chrome", "chromium", "chromium-browser") if name in browsers), None)
        if executable is None:
            return "No supported Chromium-family browser was found in PATH; browser_test was not run."
        try:
            with tempfile.TemporaryDirectory(prefix="agent-browser-") as profile_directory:
                result = subprocess.run(
                    [
                        executable,
                        "--headless",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-networking",
                        "--host-resolver-rules=MAP * 0.0.0.0,EXCLUDE localhost,EXCLUDE 127.0.0.1",
                        f"--user-data-dir={profile_directory}",
                        "--dump-dom",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            return f"browser_test could not run: {error}"
        dom = result.stdout.strip()
        if result.returncode:
            detail = (result.stderr or dom).strip()
            return f"browser_test failed (exit code {result.returncode}): {detail[:1000]}"
        if expected_text is not None:
            if expected_text not in dom:
                return f"Rendered DOM did not contain expected text: {expected_text!r}"
            outcome = f"Rendered DOM contains expected text: {expected_text!r}"
        else:
            outcome = "Rendered DOM loaded successfully."
        preview = dom[:1500] + ("..." if len(dom) > 1500 else "")
        return f"{outcome}\nDOM characters: {len(dom)}\nDOM preview:\n{preview}"

    return {
        "session_info": AgentTool("session_info", session_info, "read"),
        "list_files": AgentTool("list_files", list_files, "read"),
        "read_file": AgentTool("read_file", read_file, "read"),
        "find_text": AgentTool("find_text", find_text, "read"),
        "file_info": AgentTool("file_info", file_info, "read"),
        "write_file": AgentTool("write_file", write_file, "write"),
        "apply_patch": AgentTool("apply_patch", apply_patch, "write"),
        "toolchain_info": AgentTool("toolchain_info", toolchain_info, "read"),
        "python_runtime_info": AgentTool("python_runtime_info", python_runtime_info, "read"),
        "run_python": AgentTool("run_python", run_python, "command"),
        "web_runtime_info": AgentTool("web_runtime_info", web_runtime_info, "read"),
        "serve_project": AgentTool("serve_project", serve_project, "command"),
        "browser_test": AgentTool("browser_test", browser_test, "read"),
        "run_command": AgentTool("run_command", run_command, "command"),
    }


class AgentEngine:
    """Run native Ollama chat/tool conversations without a CLI dependency."""

    def __init__(
        self,
        *,
        api: ollama_api,
        model: str,
        tool_schema: list[dict[str, object]],
        tools: dict[str, AgentTool],
        max_steps: int = DEFAULT_MAX_STEPS,
        timeout_seconds: float,
        options: dict[str, int | float] | None = None,
        auto_continue: bool = False,
        verbose: bool = False,
        callbacks: AgentCallbacks | None = None,
        post: Callable[..., requests.Response] = requests.post,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be greater than zero")
        schema_names = schema_tool_names(tool_schema)
        if schema_names != set(tools):
            raise ValueError(
                "Tool schema and implementations differ: "
                f"schema={sorted(schema_names)}, implementation={sorted(tools)}"
            )
        self.api = api
        self.model = model
        self.tool_schema = tool_schema
        self.tools = tools
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.options = dict(api.default_options if options is None else options)
        self.auto_continue = auto_continue
        self.verbose = verbose
        self.callbacks = callbacks or AgentCallbacks()
        self._post = post

    def _status(self, text: str) -> None:
        if self.callbacks.on_status is not None:
            self.callbacks.on_status(text)

    def _call_ollama(self, messages: list[dict[str, object]]) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "tools": self.tool_schema,
            "stream": self.verbose,
            "options": self.options,
        }
        if self.verbose:
            payload["think"] = True
        self._status(f"Waiting for Ollama response (timeout {self.timeout_seconds:g} s)...")
        response = self._post(
            f"{self.api.base_url}/api/chat",
            json=payload,
            stream=self.verbose,
            timeout=(min(10, self.timeout_seconds), self.timeout_seconds),
        )
        if response.status_code == 404:
            raise RuntimeError("Ollama does not expose /api/chat. Update Ollama and use a tool-capable model.")
        response.raise_for_status()
        if self.verbose:
            return self._collect_streamed_response(response)
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Ollama chat response must be a JSON object.")
        return data

    def _collect_streamed_response(self, response: requests.Response) -> dict[str, object]:
        thinking_parts: list[str] = []
        content_parts: list[str] = []
        tool_calls: list[object] = []
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            try:
                chunk = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"Ollama returned an invalid streaming JSON chunk: {error}") from error
            if not isinstance(chunk, dict):
                raise RuntimeError("Ollama returned an invalid streaming response chunk.")
            message = chunk.get("message")
            if not isinstance(message, dict):
                continue
            thinking = message.get("thinking")
            if isinstance(thinking, str) and thinking:
                thinking_parts.append(thinking)
                if self.callbacks.on_thinking is not None:
                    self.callbacks.on_thinking(thinking)
            content = message.get("content")
            if isinstance(content, str) and content:
                content_parts.append(content)
                if self.callbacks.on_content is not None:
                    self.callbacks.on_content(content)
            chunk_tool_calls = message.get("tool_calls")
            if isinstance(chunk_tool_calls, list):
                tool_calls.extend(chunk_tool_calls)
        message: dict[str, object] = {"role": "assistant", "content": "".join(content_parts)}
        if thinking_parts:
            message["thinking"] = "".join(thinking_parts)
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {"message": message}

    def _run_tool(self, tool_call: object, step: int) -> tuple[str, dict[str, object], str]:
        if not isinstance(tool_call, dict):
            return "unknown", {}, "Error: invalid tool call returned by Ollama."
        function = tool_call.get("function")
        if not isinstance(function, dict):
            return "unknown", {}, "Error: tool call has no function object."
        name = function.get("name")
        arguments = function.get("arguments", {})
        if not isinstance(name, str) or name not in self.tools:
            return str(name or "unknown"), {}, f"Error: unknown tool {name!r}."
        if not isinstance(arguments, dict):
            return name, {}, "Error: tool arguments must be a JSON object."
        if self.callbacks.on_tool_call is not None:
            self.callbacks.on_tool_call(name, arguments)
        try:
            inspect.signature(self.tools[name].function).bind(**arguments)
            result = str(self.tools[name].function(**arguments))
        except Exception as error:
            result = f"Error: {error}"
        if self.callbacks.on_tool_result is not None:
            self.callbacks.on_tool_result(name, result)
        return name, arguments, result

    def run(self, messages: list[dict[str, object]], run: AgentRun) -> str:
        """Mutate ``messages`` with the conversation and complete one agent run."""
        started_at = time.monotonic()
        continuation_used = False
        try:
            for step in range(1, self.max_steps + 1):
                try:
                    response = self._call_ollama(messages)
                except requests.RequestException as error:
                    raise RuntimeError(f"Ollama request failed: {error}") from error
                message = response.get("message")
                if not isinstance(message, dict):
                    raise RuntimeError("Ollama did not return an assistant message.")
                messages.append(message)
                tool_calls = message.get("tool_calls")
                if not isinstance(tool_calls, list) or not tool_calls:
                    content = message.get("content")
                    if not isinstance(content, str):
                        raise RuntimeError("Ollama final message does not contain text.")
                    if self.auto_continue and not continuation_used and INCOMPLETE_FINAL_RE.search(content):
                        continuation_used = True
                        self._status("Agent described unfinished work; asking it to continue once.")
                        messages.append({"role": "user", "content": AUTO_CONTINUE_PROMPT})
                        continue
                    run.status = "completed"
                    run.final_answer = content
                    return content
                self._status(f"Agent requested {len(tool_calls)} tool call(s), step {step}/{self.max_steps}.")
                for tool_call in tool_calls:
                    name, arguments, result = self._run_tool(tool_call, step)
                    run.tool_calls.append(AgentToolCall(step, name, arguments, "completed", result))
                    messages.append({"role": "tool", "tool_name": name, "content": result})
            raise RuntimeError(f"Agent stopped after {self.max_steps} tool steps without a final response.")
        except Exception as error:
            run.status = "failed"
            run.error = str(error)
            raise
        finally:
            # ``run`` can be rendered or persisted by any caller, independently
            # of whether Ollama completed successfully.
            run.duration_seconds = time.monotonic() - started_at


def review_agent_run(
    run: AgentRun,
    *,
    api: ollama_api,
    model: str,
    scope: ProjectToolScope,
    timeout_seconds: float,
    options: dict[str, int | float],
) -> str:
    """Review one completed agent run with tools that cannot alter the project."""
    schema_path = Path(__file__).resolve().parent.parent / "assistant" / "tools" / "tool_schema.json"
    review_schema = [
        tool for tool in load_tool_schema(schema_path, "extended")
        if tool["function"]["name"] in REVIEW_TOOL_NAMES
    ]
    available_tools = build_file_tools(scope, ToolPolicy.OBSERVE)
    review_tools = tools_for_schema(review_schema, available_tools)
    evidence = []
    for call in run.tool_calls:
        result = call.result.replace("\r\n", "\n")[:2_000]
        evidence.append(f"- {call.name} (step {call.step}):\n{result}")
    prompt = "\n".join(
        [
            "Review this completed local coding-agent run.",
            f"Original request: {run.prompt}",
            "Artifacts: " + (", ".join(sorted(run.artifacts)) if run.artifacts else "(none reported)"),
            "Tool and test evidence:",
            "\n".join(evidence) if evidence else "(no tool calls)",
            "Inspect artifacts when useful. Do not change anything.",
        ]
    )
    review_run = AgentRun(model, scope.root, ToolPolicy.OBSERVE, prompt)
    engine = AgentEngine(
        api=api,
        model=model,
        tool_schema=review_schema,
        tools=review_tools,
        max_steps=REVIEW_MAX_STEPS,
        timeout_seconds=timeout_seconds,
        options=options,
        auto_continue=False,
        verbose=False,
    )
    return engine.run(
        [{"role": "system", "content": REVIEW_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        review_run,
    )

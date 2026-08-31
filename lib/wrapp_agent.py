"""Reusable local Ollama agent engine and project-scoped file tools.

``assistant/tools`` intentionally contains only declarative tool data.  This
module binds that data to implementations that are constrained to one active
project directory, so both the CLI and a future Cowork UI use the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import inspect
import json
from pathlib import Path
import subprocess
import time
from typing import Callable, Iterable

import requests

from lib.wrapp_ollama import ollama_api


DEFAULT_MAX_STEPS = 24
SYSTEM_PROMPT = """You are a careful local coding agent.
Work only in the current project supplied by the file tools. Use the provided
tools to inspect, create, and verify files. Before overwriting an existing
file, read it first. Do not claim that a file or command succeeded unless its
tool result confirms it. A command result always includes an exit code.

The user will often ask you to build a small playable game. For such requests,
create the game files in the current project, explain how to start the game,
and run a lightweight verification step when practical. If that verification
returns a non-zero exit code, an exception, or output indicating an error,
inspect the relevant file, improve it, and run the verification again. Stop
only after it succeeds, the user declines a command, or the step limit is
reached. Keep your final answer concise and state which files you created or
changed. To verify an interactive program, use the optional ``stdin`` argument
of ``run_command`` with safe sample values instead of waiting for manual input.
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
        return "\n".join(lines)


def database_tool_call(call: AgentToolCall) -> dict[str, object]:
    """Return a compact tool record without the full contents of written files."""
    arguments = dict(call.arguments)
    for field_name in ("content", "stdin"):
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


def load_tool_schema(path: Path) -> list[dict[str, object]]:
    """Load and minimally validate native Ollama tool definitions from JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Cannot read tool schema {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Tool schema is not valid JSON: {path}: {error}") from error
    if not isinstance(data, list) or not data:
        raise ValueError(f"Tool schema must contain a non-empty JSON array: {path}")
    for index, tool in enumerate(data, start=1):
        if not isinstance(tool, dict) or not isinstance(tool.get("function"), dict):
            raise ValueError(f"Tool schema item {index} must contain a function object.")
    return data


def schema_tool_names(schema: Iterable[dict[str, object]]) -> set[str]:
    """Extract names from a validated Ollama tool schema."""
    names: set[str] = set()
    for tool in schema:
        function = tool.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            raise ValueError("Every tool schema function must have a string name.")
        names.add(function["name"])
    return names


def _confirm_or_decline(confirm: Confirm, message: str) -> bool:
    try:
        return bool(confirm(message))
    except (EOFError, KeyboardInterrupt):
        return False


def build_file_tools(
    scope: ProjectToolScope,
    policy: ToolPolicy = ToolPolicy.CODE,
    *,
    confirm: Confirm | None = None,
    run_confirm: Confirm | None = None,
    on_artifact: Callable[[str], None] | None = None,
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

    def read_file(path: str) -> str:
        file_path = scope.resolve(path)
        if not file_path.is_file():
            raise ValueError(f"Not a file: {scope.display_path(file_path)}")
        return file_path.read_text(encoding="utf-8")

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

    return {
        "list_files": AgentTool("list_files", list_files, "read"),
        "read_file": AgentTool("read_file", read_file, "read"),
        "write_file": AgentTool("write_file", write_file, "write"),
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
            "options": self.api.default_options,
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

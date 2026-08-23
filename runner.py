r"""Run a simple text file containing project CLI commands in sequence.

The first version intentionally supports only commands in this form:

    python .\script.py argument

Each command is executed with the same Python interpreter that runs this file.
Shell commands and scripts outside the repository root are rejected.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_project_config,
    read_debug_enabled,
    read_log_enabled,
)
from lib.wrapp_ollama import MODEL_UNAVAILABLE_EXIT_CODE, ollama_api
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent
FLOWS_DIR = PROJECT_ROOT / "flows"
DEFAULT_FLOW_PATH = Path("flow_test.txt")
PYTHON_LAUNCHERS = {"py", "py.exe", "python", "python.exe", "python3", "python3.exe"}
FLOW_LOG_ENVIRONMENT_VARIABLE = "OLLAMA_FLOW_LOG"
FORCE_COLOR_ENVIRONMENT_VARIABLE = "FORCE_COLOR"
PYTHON_IO_ENCODING_ENVIRONMENT_VARIABLE = "PYTHONIOENCODING"
FLOW_VARIABLE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
TEXT_FLOW_VARIABLE_DECLARATION_PATTERN = re.compile(
    r"^\s*\$([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$"
)
TEXT_FLOW_VARIABLE_REFERENCE_PATTERN = re.compile(
    r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))"
)
TEXT_FLOW_IF_PATTERN = re.compile(r"^@if\s+(file_exists|file_not_empty)\(\s*(.+?)\s*\)$")
TEXT_FLOW_ELSE_PATTERN = re.compile(r"^@else$")
TEXT_FLOW_END_PATTERN = re.compile(r"^@end$")
TEXT_FLOW_FOR_PATTERN = re.compile(r"^@for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+\((.+)\)$")
TEXT_FLOW_FOR_BATCH_PATTERN = re.compile(r"^@for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+\$(?:\{batch\}|batch)$")
TEXT_FLOW_ENDFOR_PATTERN = re.compile(r"^@endfor$")
BATCH_LIST_FILENAME = "batch_list.txt"
FLOW_RUN_TIMESTAMP_VARIABLE = "run_timestamp"


class FlowError(ValueError):
    """Report an invalid flow file or command."""


@dataclass(frozen=True)
class FlowCommand:
    """Store one validated command from the flow file."""

    source_label: str
    display_arguments: tuple[str, ...]
    execution_arguments: tuple[str, ...]

    @property
    def display_text(self) -> str:
        """Return a readable command line for terminal output."""

        return subprocess.list2cmdline(self.display_arguments)


@dataclass(frozen=True)
class FlowCondition:
    """Store one safe, file-based branch condition."""

    kind: str
    path: Path

    @property
    def display_text(self) -> str:
        """Return a compact condition description for the flow log."""

        return f"{self.kind}({self.path.as_posix()!r})"


@dataclass(frozen=True)
class FlowBranch:
    """Store the two possible paths of a conditional JSON flow step."""

    source_label: str
    condition: FlowCondition
    then_steps: tuple["FlowNode", ...]
    else_steps: tuple["FlowNode", ...]


FlowNode = FlowCommand | FlowBranch


def parse_arguments() -> argparse.Namespace:
    """Read an optional flow path and the optional dry-run switch."""

    parser = argparse.ArgumentParser(
        description="Run validated local_ai_flow CLI commands from a text file."
    )
    parser.add_argument(
        "flow_file",
        nargs="?",
        type=Path,
        default=DEFAULT_FLOW_PATH,
        help="flow command file (default: flow.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print commands without executing them",
    )
    parser.add_argument(
        "--model",
        dest="model_override",
        metavar="MODEL",
        help="override the Ollama model for every cli_ollama.py command in this flow",
    )
    parser.add_argument(
        "--sc",
        dest="sc_overrides",
        action="append",
        metavar="NAME",
        help="append a slash command to every cli_ollama.py command in this flow",
    )
    return parser.parse_args()


def resolve_flow_path(configured_path: Path, project_directory: Path) -> Path:
    """Resolve a flow from the root, active project, or ``flows`` directory."""

    if configured_path.is_absolute():
        flow_path = configured_path
    else:
        flow_candidates = (
            PROJECT_ROOT / configured_path,
            project_directory / configured_path,
            FLOWS_DIR / configured_path,
        )
        flow_path = next(
            (candidate for candidate in flow_candidates if candidate.is_file()),
            PROJECT_ROOT / configured_path,
        )

    flow_path = flow_path.resolve()
    try:
        flow_path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise FlowError("The flow file must remain inside the repository.") from error
    if not flow_path.is_file():
        raise FlowError(
            f"Flow file does not exist in the repository root, active project directory, "
            f"or flows directory: "
            f"{configured_path}"
        )
    return flow_path


def split_command(line: str, flow_path: Path, line_number: int) -> list[str]:
    """Split one command while preserving Windows path backslashes."""

    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    lexer.escape = ""
    try:
        return list(lexer)
    except ValueError as error:
        raise FlowError(f"{flow_path.name}:{line_number}: {error}") from error


def expand_text_flow_variables(
    value: str,
    variables: dict[str, str],
    flow_path: Path,
    line_number: int,
) -> str:
    """Expand ``$name`` and ``${name}`` references without using a shell."""

    def replace_reference(match: re.Match[str]) -> str:
        variable_name = match.group(1) or match.group(2)
        if variable_name not in variables:
            raise FlowError(f"{flow_path.name}:{line_number}: unknown flow variable ${variable_name}")
        return variables[variable_name]

    expanded = TEXT_FLOW_VARIABLE_REFERENCE_PATTERN.sub(replace_reference, value)
    if "${" in expanded:
        raise FlowError(f"{flow_path.name}:{line_number}: invalid flow variable reference in {value!r}")
    return expanded


def validate_command(
    arguments: list[str],
    flow_path: Path,
    source_label: str,
) -> FlowCommand:
    """Allow only Python calls to root-level project ``*.py`` scripts."""

    location = f"{flow_path.name}:{source_label}"
    if len(arguments) < 2:
        raise FlowError(f"{location}: expected 'python cli_name.py [arguments]'")

    launcher = Path(arguments[0]).name.lower()
    if launcher not in PYTHON_LAUNCHERS:
        raise FlowError(f"{location}: only Python CLI commands are allowed")

    configured_script = Path(arguments[1])
    if configured_script.is_absolute():
        script_path = configured_script.resolve()
    else:
        script_path = (PROJECT_ROOT / configured_script).resolve()

    if script_path.parent != PROJECT_ROOT:
        raise FlowError(f"{location}: the CLI script must be in the repository root")
    if script_path.suffix.casefold() != ".py":
        raise FlowError(f"{location}: only root-level *.py scripts are allowed")
    if not script_path.is_file():
        raise FlowError(f"{location}: CLI script does not exist: {script_path.name}")

    display_arguments = (arguments[0], script_path.name, *arguments[2:])
    execution_arguments = (sys.executable, str(script_path), *arguments[2:])
    return FlowCommand(
        source_label=source_label,
        display_arguments=display_arguments,
        execution_arguments=execution_arguments,
    )


def normalize_json_argument(value: object, location: str) -> str:
    """Convert a safe JSON scalar to a CLI argument string."""

    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    raise FlowError(f"{location}: command arguments and matrix values must be strings or numbers")


def expand_json_template(template: str, variables: dict[str, str], location: str) -> str:
    """Replace ``{variable}`` placeholders and reject accidental typos."""

    def replace_placeholder(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        if variable_name not in variables:
            raise FlowError(f"{location}: unknown matrix variable {{{variable_name}}}")
        return variables[variable_name]

    expanded = FLOW_VARIABLE_PATTERN.sub(replace_placeholder, template)
    if "{" in expanded or "}" in expanded:
        raise FlowError(f"{location}: invalid matrix placeholder in {template!r}")
    return expanded


def load_json_command_step(
    step: object,
    flow_path: Path,
    location: str,
    run_timestamp: str,
) -> list[FlowCommand]:
    """Validate one runnable JSON step and expand its optional matrix."""

    if not isinstance(step, dict):
        raise FlowError(f"{flow_path.name}:{location}: step must be an object")
    unknown_step_keys = set(step) - {"run", "args", "matrix"}
    if unknown_step_keys:
        raise FlowError(
            f"{flow_path.name}:{location}: unknown key(s): {', '.join(sorted(unknown_step_keys))}"
        )
    script_name = step.get("run")
    raw_arguments = step.get("args", [])
    if not isinstance(script_name, str) or not script_name:
        raise FlowError(f"{flow_path.name}:{location}: \"run\" must be a script name")
    if not isinstance(raw_arguments, list):
        raise FlowError(f"{flow_path.name}:{location}: \"args\" must be an array")
    argument_templates = [
        normalize_json_argument(argument, f"{flow_path.name}:{location}")
        for argument in raw_arguments
    ]

    raw_matrix = step.get("matrix", {})
    if not isinstance(raw_matrix, dict):
        raise FlowError(f"{flow_path.name}:{location}: \"matrix\" must be an object")
    matrix_names = list(raw_matrix)
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in matrix_names):
        raise FlowError(f"{flow_path.name}:{location}: matrix variable names must be identifiers")
    if FLOW_RUN_TIMESTAMP_VARIABLE in matrix_names:
        raise FlowError(
            f"{flow_path.name}:{location}: \"{FLOW_RUN_TIMESTAMP_VARIABLE}\" is a reserved flow variable"
        )
    matrix_values: list[list[str]] = []
    for name in matrix_names:
        values = raw_matrix[name]
        if not isinstance(values, list) or not values:
            raise FlowError(f"{flow_path.name}:{location}: matrix value \"{name}\" must be a non-empty array")
        matrix_values.append(
            [normalize_json_argument(value, f"{flow_path.name}:{location}") for value in values]
        )

    used_variables = {
        match.group(1)
        for argument in argument_templates
        for match in FLOW_VARIABLE_PATTERN.finditer(argument)
    }
    unused_variables = set(matrix_names) - used_variables
    if unused_variables:
        raise FlowError(
            f"{flow_path.name}:{location}: unused matrix variable(s): {', '.join(sorted(unused_variables))}"
        )

    commands: list[FlowCommand] = []
    combinations = itertools.product(*matrix_values) if matrix_values else [()]
    for combination_number, combination in enumerate(combinations, start=1):
        variables = {
            FLOW_RUN_TIMESTAMP_VARIABLE: run_timestamp,
            **dict(zip(matrix_names, combination)),
        }
        arguments = [
            expand_json_template(argument, variables, f"{flow_path.name}:{location}")
            for argument in argument_templates
        ]
        item_label = location if not matrix_values else f"{location}, matrix item {combination_number}"
        commands.append(validate_command(["python", script_name, *arguments], flow_path, item_label))
    return commands


def load_json_v1_steps(flow_path: Path, steps: list[object], run_timestamp: str) -> list[FlowCommand]:
    """Load the original linear JSON-flow format."""

    commands: list[FlowCommand] = []
    for step_number, step in enumerate(steps, start=1):
        commands.extend(load_json_command_step(step, flow_path, f"step {step_number}", run_timestamp))
    return commands


def parse_flow_condition(value: object, flow_path: Path, location: str) -> FlowCondition:
    """Validate a deliberately small condition language for JSON flow version 2."""

    if not isinstance(value, dict) or len(value) != 1:
        raise FlowError(
            f"{flow_path.name}:{location}: \"if\" must contain exactly one file condition"
        )
    kind, raw_path = next(iter(value.items()))
    if kind not in {"file_exists", "file_not_empty"}:
        raise FlowError(
            f"{flow_path.name}:{location}: supported conditions are file_exists and file_not_empty"
        )
    if not isinstance(raw_path, str) or not raw_path:
        raise FlowError(f"{flow_path.name}:{location}: condition path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise FlowError(f"{flow_path.name}:{location}: condition path must be relative to the project directory")
    return FlowCondition(kind=kind, path=path)


def load_json_v2_steps(
    flow_path: Path,
    steps: list[object],
    run_timestamp: str,
    *,
    prefix: str = "step",
) -> list[FlowNode]:
    """Load conditional JSON steps while validating both branches before execution."""

    nodes: list[FlowNode] = []
    for step_number, step in enumerate(steps, start=1):
        location = f"{prefix} {step_number}"
        if not isinstance(step, dict):
            raise FlowError(f"{flow_path.name}:{location}: step must be an object")
        if "if" not in step:
            nodes.extend(load_json_command_step(step, flow_path, location, run_timestamp))
            continue

        unknown_step_keys = set(step) - {"if", "then", "else"}
        if unknown_step_keys:
            raise FlowError(
                f"{flow_path.name}:{location}: unknown branch key(s): {', '.join(sorted(unknown_step_keys))}"
            )
        condition = parse_flow_condition(step["if"], flow_path, location)
        raw_then_steps = step.get("then")
        raw_else_steps = step.get("else", [])
        if not isinstance(raw_then_steps, list) or not raw_then_steps:
            raise FlowError(f"{flow_path.name}:{location}: \"then\" must be a non-empty array")
        if not isinstance(raw_else_steps, list):
            raise FlowError(f"{flow_path.name}:{location}: \"else\" must be an array")
        nodes.append(
            FlowBranch(
                source_label=location,
                condition=condition,
                then_steps=tuple(
                    load_json_v2_steps(
                        flow_path, raw_then_steps, run_timestamp, prefix=f"{location}.then step"
                    )
                ),
                else_steps=tuple(
                    load_json_v2_steps(
                        flow_path, raw_else_steps, run_timestamp, prefix=f"{location}.else step"
                    )
                ),
            )
        )
    return nodes


def load_json_flow(flow_path: Path, run_timestamp: str) -> list[FlowNode]:
    """Load a structured flow, including version 2 conditional branches."""

    try:
        document = json.loads(flow_path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise FlowError(f"Could not read flow file {flow_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise FlowError(f"{flow_path.name}: invalid JSON: {error.msg} (line {error.lineno})") from error

    if not isinstance(document, dict):
        raise FlowError(f"{flow_path.name}: JSON flow must be an object")
    unknown_top_level_keys = set(document) - {"version", "steps"}
    if unknown_top_level_keys:
        raise FlowError(
            f"{flow_path.name}: unknown top-level key(s): {', '.join(sorted(unknown_top_level_keys))}"
        )
    version = document.get("version")
    if version not in {1, 2} or isinstance(version, bool):
        raise FlowError(f"{flow_path.name}: JSON flow requires \"version\": 1 or 2")
    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        raise FlowError(f"{flow_path.name}: \"steps\" must be a non-empty array")
    return (
        load_json_v1_steps(flow_path, steps, run_timestamp)
        if version == 1
        else load_json_v2_steps(flow_path, steps, run_timestamp)
    )


def strip_control_line_comment(line: str) -> str:
    """Strip a trailing '# comment' from an @if/@else/@end control line."""

    match = re.search(r"(?:^|\s)#", line)
    return (line[: match.start()] if match else line).strip()


def build_text_flow_condition(
    kind: str,
    raw_path: str,
    flow_path: Path,
    line_number: int,
) -> FlowCondition:
    """Validate an @if condition path the same way JSON flow conditions are validated."""

    if not raw_path:
        raise FlowError(f"{flow_path.name}:{line_number}: '@if' condition path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise FlowError(
            f"{flow_path.name}:{line_number}: '@if' condition path must be relative to the project directory"
        )
    return FlowCondition(kind=kind, path=path)


def parse_for_items(raw_items: str, flow_path: Path, line_number: int) -> list[str]:
    """Parse the comma-separated, double-quoted string list inside @for VAR in (...)."""

    items: list[str] = []
    position = 0
    length = len(raw_items)
    while position < length:
        while position < length and raw_items[position] in " \t,":
            position += 1
        if position >= length:
            break
        if raw_items[position] != '"':
            raise FlowError(
                f"{flow_path.name}:{line_number}: '@for' array items must be double-quoted strings"
            )
        end = raw_items.find('"', position + 1)
        if end == -1:
            raise FlowError(f"{flow_path.name}:{line_number}: unterminated string in '@for' array")
        items.append(raw_items[position + 1 : end])
        position = end + 1
    if not items:
        raise FlowError(f"{flow_path.name}:{line_number}: '@for' array must contain at least one quoted string")
    return items


def read_batch_list_items(project_directory: Path, flow_path: Path, line_number: int) -> list[str]:
    """Read SUBDIR/batch_list.txt (one item per line) for '@for VAR in $batch'."""

    batch_list_path = project_directory / BATCH_LIST_FILENAME
    try:
        text = batch_list_path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise FlowError(
            f"{flow_path.name}:{line_number}: could not read {batch_list_path} for '@for ... in $batch': "
            f"{error}. Run 'cli_tool.py --batch' first (typically in an earlier flow step, "
            "or as a separate flow invoked via 'python3 runner.py')."
        ) from error
    items = [line.strip() for line in text.splitlines() if line.strip()]
    if not items:
        raise FlowError(f"{flow_path.name}:{line_number}: {batch_list_path} is empty; nothing to iterate over")
    return items


def parse_text_flow_block(
    lines: list[str],
    start_index: int,
    flow_path: Path,
    variables: dict[str, str],
    project_directory: Path,
    *,
    terminators: frozenset[str],
) -> tuple[list[FlowNode], int, str | None]:
    """Parse statements until EOF or one of `terminators` ('@else', '@end', '@endfor').

    Returns the parsed nodes, the index of the terminating line (or len(lines)
    at end of file), and the matched terminator keyword (or None at EOF).
    """

    nodes: list[FlowNode] = []
    index = start_index
    while index < len(lines):
        line_number = index + 1
        line = lines[index]
        control_line = strip_control_line_comment(line)

        matched_terminator: str | None = None
        if TEXT_FLOW_END_PATTERN.fullmatch(control_line):
            matched_terminator = "@end"
        elif TEXT_FLOW_ELSE_PATTERN.fullmatch(control_line):
            matched_terminator = "@else"
        elif TEXT_FLOW_ENDFOR_PATTERN.fullmatch(control_line):
            matched_terminator = "@endfor"

        if matched_terminator is not None:
            if matched_terminator not in terminators:
                opener = "'@for'" if matched_terminator == "@endfor" else "'@if'"
                raise FlowError(
                    f"{flow_path.name}:{line_number}: '{matched_terminator}' without a matching {opener}"
                )
            return nodes, index, matched_terminator

        if_match = TEXT_FLOW_IF_PATTERN.fullmatch(control_line)
        if if_match is not None:
            kind, raw_path_argument = if_match.groups()
            path_tokens = split_command(raw_path_argument, flow_path, line_number)
            if len(path_tokens) != 1:
                raise FlowError(
                    f"{flow_path.name}:{line_number}: '@if' needs exactly one quoted path argument"
                )
            expanded_path = expand_text_flow_variables(path_tokens[0], variables, flow_path, line_number)
            condition = build_text_flow_condition(kind, expanded_path, flow_path, line_number)

            then_nodes, then_end_index, then_terminator = parse_text_flow_block(
                lines, index + 1, flow_path, variables, project_directory, terminators=frozenset({"@else", "@end"})
            )
            if then_terminator is None:
                raise FlowError(f"{flow_path.name}:{line_number}: '@if' is missing a matching '@end'")
            if not then_nodes:
                raise FlowError(f"{flow_path.name}:{line_number}: '@if' block must contain at least one command")

            if then_terminator == "@else":
                else_nodes, else_end_index, else_terminator = parse_text_flow_block(
                    lines, then_end_index + 1, flow_path, variables, project_directory, terminators=frozenset({"@end"})
                )
                if else_terminator is None:
                    raise FlowError(f"{flow_path.name}:{line_number}: '@if' is missing a matching '@end'")
                index = else_end_index + 1
            else:
                else_nodes = []
                index = then_end_index + 1

            nodes.append(
                FlowBranch(
                    source_label=f"line {line_number}",
                    condition=condition,
                    then_steps=tuple(then_nodes),
                    else_steps=tuple(else_nodes),
                )
            )
            continue

        for_match = TEXT_FLOW_FOR_PATTERN.fullmatch(control_line)
        for_batch_match = TEXT_FLOW_FOR_BATCH_PATTERN.fullmatch(control_line)
        if for_match is not None or for_batch_match is not None:
            if for_batch_match is not None:
                variable_name = for_batch_match.group(1)
                items = read_batch_list_items(project_directory, flow_path, line_number)
            else:
                variable_name, raw_items = for_match.groups()
                items = parse_for_items(raw_items, flow_path, line_number)
            if variable_name in variables:
                raise FlowError(
                    f"{flow_path.name}:{line_number}: flow variable ${variable_name} is already defined"
                )

            body_start_index = index + 1
            body_end_index = body_start_index
            for item_value in items:
                variables[variable_name] = item_value
                item_nodes, body_end_index, body_terminator = parse_text_flow_block(
                    lines, body_start_index, flow_path, variables, project_directory, terminators=frozenset({"@endfor"})
                )
                if body_terminator is None:
                    del variables[variable_name]
                    raise FlowError(f"{flow_path.name}:{line_number}: '@for' is missing a matching '@endfor'")
                if not item_nodes:
                    del variables[variable_name]
                    raise FlowError(
                        f"{flow_path.name}:{line_number}: '@for' block must contain at least one command"
                    )
                nodes.extend(item_nodes)
            del variables[variable_name]
            index = body_end_index + 1
            continue

        if control_line.startswith("@"):
            raise FlowError(
                f"{flow_path.name}:{line_number}: invalid flow control line: {line.strip()!r}; "
                "expected '@if file_exists(\"path\")', '@if file_not_empty(\"path\")', '@else', '@end', "
                "'@for VAR in (\"a\", \"b\")', '@for VAR in $batch', or '@endfor'"
            )

        arguments = split_command(line, flow_path, line_number)
        if not arguments:
            index += 1
            continue
        declaration = TEXT_FLOW_VARIABLE_DECLARATION_PATTERN.fullmatch(line)
        if declaration is not None:
            name, raw_value = declaration.groups()
            if name in variables:
                raise FlowError(f"{flow_path.name}:{line_number}: flow variable ${name} is already defined")
            value_tokens = split_command(raw_value, flow_path, line_number)
            if len(value_tokens) != 1:
                raise FlowError(
                    f"{flow_path.name}:{line_number}: flow variable ${name} needs exactly one quoted string value"
                )
            variables[name] = expand_text_flow_variables(value_tokens[0], variables, flow_path, line_number)
            index += 1
            continue
        expanded_arguments = [
            expand_text_flow_variables(argument, variables, flow_path, line_number)
            for argument in arguments
        ]
        nodes.append(validate_command(expanded_arguments, flow_path, f"line {line_number}"))
        index += 1

    return nodes, index, None


def load_text_flow(flow_path: Path, project_directory: Path) -> list[FlowNode]:
    """Load commands, safe string variables, @if/@else/@end, and @for/@endfor from a text flow."""

    try:
        lines = flow_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise FlowError(f"Could not read flow file {flow_path}: {error}") from error

    variables: dict[str, str] = {}
    nodes, _, _ = parse_text_flow_block(lines, 0, flow_path, variables, project_directory, terminators=frozenset())

    if not nodes:
        raise FlowError(f"Flow file contains no commands: {flow_path}")
    return nodes


def load_flow(flow_path: Path, project_directory: Path) -> list[FlowNode]:
    """Load either a legacy text flow or a structured JSON flow."""

    commands = (
        load_json_flow(flow_path, datetime.now().strftime("%y%m%d_%H%M"))
        if flow_path.suffix.casefold() == ".json"
        else load_text_flow(flow_path, project_directory)
    )
    if not commands:
        raise FlowError(f"Flow file contains no commands: {flow_path}")
    return commands


def iter_flow_commands(nodes: list[FlowNode] | tuple[FlowNode, ...]):
    """Yield every runnable command, including commands in both branch paths."""

    for node in nodes:
        if isinstance(node, FlowCommand):
            yield node
            continue
        yield from iter_flow_commands(node.then_steps)
        yield from iter_flow_commands(node.else_steps)


def get_initial_project_override(nodes: list[FlowNode]) -> str | None:
    """Return the project selected by the first CLI command, if it has one."""

    for index, command in enumerate(iter_flow_commands(nodes)):
        script_name = Path(command.execution_arguments[1]).name
        arguments = command.execution_arguments[2:]
        for argument_index, argument in enumerate(arguments):
            if argument.startswith("--project="):
                project_name = argument.removeprefix("--project=")
            elif argument == "--project":
                if argument_index + 1 >= len(arguments):
                    raise FlowError(f"{command.source_label}: --project requires a directory")
                project_name = arguments[argument_index + 1]
            else:
                continue

            if script_name != "cli_ollama.py":
                raise FlowError(f"{command.source_label}: --project is available only for cli_ollama.py")
            if index != 0:
                raise FlowError("--project must be in the first active flow command so logging uses that project")
            if not project_name:
                raise FlowError(f"{command.source_label}: --project requires a directory")
            return project_name
    return None


def get_option_value(arguments: tuple[str, ...], option: str) -> str | None:
    """Return an option's value from long CLI syntax, if it is present."""

    for index, argument in enumerate(arguments):
        if argument == option:
            return arguments[index + 1] if index + 1 < len(arguments) else None
        if argument.startswith(f"{option}="):
            return argument.removeprefix(f"{option}=")
    return None


def has_option(arguments: tuple[str, ...], option: str) -> bool:
    """Return whether long CLI syntax contains an option with or without a value."""

    return any(argument == option or argument.startswith(f"{option}=") for argument in arguments)


def materialize_random_seed(command: FlowCommand) -> FlowCommand:
    """Replace ``--seed_rnd`` with the one concrete seed used by a flow step."""

    if Path(command.execution_arguments[1]).name != "cli_ollama.py":
        return command

    arguments = command.execution_arguments[2:]
    if not has_option(arguments, "--seed_rnd"):
        return command

    seed = str(secrets.randbelow(999_999) + 1)
    execution_arguments: list[str] = list(command.execution_arguments[:2])
    for argument in arguments:
        if argument == "--seed_rnd":
            execution_arguments.extend(("--seed", seed))
        else:
            execution_arguments.append(argument)
    return FlowCommand(
        source_label=command.source_label,
        display_arguments=command.display_arguments,
        execution_arguments=tuple(execution_arguments),
    )


def replace_long_option(arguments: tuple[str, ...], option: str, value: str) -> tuple[str, ...]:
    """Replace an optional long CLI value, retaining all unrelated arguments."""

    replaced: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == option:
            index += 2
            continue
        if argument.startswith(f"{option}="):
            index += 1
            continue
        replaced.append(argument)
        index += 1
    return (*replaced, option, value)


def apply_model_override(nodes: list[FlowNode], model_name: str | None) -> list[FlowNode]:
    """Apply a runner-level model override to every Ollama command in a flow."""

    if model_name is None:
        return nodes
    model = model_name.strip()
    if not model:
        raise FlowError("--model requires non-empty text")

    def replace_node(node: FlowNode) -> FlowNode:
        if isinstance(node, FlowBranch):
            return FlowBranch(
                source_label=node.source_label,
                condition=node.condition,
                then_steps=tuple(replace_node(child) for child in node.then_steps),
                else_steps=tuple(replace_node(child) for child in node.else_steps),
            )
        if Path(node.execution_arguments[1]).name != "cli_ollama.py":
            return node
        updated_arguments = replace_long_option(node.execution_arguments[2:], "--model", model)
        return FlowCommand(
            source_label=node.source_label,
            display_arguments=(*node.display_arguments[:2], *updated_arguments),
            execution_arguments=(*node.execution_arguments[:2], *updated_arguments),
        )

    return [replace_node(node) for node in nodes]


def apply_sc_overrides(nodes: list[FlowNode], names: list[str] | None) -> list[FlowNode]:
    """Append validated slash-command names to every Ollama command in a flow."""

    if not names:
        return nodes
    commands = [name.strip().removeprefix("/") for name in names]
    if not all(commands):
        raise FlowError("Every runner --sc value must be non-empty text")

    def replace_node(node: FlowNode) -> FlowNode:
        if isinstance(node, FlowBranch):
            return FlowBranch(
                source_label=node.source_label,
                condition=node.condition,
                then_steps=tuple(replace_node(child) for child in node.then_steps),
                else_steps=tuple(replace_node(child) for child in node.else_steps),
            )
        if Path(node.execution_arguments[1]).name != "cli_ollama.py":
            return node
        updated_arguments = (*node.execution_arguments[2:], *(item for name in commands for item in ("--sc", name)))
        return FlowCommand(
            source_label=node.source_label,
            display_arguments=(*node.display_arguments[:2], *updated_arguments),
            execution_arguments=(*node.execution_arguments[:2], *updated_arguments),
        )

    return [replace_node(node) for node in nodes]


def get_ollama_parameter_report(command: FlowCommand) -> str | None:
    """Return the effective Ollama settings for one runnable CLI task.

    This is deliberately a read-only preview: it loads configuration and task
    options but neither connects to Ollama nor starts the command.  Project
    management commands do not have generation settings and return no report.
    """

    if Path(command.execution_arguments[1]).name != "cli_ollama.py":
        return None

    arguments = command.execution_arguments[2:]
    if has_option(arguments, "--project") or has_option(arguments, "--debug"):
        return None
    task_filename = get_option_value(arguments, "--type")
    if not task_filename:
        return None

    try:
        from cli_ollama import get_task_kind, load_task, resolve_task_file

        task = load_task(resolve_task_file(task_filename))
        task_kind = get_task_kind(task)
        app = ollama_api(config_path=PROJECT_ROOT / "lib" / "ollama.json", debug_enabled=False)
        options = app.effective_task_options(task)
    except (OSError, ValueError):
        return None

    model_name = get_option_value(arguments, "--model") or task.get("model")
    overrides = {
        "--seed": "seed",
        "--temp": "temperature",
        "--num-predict": "num_predict",
        "--num-ctx": "num_ctx",
        "--repeat-penalty": "repeat_penalty",
    }
    for option, option_name in overrides.items():
        value = get_option_value(arguments, option)
        if value is not None:
            options[option_name] = value
    if not isinstance(model_name, str) or not model_name:
        return None
    think = task.get("think", False)
    values = (
        ("task", task_kind),
        ("model", model_name),
        ("seed", options["seed"]),
        ("temperature", options["temperature"]),
        ("num_predict", options["num_predict"]),
        ("num_ctx", options["num_ctx"]),
        ("repeat_penalty", options["repeat_penalty"]),
        ("think", str(think).lower()),
    )
    return "[ " + " | ".join(f"{name}: {value}" for name, value in values) + " ]"


def evaluate_flow_condition(condition: FlowCondition, project_directory: Path) -> bool:
    """Evaluate one file condition without allowing access outside the project."""

    project_root = project_directory.resolve()
    path = (project_root / condition.path).resolve()
    try:
        path.relative_to(project_root)
    except ValueError as error:
        raise FlowError("Condition path must remain inside the project directory") from error
    if condition.kind == "file_exists":
        return path.is_file()
    return path.is_file() and path.stat().st_size > 0


def run_flow(
    flow_path: Path,
    nodes: list[FlowNode],
    dry_run: bool,
    *,
    project_directory: Path,
    capture_output: bool,
    debug_enabled: bool,
) -> int:
    """Print and execute validated commands, choosing version 2 branches at runtime."""

    terminal = Terminal()
    mode = "Dry run" if dry_run else "Flow"
    flow_started_at = time.monotonic()
    timestamp = f"[{datetime.now():%H:%M:%S}] " if debug_enabled else ""
    terminal.print("y", f"{timestamp}{mode}: {flow_path.name}")
    if debug_enabled:
        terminal.print("bright_black", f"Working directory: {PROJECT_ROOT}")

    total = sum(1 for _ in iter_flow_commands(nodes))
    completed = 0

    def run_command(command: FlowCommand) -> int:
        nonlocal completed

        completed += 1
        index = completed
        command = materialize_random_seed(command)
        action_started_at = time.monotonic()
        timestamp = f"[{datetime.now():%H:%M:%S}] " if debug_enabled else ""
        terminal.print("y", command.display_text)
        parameter_report = get_ollama_parameter_report(command)
        if parameter_report is not None:
            terminal.print("w", parameter_report)
        if debug_enabled:
            terminal.print(
                "bright_black",
                f"{timestamp}[{index}/{total}] "
                f"{command.source_label}: {command.display_text}",
            )
        if dry_run:
            duration = f" [Duration: {time.monotonic() - action_started_at:.1f} s]"
            if debug_enabled:
                terminal.print(
                    "bright_black",
                    f"{timestamp}[{index}/{total}] validated{duration}",
                )
            return 0

        try:
            if debug_enabled:
                terminal.print(
                    "bright_black",
                    f"{timestamp}[{index}/{total}] executing: "
                    f"{subprocess.list2cmdline(command.execution_arguments)}",
                )
            if capture_output:
                environment = os.environ.copy()
                environment[FLOW_LOG_ENVIRONMENT_VARIABLE] = "1"
                environment[FORCE_COLOR_ENVIRONMENT_VARIABLE] = "1"
                # The parent decodes captured output as UTF-8.  Force the
                # child Python process to use the same encoding instead of
                # inheriting the active Windows console code page.
                environment[PYTHON_IO_ENCODING_ENVIRONMENT_VARIABLE] = "utf-8"
                with subprocess.Popen(
                    command.execution_arguments,
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=None,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=environment,
                ) as process:
                    if process.stdout is not None:
                        for output_line in process.stdout:
                            print(
                                terminal.color("bright_black", output_line),
                                end="",
                                flush=True,
                            )
                    return_code = process.wait()
            else:
                return_code = subprocess.run(
                    command.execution_arguments,
                    cwd=PROJECT_ROOT,
                    check=False,
                ).returncode
        except OSError as error:
            Terminal(file=sys.stderr).print("r", f"ERROR: Could not start step {index}: {error}")
            return 1

        timestamp = f"[{datetime.now():%H:%M:%S}] " if debug_enabled else ""
        duration = f" [Duration: {time.monotonic() - action_started_at:.1f} s]"
        if debug_enabled:
            terminal.print(
                "bright_black",
                f"{timestamp}[{index}/{total}] exit code: {return_code}{duration}",
            )
        if return_code == MODEL_UNAVAILABLE_EXIT_CODE:
            terminal.print(
                "y",
                f"WARNING: Step {index} was skipped because its Ollama model is unavailable.",
            )
            return 0
        if return_code != 0:
            Terminal(file=sys.stderr).print(
                "r",
                f"ERROR: Flow stopped at step {index} with exit code "
                f"{return_code}.",
            )
            return return_code
        return 0

    def run_steps(steps: list[FlowNode] | tuple[FlowNode, ...]) -> int:
        for node in steps:
            if isinstance(node, FlowCommand):
                return_code = run_command(node)
                if return_code != 0:
                    return return_code
                continue

            if dry_run:
                terminal.print(
                    "bright_black",
                    f"{node.source_label}: {node.condition.display_text} "
                    "will select then or else at runtime; both branches validated.",
                )
                return_code = run_steps(node.then_steps)
                if return_code != 0:
                    return return_code
                return_code = run_steps(node.else_steps)
                if return_code != 0:
                    return return_code
                continue

            try:
                condition_result = evaluate_flow_condition(node.condition, project_directory)
            except (OSError, FlowError) as error:
                Terminal(file=sys.stderr).print(
                    "r", f"ERROR: Could not evaluate {node.source_label}: {error}"
                )
                return 1
            branch_name = "then" if condition_result else "else"
            terminal.print(
                "y",
                f"{node.source_label}: {node.condition.display_text} -> {condition_result} ({branch_name})",
            )
            return_code = run_steps(node.then_steps if condition_result else node.else_steps)
            if return_code != 0:
                return return_code
        return 0

    return_code = run_steps(nodes)
    if return_code != 0:
        return return_code

    if dry_run:
        duration = f" [Duration: {time.monotonic() - flow_started_at:.1f} s]"
        terminal.print(
            "y",
            f"Dry run completed: {total} command(s) validated.{duration}",
        )
    else:
        duration = f" [Duration: {time.monotonic() - flow_started_at:.1f} s]"
        completion = (
            f"{completed} step(s)"
            if completed == total
            else f"{completed} selected step(s); {total - completed} step(s) not selected"
        )
        terminal.print(
            "y",
            f"Flow completed successfully: {completion}.{duration}",
        )
    return 0


def main() -> int:
    """Validate and run the selected command flow."""

    arguments = parse_arguments()
    try:
        project_config = load_project_config(PROJECT_ROOT)
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        flow_path = resolve_flow_path(arguments.flow_file, project_directory)
        commands = apply_model_override(load_flow(flow_path, project_directory), arguments.model_override)
        commands = apply_sc_overrides(commands, arguments.sc_overrides)
        project_override = get_initial_project_override(commands)
        if project_override and not arguments.dry_run:
            updated_project_config = {**project_config, "subdir": project_override}
            get_project_directory(PROJECT_ROOT, updated_project_config)
            (PROJECT_ROOT / "project.json").write_text(
                json.dumps(updated_project_config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            project_config = load_project_config(PROJECT_ROOT)
            project_directory = get_project_directory(PROJECT_ROOT, project_config)
        log_enabled = read_log_enabled(PROJECT_ROOT / "project.json")
        project_debug = read_debug_enabled(PROJECT_ROOT / "project.json")
    except (OSError, FlowError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    with console_log(project_directory, "runner.py", log_enabled):
        try:
            return run_flow(
                flow_path,
                commands,
                arguments.dry_run,
                project_directory=project_directory,
                capture_output=log_enabled,
                debug_enabled=True if project_debug is None else project_debug,
            )
        except KeyboardInterrupt:
            print("\nFlow interrupted by user.", file=sys.stderr)
            return 130


if __name__ == "__main__":
    raise SystemExit(main())

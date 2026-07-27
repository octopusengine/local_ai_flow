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
from lib.wrapp_ollama import MODEL_UNAVAILABLE_EXIT_CODE
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FLOW_PATH = Path("flow_test.txt")
PYTHON_LAUNCHERS = {"py", "py.exe", "python", "python.exe", "python3", "python3.exe"}
FLOW_LOG_ENVIRONMENT_VARIABLE = "OLLAMA_FLOW_LOG"
FORCE_COLOR_ENVIRONMENT_VARIABLE = "FORCE_COLOR"
PYTHON_IO_ENCODING_ENVIRONMENT_VARIABLE = "PYTHONIOENCODING"
FLOW_VARIABLE_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
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
    return parser.parse_args()


def resolve_flow_path(configured_path: Path, project_directory: Path) -> Path:
    """Resolve a flow from the root, active project, or ``flows`` directory."""

    if configured_path.is_absolute():
        flow_path = configured_path
    else:
        flow_candidates = (
            PROJECT_ROOT / configured_path,
            project_directory / configured_path,
            PROJECT_ROOT / "flows" / configured_path,
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

    display_arguments = ("python", script_path.name, *arguments[2:])
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


def load_json_flow(flow_path: Path, run_timestamp: str) -> list[FlowCommand]:
    """Load a structured flow and expand each step's parameter matrix."""

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
    if document.get("version") != 1 or isinstance(document.get("version"), bool):
        raise FlowError(f"{flow_path.name}: JSON flow requires \"version\": 1")
    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        raise FlowError(f"{flow_path.name}: \"steps\" must be a non-empty array")

    commands: list[FlowCommand] = []
    for step_number, step in enumerate(steps, start=1):
        location = f"step {step_number}"
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


def load_text_flow(flow_path: Path) -> list[FlowCommand]:
    """Load and validate every active command in a legacy text flow."""

    try:
        lines = flow_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise FlowError(f"Could not read flow file {flow_path}: {error}") from error

    commands: list[FlowCommand] = []
    for line_number, line in enumerate(lines, start=1):
        arguments = split_command(line, flow_path, line_number)
        if not arguments:
            continue
        commands.append(validate_command(arguments, flow_path, f"line {line_number}"))

    if not commands:
        raise FlowError(f"Flow file contains no commands: {flow_path}")
    return commands


def load_flow(flow_path: Path) -> list[FlowCommand]:
    """Load either a legacy text flow or a structured JSON flow."""

    commands = (
        load_json_flow(flow_path, datetime.now().strftime("%y%m%d_%H%M"))
        if flow_path.suffix.casefold() == ".json"
        else load_text_flow(flow_path)
    )
    if not commands:
        raise FlowError(f"Flow file contains no commands: {flow_path}")
    return commands


def get_initial_project_override(commands: list[FlowCommand]) -> str | None:
    """Return the project selected by the first CLI command, if it has one."""

    for index, command in enumerate(commands):
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


def run_flow(
    flow_path: Path,
    commands: list[FlowCommand],
    dry_run: bool,
    *,
    capture_output: bool,
    debug_enabled: bool,
) -> int:
    """Print and optionally execute validated commands in sequence."""

    terminal = Terminal()
    mode = "Dry run" if dry_run else "Flow"
    flow_started_at = time.monotonic()
    timestamp = f"[{datetime.now():%H:%M:%S}] " if debug_enabled else ""
    terminal.print("y", f"{timestamp}{mode}: {flow_path.name}")
    if debug_enabled:
        terminal.print("bright_black", f"Working directory: {PROJECT_ROOT}")

    total = len(commands)
    for index, command in enumerate(commands, start=1):
        action_started_at = time.monotonic()
        timestamp = f"[{datetime.now():%H:%M:%S}] " if debug_enabled else ""
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
            continue

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
            continue
        if return_code != 0:
            Terminal(file=sys.stderr).print(
                "r",
                f"ERROR: Flow stopped at step {index} with exit code "
                f"{return_code}.",
            )
            return return_code

    if dry_run:
        duration = f" [Duration: {time.monotonic() - flow_started_at:.1f} s]"
        terminal.print(
            "y",
            f"Dry run completed: {total} command(s) validated.{duration}",
        )
    else:
        duration = f" [Duration: {time.monotonic() - flow_started_at:.1f} s]"
        terminal.print(
            "y",
            f"Flow completed successfully: {total} step(s).{duration}",
        )
    return 0


def main() -> int:
    """Validate and run the selected command flow."""

    arguments = parse_arguments()
    try:
        project_config = load_project_config(PROJECT_ROOT)
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        flow_path = resolve_flow_path(arguments.flow_file, project_directory)
        commands = load_flow(flow_path)
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
                capture_output=log_enabled,
                debug_enabled=True if project_debug is None else project_debug,
            )
        except KeyboardInterrupt:
            print("\nFlow interrupted by user.", file=sys.stderr)
            return 130


if __name__ == "__main__":
    raise SystemExit(main())

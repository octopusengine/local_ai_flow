r"""Run a simple text file containing project CLI commands in sequence.

The first version intentionally supports only commands in this form:

    python .\cli_example.py argument

Each command is executed with the same Python interpreter that runs this file.
Shell commands and scripts outside the repository root are rejected.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FLOW_PATH = PROJECT_ROOT / "flow_example.txt"
PYTHON_LAUNCHERS = {"py", "py.exe", "python", "python.exe", "python3", "python3.exe"}
CLI_SCRIPT_PATTERN = re.compile(r"cli_[a-z0-9_]+\.py")


class FlowError(ValueError):
    """Report an invalid flow file or command."""


@dataclass(frozen=True)
class FlowCommand:
    """Store one validated command from the flow file."""

    line_number: int
    display_arguments: tuple[str, ...]
    execution_arguments: tuple[str, ...]

    @property
    def display_text(self) -> str:
        """Return a readable command line for terminal output."""

        return subprocess.list2cmdline(self.display_arguments)


def parse_arguments() -> argparse.Namespace:
    """Read the flow path and optional dry-run switch."""

    parser = argparse.ArgumentParser(
        description="Run validated local_ai_flow CLI commands from a text file."
    )
    parser.add_argument(
        "flow_file",
        nargs="?",
        type=Path,
        default=DEFAULT_FLOW_PATH,
        help="flow command file (default: flow_example.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print commands without executing them",
    )
    return parser.parse_args()


def resolve_flow_path(configured_path: Path) -> Path:
    """Resolve a flow path and require it to remain inside the repository."""

    flow_path = configured_path
    if not flow_path.is_absolute():
        flow_path = PROJECT_ROOT / flow_path
    flow_path = flow_path.resolve()
    try:
        flow_path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise FlowError("The flow file must remain inside the repository.") from error
    if not flow_path.is_file():
        raise FlowError(f"Flow file does not exist: {flow_path}")
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
    line_number: int,
) -> FlowCommand:
    """Allow only Python calls to root-level project cli_*.py scripts."""

    location = f"{flow_path.name}:{line_number}"
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
    if CLI_SCRIPT_PATTERN.fullmatch(script_path.name) is None:
        raise FlowError(f"{location}: only cli_*.py scripts are allowed")
    if not script_path.is_file():
        raise FlowError(f"{location}: CLI script does not exist: {script_path.name}")

    display_arguments = ("python", script_path.name, *arguments[2:])
    execution_arguments = (sys.executable, str(script_path), *arguments[2:])
    return FlowCommand(
        line_number=line_number,
        display_arguments=display_arguments,
        execution_arguments=execution_arguments,
    )


def load_flow(flow_path: Path) -> list[FlowCommand]:
    """Load and validate every active command before executing the flow."""

    try:
        lines = flow_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise FlowError(f"Could not read flow file {flow_path}: {error}") from error

    commands: list[FlowCommand] = []
    for line_number, line in enumerate(lines, start=1):
        arguments = split_command(line, flow_path, line_number)
        if not arguments:
            continue
        commands.append(validate_command(arguments, flow_path, line_number))

    if not commands:
        raise FlowError(f"Flow file contains no commands: {flow_path}")
    return commands


def run_flow(flow_path: Path, commands: list[FlowCommand], dry_run: bool) -> int:
    """Print and optionally execute validated commands in sequence."""

    mode = "Dry run" if dry_run else "Flow"
    print(f"{mode}: {flow_path.name}", flush=True)
    print(f"Working directory: {PROJECT_ROOT}", flush=True)

    total = len(commands)
    for index, command in enumerate(commands, start=1):
        print(
            f"[{index}/{total}] line {command.line_number}: {command.display_text}",
            flush=True,
        )
        if dry_run:
            continue

        try:
            result = subprocess.run(
                command.execution_arguments,
                cwd=PROJECT_ROOT,
                check=False,
            )
        except OSError as error:
            print(f"ERROR: Could not start step {index}: {error}", file=sys.stderr)
            return 1

        print(f"[{index}/{total}] exit code: {result.returncode}", flush=True)
        if result.returncode != 0:
            print(
                f"ERROR: Flow stopped at step {index} with exit code "
                f"{result.returncode}.",
                file=sys.stderr,
            )
            return result.returncode

    if dry_run:
        print(f"Dry run completed: {total} command(s) validated.", flush=True)
    else:
        print(f"Flow completed successfully: {total} step(s).", flush=True)
    return 0


def main() -> int:
    """Validate and run the selected command flow."""

    arguments = parse_arguments()
    try:
        flow_path = resolve_flow_path(arguments.flow_file)
        commands = load_flow(flow_path)
    except FlowError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    try:
        return run_flow(flow_path, commands, arguments.dry_run)
    except KeyboardInterrupt:
        print("\nFlow interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

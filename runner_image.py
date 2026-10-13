#!/usr/bin/env python3
"""
Simple image flow runner.

Flow files are stored in ./flow/*.txt or can be passed explicitly.

Supported syntax:

    $input = "./src/test1.jpg"
    $seed = 1
    $scale = 0.9

    python cli_image.py -e $input -s $seed -r $scale -t 10

    @for T in 10,15,20,25,30
        python cli_image.py -e $input -s $seed -f test12_08${T}.png -r $scale -t $T
    @endfor

Range syntax is also supported:

    @for T in 10..30 step 5
        python cli_image.py -e $input -s $seed -t $T
    @endfor

Blank lines and lines beginning with # are ignored.

Join any number of UTF-8 files and text variables with a single newline:
    $intro = "A realistic photograph."
    $base1 = @join($intro, "./prom/e_male.txt", "./prom/d_bikni.txt")
    $base2 = @join($intro, /p_dance, ./prompts/another.txt, "kresba")

Standalone variables and quoted text insert text. Other arguments are file
paths relative to the runner directory. /name searches the prompt_file array
in cli_image.json in order. Each array entry is a directory.
With no config, /name reads ./prom/name.txt.
File paths may contain variables.
Loop list variables are resolved at runtime without splitting their contents:
    @for B in $base1, $base2, $base3
        python cli_image.py -b "$B" -p "A person."
    @endfor
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from prompt_paths import find_prompt


ROOT = Path(__file__).resolve().parent
FLOW_DIR = ROOT / "flow"
VERSION = "v0.8"


PYTHON_LAUNCHERS = {"python", "python3", "py"}


class FlowError(Exception):
    pass


@dataclass
class Command:
    line_number: int
    text: str


@dataclass
class Assignment:
    line_number: int
    name: str
    value: str


@dataclass
class ForBlock:
    line_number: int
    variable: str
    values: list[str]
    body: list[object]


Node = Command | Assignment | ForBlock


# ----------------------------------------------------------------------
# Variables
# ----------------------------------------------------------------------

VARIABLE_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")


def replace_variables(text: str, variables: dict[str, str]) -> str:
    """
    Replace:

        $input
        ${input}

    with values from variables.
    """

    def repl(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)

        if name not in variables:
            raise FlowError(f"undefined variable: ${name}")

        return variables[name]

    return VARIABLE_RE.sub(repl, text)


# ----------------------------------------------------------------------
# FOR values
# ----------------------------------------------------------------------

def parse_for_values(spec: str, path: Path, line_number: int) -> list[str]:
    """
    Parse:

        10,15,20,25,30

    or:

        10..30 step 5

    or:

        10..30
    """

    spec = spec.strip()

    # Optional surrounding parentheses are allowed.
    # Example: @for SEED in (123..150)
    if len(spec) >= 2 and spec[0] == "(" and spec[-1] == ")":
        spec = spec[1:-1].strip()

    if not spec:
        raise FlowError(
            f"{path.name}:{line_number}: empty @for value list"
        )

    # Comma-separated values:
    #
    #   10,15,20,25,30
    if "," in spec:
        values = [item.strip() for item in spec.split(",")]

        if any(not item for item in values):
            raise FlowError(
                f"{path.name}:{line_number}: invalid @for value list"
            )

        return values

    # Range:
    #
    #   10..30
    #   10..30 step 5
    match = re.fullmatch(
        r"(-?\d+)\.\.(-?\d+)(?:\s+step\s+(-?\d+))?",
        spec,
        re.IGNORECASE,
    )

    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        step_text = match.group(3)

        if step_text is None:
            step = 1 if end >= start else -1
        else:
            step = int(step_text)

            if step == 0:
                raise FlowError(
                    f"{path.name}:{line_number}: @for step cannot be zero"
                )

            if start < end and step < 0:
                raise FlowError(
                    f"{path.name}:{line_number}: step must be positive"
                )

            if start > end and step > 0:
                raise FlowError(
                    f"{path.name}:{line_number}: step must be negative"
                )

        values = []

        if step > 0:
            current = start
            while current <= end:
                values.append(str(current))
                current += step
        else:
            current = start
            while current >= end:
                values.append(str(current))
                current += step

        return values

    # Single value is also allowed:
    #
    #   @for T in 10
    return [spec]


# ----------------------------------------------------------------------
# Flow parser
# ----------------------------------------------------------------------

def read_flow_text(path: Path) -> str:
    """Read a flow file with UTF-8 first and common Mac/Windows fallbacks."""

    data = path.read_bytes()

    # Preferred encoding. UTF-8-SIG also handles files with a BOM.
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    # macOS editors can sometimes leave legacy Mac Roman text behind.
    for encoding in ("mac_roman", "cp1250"):
        try:
            text = data.decode(encoding)
            print(f"Warning: {path.name} is not UTF-8; using {encoding}.")
            return text
        except UnicodeDecodeError:
            continue

    raise FlowError(
        f"cannot decode {path}; save the flow as UTF-8"
    )


def parse_flow(path: Path) -> list[Node]:
    try:
        lines = read_flow_text(path).splitlines()
    except OSError as exc:
        raise FlowError(f"cannot read {path}: {exc}") from exc

    root: list[Node] = []
    stack: list[list[Node]] = [root]
    for_stack: list[ForBlock] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        # --------------------------------------------------------------
        # Variable assignment
        #
        # $input = "./src/test1.jpg"
        # $seed = 123
        # --------------------------------------------------------------

        assignment_match = re.fullmatch(
            r"\$([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*",
            line,
        )

        if assignment_match:
            name = assignment_match.group(1)
            value = assignment_match.group(2)

            # Remove optional surrounding quotes.
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {"'", '"'}
            ):
                value = value[1:-1]

            node = Assignment(
                line_number=line_number,
                name=name,
                value=value,
            )

            stack[-1].append(node)
            continue

        # --------------------------------------------------------------
        # @for
        #
        # @for T in 10,15,20,25,30
        # @for T in 10..30 step 5
        # --------------------------------------------------------------

        if line.startswith("@for "):
            match = re.fullmatch(
                r"@for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)",
                line,
                re.IGNORECASE,
            )

            if not match:
                raise FlowError(
                    f"{path.name}:{line_number}: "
                    "expected '@for NAME in VALUES'"
                )

            variable = match.group(1)
            value_spec = match.group(2)

            values = parse_for_values(
                value_spec,
                path,
                line_number,
            )

            block = ForBlock(
                line_number=line_number,
                variable=variable,
                values=values,
                body=[],
            )

            stack[-1].append(block)

            stack.append(block.body)
            for_stack.append(block)

            continue

        # --------------------------------------------------------------
        # @endfor
        # --------------------------------------------------------------

        if line.lower() == "@endfor":
            if not for_stack:
                raise FlowError(
                    f"{path.name}:{line_number}: "
                    "unexpected '@endfor'"
                )

            stack.pop()
            for_stack.pop()

            continue

        # --------------------------------------------------------------
        # Normal command
        # --------------------------------------------------------------

        stack[-1].append(
            Command(
                line_number=line_number,
                text=line,
            )
        )

    if for_stack:
        block = for_stack[-1]

        raise FlowError(
            f"{path.name}:{block.line_number}: "
            "missing '@endfor'"
        )

    return root


# ----------------------------------------------------------------------
# Command expansion
# ----------------------------------------------------------------------

def expand_command(
    command: str,
    variables: dict[str, str],
) -> str:
    return replace_variables(command, variables)


# ----------------------------------------------------------------------
# Command execution
# ----------------------------------------------------------------------

def evaluate_assignment(value: str, variables: dict[str, str]) -> str:
    """Join file contents, short prompts, and text without reinterpreting them."""
    if not value.startswith("@join"):
        return replace_variables(value, variables)
    match = re.fullmatch(r"@join\s*\((.*)\)", value)
    if not match:
        raise FlowError("expected @join(file1, $variable, ...)")
    arguments = []
    current = []
    quote = None
    escaped = False
    for char in match.group(1):
        if escaped:
            current.append(char)
            escaped = False
        elif quote and char == "\\":
            current.append(char)
            escaped = True
        elif char == quote:
            current.append(char)
            quote = None
        elif char in ('"', "'"):
            current.append(char)
            quote = char
        elif char == "," and quote is None:
            arguments.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    arguments.append("".join(current).strip())
    if arguments == [""]:
        raise FlowError("@join requires a comma-separated list of files or variables")
    if any(not argument for argument in arguments):
        raise FlowError("@join contains an empty argument")
    contents = []
    for argument in arguments:
        try:
            tokens = shlex.split(argument)
        except ValueError as exc:
            raise FlowError(f"invalid @join arguments: {exc}") from exc
        if len(tokens) != 1:
            raise FlowError("@join arguments must be separated by commas")
        token = tokens[0]
        if VARIABLE_RE.fullmatch(token):
            text = replace_variables(token, variables).strip()
            if not text:
                raise FlowError(f"@join variable is empty: {token}")
        elif argument.startswith(('"', "'")) and not Path(token).suffix and not any(separator in token for separator in ("/", "\\")):
            text = replace_variables(token, variables).strip()
            if not text:
                raise FlowError("@join text is empty")
        else:
            if re.fullmatch(r"/[A-Za-z0-9_-]+", token) and not argument.startswith(('"', "'")):
                try:
                    config_path = ROOT / "cli_image.json"
                    if config_path.exists():
                        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
                        if not isinstance(config, dict):
                            raise ValueError("configuration root must be a JSON object")
                        sources = config.get("prompt_file", ["prom"])
                    else:
                        sources = ["prom"]
                    path = find_prompt(sources, ROOT, token[1:])
                except (OSError, ValueError) as exc:
                    raise FlowError(f"cannot read @join file {token}: {exc}") from exc
            else:
                path = Path(replace_variables(token, variables))
                if not path.is_absolute():
                    path = ROOT / path
            try:
                text = path.read_text(encoding="utf-8-sig").strip()
            except (OSError, UnicodeError) as exc:
                raise FlowError(f"cannot read @join file {path}: {exc}") from exc
            if not text:
                raise FlowError(f"@join file is empty: {path}")
        contents.append(text)
    return "\n".join(contents)


def run_command(
    command: str,
    variables: dict[str, str],
    dry_run: bool,
    flow_path: Path,
    line_number: int,
) -> None:

    try:
        # Parse first so prompt quotes and newlines remain literal content.
        parts = [replace_variables(part, variables) for part in shlex.split(command)]
    except ValueError as exc:
        raise FlowError(
            f"{flow_path.name}:{line_number}: "
            f"invalid command: {exc}"
        ) from exc

    if not parts:
        return

    # Use the same Python interpreter that runs runner_image.py.
    if parts[0] in PYTHON_LAUNCHERS:
        parts[0] = sys.executable

    print()
    print(f"[line {line_number}]")
    print("$", " ".join(shlex.quote(part) for part in parts))

    if dry_run:
        return

    try:
        result = subprocess.run(
            parts,
            cwd=ROOT,
        )
    except OSError as exc:
        raise FlowError(
            f"{flow_path.name}:{line_number}: "
            f"cannot execute command: {exc}"
        ) from exc

    if result.returncode != 0:
        raise FlowError(
            f"{flow_path.name}:{line_number}: "
            f"command failed with exit code {result.returncode}"
        )


# ----------------------------------------------------------------------
# Node execution
# ----------------------------------------------------------------------

def execute_nodes(
    nodes: list[Node],
    variables: dict[str, str],
    dry_run: bool,
    flow_path: Path,
) -> None:

    for node in nodes:

        # --------------------------------------------------------------
        # Assignment
        # --------------------------------------------------------------

        if isinstance(node, Assignment):
            try:
                value = evaluate_assignment(node.value, variables)
            except FlowError as exc:
                raise FlowError(f"{flow_path.name}:{node.line_number}: {exc}") from exc

            variables[node.name] = value

            if dry_run:
                print(f"[line {node.line_number}] ${node.name} = {value}")

            continue

        # --------------------------------------------------------------
        # Command
        # --------------------------------------------------------------

        if isinstance(node, Command):
            run_command(
                node.text,
                variables,
                dry_run,
                flow_path,
                node.line_number,
            )

            continue

        # --------------------------------------------------------------
        # FOR block
        # --------------------------------------------------------------

        if isinstance(node, ForBlock):

            for value in node.values:
                loop_variables = dict(variables)

                try:
                    resolved_value = replace_variables(value, variables)
                except FlowError as exc:
                    raise FlowError(f"{flow_path.name}:{node.line_number}: {exc}") from exc
                loop_variables[node.variable] = resolved_value

                if dry_run:
                    print(
                        f"\n[for {node.variable}={resolved_value}]"
                    )

                execute_nodes(
                    node.body,
                    loop_variables,
                    dry_run,
                    flow_path,
                )

            continue

        raise FlowError(
            f"internal error: unknown node type {type(node)}"
        )


# ----------------------------------------------------------------------
# Flow discovery
# ----------------------------------------------------------------------

def find_flow(name: str | None) -> Path:
    if name:
        path = Path(name)

        if not path.suffix:
            path = path.with_suffix(".txt")

        if not path.is_absolute():
            path = ROOT / path

        if not path.exists():
            flow_candidate = FLOW_DIR / path.name

            if flow_candidate.exists():
                path = flow_candidate

        if not path.exists():
            raise FlowError(f"flow file not found: {path}")

        return path

    FLOW_DIR.mkdir(exist_ok=True)

    flows = sorted(FLOW_DIR.glob("*.txt"))

    if not flows:
        raise FlowError(
            f"no .txt flow files found in {FLOW_DIR}"
        )

    return flows[0]


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simple Python image flow runner"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    parser.add_argument(
        "flow",
        nargs="?",
        help="flow file, e.g. test3.txt",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show commands without executing them",
    )

    args = parser.parse_args()

    try:
        flow_path = find_flow(args.flow)

        print(f"Runner: {VERSION}")
        print(f"Flow: {flow_path}")

        nodes = parse_flow(flow_path)

        variables: dict[str, str] = {}

        execute_nodes(
            nodes,
            variables,
            args.dry_run,
            flow_path,
        )

        print()
        print("Done.")

        return 0

    except FlowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

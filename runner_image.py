#!/usr/bin/env python3
"""
Simple image flow runner.

Flow files are stored in ./flow/*.txt or can be passed explicitly.

Supported syntax:

    $input = "./src/test1.jpg"
    $seed = 1
    $scale = 0.9

    # String concatenation automatically inserts a newline:
    $animal = "dog"
    $color = "black"
    $envir = "forest"
    $base = $animal + $color + $envir

    # Result:
    # dog\nblack\nforest

    python cli_image.py -e $input -s $seed -r $scale -t 10

    @for T in 10,15,20,25,30
        python cli_image.py -e $input -s $seed -f test12_08${T}.png -r $scale -t $T
    @endfor

Range syntax is also supported:

    @for T in 10..30 step 5
        python cli_image.py -e $input -s $seed -t $T
    @endfor

Blank lines and lines beginning with # are ignored.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FLOW_DIR = ROOT / "flow"


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


def evaluate_assignment(value: str, variables: dict[str, str]) -> str:
    """
    Evaluate a flow assignment.

    '+' means string concatenation only.
    """
    value = value.strip()
    is_concatenation = "+" in value

    parts = []
    current = []
    quote = None
    escaped = False

    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue

        if char == "\\" and quote is not None:
            current.append(char)
            escaped = True
            continue

        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            current.append(char)
            continue

        if char == "+" and quote is None:
            parts.append("".join(current).strip())
            current = []
            continue

        current.append(char)

    if quote is not None:
        raise FlowError("unterminated quote in assignment")

    parts.append("".join(current).strip())

    if any(part == "" for part in parts):
        raise FlowError("empty part in string concatenation")

    result = []

    for part in parts:
        if (
            len(part) >= 2
            and part[0] == part[-1]
            and part[0] in {"'", '"'}
        ):
            result.append(part[1:-1])
        else:
            result.append(replace_variables(part, variables))

    output = "".join(result)

    # Concatenated string assignments automatically insert a newline
    # between every participating part. Explicit "+" parts are not needed.
    if is_concatenation:
        output = "\n".join(result)

    return output


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

            # Store the expression. It is evaluated at execution time,
            # so assignments can refer to variables defined earlier.
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

def run_command(
    command: str,
    variables: dict[str, str],
    dry_run: bool,
    flow_path: Path,
    line_number: int,
) -> None:

    expanded = expand_command(command, variables)

    try:
        parts = shlex.split(expanded)
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
            value = evaluate_assignment(
                node.value,
                variables,
            )

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

                loop_variables[node.variable] = value

                if dry_run:
                    print(
                        f"\n[for {node.variable}={value}]"
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


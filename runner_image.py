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

def parse_flow(path: Path) -> list[Node]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
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
            value = replace_variables(
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


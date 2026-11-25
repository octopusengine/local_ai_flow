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

Loop over prompt names beginning with a prefix:
    @for D in @prefix("d_")
        $dress = @join("/${D}")
        python cli_image.py -b "$dress"
    @endfor
Names come from prompt_file directories (default ./prom), sorted without
duplicates, without the .txt extension. No matches is an error.

Pick one random value each time an assignment executes (also inside loops):
    $D = @random in @prefix("d_")
    $D = @random in d_dress,d_other,d_coat
    $T = @random in 10..30 step 5
The same value sources as @for are supported, including variables.
Selections may repeat. The cli_image.py -s seed does not seed these choices.

Blank lines and lines beginning with # are ignored.
Use @exit on its own line to stop the entire flow, including nested loops.

Join any number of UTF-8 files and text variables with a single newline:
    $intro = "A realistic photograph."
    $base1 = @join($intro, "./prom/e_male.txt", "./prom/d_bikni.txt")
    $base2 = @join($intro, /p_dance, ./prompts/another.txt, "kresba")

Standalone variables and quoted text insert text. Other arguments are file
paths relative to the runner directory. /name searches the prompt_file array
in cli_image.json in order. Each array entry is a directory.
With no config, /name reads ./prom/name.txt.
File paths may contain variables.
Select merge references without reading their contents:
    $files = @files("./dest/background", "./dest/foreground.png")
    python cli_image.py -m --files $files -p "A graphic." -n ./dest/result
Each path is passed as a separate argument. Paths without an extension use
output.format from cli_image.json. Reference order is preserved.
Loop list variables are resolved at runtime without splitting their contents:
    @for B in $base1, $base2, $base3
        python cli_image.py -b "$B" -p "A person."
    @endfor
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from prompt_paths import find_prompt, prompt_entries


ROOT = Path(__file__).resolve().parent
FLOW_DIR = ROOT / "flow"
VERSION = "v0.82"

# Keep runner diagnostics and expanded prompts Unicode-safe on supported terminals.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


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
class Exit:
    line_number: int


@dataclass
class ForBlock:
    line_number: int
    variable: str
    values: list[str]
    body: list[object]
    prefix: str | None = None


Node = Command | Assignment | Exit | ForBlock


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

        value = variables[name]
        if isinstance(value, FileList):
            raise FlowError(f"${name} is a file list; use it as a standalone command argument")
        return value

    return VARIABLE_RE.sub(repl, text)


# ----------------------------------------------------------------------
# FOR values
# ----------------------------------------------------------------------

def parse_for_values(spec: str, path: Path | None = None, line_number: int = 0) -> list[str]:
    """
    Parse:

        10,15,20,25,30

    or:

        10..30 step 5

    or:

        10..30
    """

    location = f"{path.name}:{line_number}: " if path is not None else ""
    spec = spec.strip()

    if spec.startswith("@prefix"):
        match = re.fullmatch(r'''@prefix\s*\(\s*(["'])([A-Za-z0-9_-]+)\1\s*\)''', spec)
        if not match:
            raise FlowError(f'{location}expected @prefix("prefix")')
        prefix = match.group(2)
        try:
            config_path = ROOT / "cli_image.json"
            config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
            if not isinstance(config, dict):
                raise ValueError("configuration root must be a JSON object")
            sources = config.get("prompt_file", ["prom"])
            entries = prompt_entries(sources, ROOT)
            directories = entries if isinstance(sources, list) else [entry.parent for entry in entries]
            names = set()
            for directory in directories:
                if not directory.exists():
                    continue
                for candidate in directory.iterdir():
                    if (candidate.is_file() and candidate.suffix == ".txt"
                            and candidate.stem.startswith(prefix)
                            and re.fullmatch(r"[A-Za-z0-9_-]+", candidate.stem)):
                        names.add(candidate.stem)
        except (OSError, UnicodeError, ValueError) as exc:
            raise FlowError(f"{location}cannot list @prefix prompts: {exc}") from exc
        if not names:
            raise FlowError(f"{location}no prompts match @prefix({prefix!r})")
        print(f'@prefix("{prefix}"): Loaded {len(names)} matching prompt files.')
        return sorted(names)

    # Optional surrounding parentheses are allowed.
    # Example: @for SEED in (123..150)
    if len(spec) >= 2 and spec[0] == "(" and spec[-1] == ")":
        spec = spec[1:-1].strip()

    if not spec:
        raise FlowError(
            f"{location}empty value list"
        )

    # Comma-separated values:
    #
    #   10,15,20,25,30
    if "," in spec:
        values = [item.strip() for item in spec.split(",")]

        if any(not item for item in values):
            raise FlowError(
                f"{location}invalid value list"
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
                    f"{location}step cannot be zero"
                )

            if start < end and step < 0:
                raise FlowError(
                    f"{location}step must be positive"
                )

            if start > end and step > 0:
                raise FlowError(
                    f"{location}step must be negative"
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

def strip_html_comments(text: str) -> str:
    """Remove closed HTML comments, preserving line numbers and word boundaries."""
    return re.sub(
        r"<!--.*?-->",
        lambda match: " " + "\n" * match.group(0).count("\n"),
        text,
        flags=re.DOTALL,
    )


def read_flow_text(path: Path) -> str:
    """Decode flow/prompt text, then remove HTML comments without changing line numbers."""

    data = path.read_bytes()

    # Preferred encoding. UTF-8-SIG also handles files with a BOM.
    try:
        return strip_html_comments(data.decode("utf-8-sig"))
    except UnicodeDecodeError:
        pass

    # If UTF-8 fails, prefer CP1250 for Czech Windows text; MacRoman is last.
    for encoding in ("cp1250", "cp1252", "mac_roman"):
        try:
            text = data.decode(encoding)
            print(f"Warning: {path.name} is not UTF-8; using {encoding}.")
            return strip_html_comments(text)
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

        if line.lower() == "@exit":
            stack[-1].append(Exit(line_number=line_number))
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
                prefix=value_spec.strip() if value_spec.strip().startswith("@prefix") else None,
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
    if value.startswith("@random"):
        match = re.fullmatch(r"@random\s+in\s+(.*)", value)
        if not match:
            raise FlowError('expected @random in VALUES')
        values = parse_for_values(match.group(1))
        # Resolve each item separately, preserving commas inside variable values.
        return random.choice([replace_variables(item, variables) for item in values])
    if value.startswith("@files"):
        match = re.fullmatch(r"@files\s*\((.*)\)", value)
        if not match:
            raise FlowError("expected @files(file1, $variable, ...)")
        lexer = shlex.shlex(match.group(1), posix=True, punctuation_chars=",")
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError as exc:
            raise FlowError(f"invalid @files arguments: {exc}") from exc
        if not tokens or len(tokens) % 2 == 0 or any(
            token != "," if index % 2 else token.startswith(",")
            for index, token in enumerate(tokens)
        ):
            raise FlowError("@files requires a comma-separated list of paths")
        paths = [replace_variables(token, variables) for token in tokens[::2]]
        if any(not path.strip() for path in paths):
            raise FlowError("@files contains an empty path")
        return FileList(paths)
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
        elif argument.startswith(('"', "'")):
            # Quoted text is normally literal, but a quoted /name that becomes
            # a prompt shorthand after variable expansion (e.g. "/${P}")
            # should load the matching prompt fragment's contents.
            expanded = replace_variables(token, variables).strip()
            if not expanded:
                raise FlowError("@join text is empty")
            if re.fullmatch(r"/[A-Za-z0-9_-]+", expanded):
                try:
                    config_path = ROOT / "cli_image.json"
                    if config_path.exists():
                        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
                        if not isinstance(config, dict):
                            raise ValueError("configuration root must be a JSON object")
                        sources = config.get("prompt_file", ["prom"])
                    else:
                        sources = ["prom"]
                    path = find_prompt(sources, ROOT, expanded[1:])
                    text = read_flow_text(path).strip()
                except (OSError, UnicodeError, ValueError) as exc:
                    raise FlowError(f"cannot read @join prompt {expanded}: {exc}") from exc
                if not text:
                    raise FlowError(f"@join prompt is empty: {expanded}")
            else:
                text = expanded
        else:
            expanded = replace_variables(token, variables).strip()
            if re.fullmatch(r"/[A-Za-z0-9_-]+", expanded):
                try:
                    config_path = ROOT / "cli_image.json"
                    if config_path.exists():
                        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
                        if not isinstance(config, dict):
                            raise ValueError("configuration root must be a JSON object")
                        sources = config.get("prompt_file", ["prom"])
                    else:
                        sources = ["prom"]
                    path = find_prompt(sources, ROOT, expanded[1:])
                except (OSError, ValueError) as exc:
                    raise FlowError(f"cannot read @join file {expanded}: {exc}") from exc
            else:
                path = Path(expanded)
                if not path.is_absolute():
                    path = ROOT / path
            try:
                text = read_flow_text(path).strip()
            except (OSError, UnicodeError) as exc:
                raise FlowError(f"cannot read @join file {path}: {exc}") from exc
            if not text:
                raise FlowError(f"@join file is empty: {path}")
        contents.append(text)
    return "\n".join(contents)


class FileList(list):
    """Paths expanded as separate subprocess arguments, without shell parsing."""


def run_command(
    command: str,
    variables: dict[str, str],
    dry_run: bool,
    flow_path: Path,
    line_number: int,
) -> None:

    try:
        # Parse first so prompt quotes and newlines remain literal content.
        parts = []
        for part in shlex.split(command):
            match = VARIABLE_RE.fullmatch(part)
            value = variables.get(match.group(1) or match.group(2)) if match else None
            if isinstance(value, FileList):
                parts.extend(value)
            else:
                parts.append(replace_variables(part, variables))
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
) -> bool:
    """Execute nodes; return True when @exit stops the entire flow."""

    for node in nodes:

        if isinstance(node, Exit):
            if dry_run:
                print(f"[line {node.line_number}] @exit")
            return True

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

            for iteration, value in enumerate(node.values, start=1):
                loop_variables = dict(variables)

                try:
                    resolved_value = replace_variables(value, variables)
                except FlowError as exc:
                    raise FlowError(f"{flow_path.name}:{node.line_number}: {exc}") from exc
                loop_variables[node.variable] = resolved_value

                if node.prefix is not None:
                    print(
                        f"\n[for {node.variable}={resolved_value} "
                        f"{iteration}/{len(node.values)}]",
                        flush=True,
                    )
                elif dry_run:
                    print(
                        f"\n[for {node.variable}={resolved_value}]"
                    )

                if execute_nodes(
                    node.body,
                    loop_variables,
                    dry_run,
                    flow_path,
                ):
                    return True

            continue

        raise FlowError(
            f"internal error: unknown node type {type(node)}"
        )

    return False


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

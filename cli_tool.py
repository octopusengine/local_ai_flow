"""Simple local utility with a handful of standalone actions, usable as a runner.py step."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

from lib.wrapp_log import get_project_directory, load_project_config


PROJECT_DIR = Path(__file__).resolve().parent
TOOL_CONFIG_PATH = PROJECT_DIR / "cli_tool.json"
CONTEXT_FILENAME = "tools_context.txt"
MAX_LOGGED_RESPONSE_CHARS = 1000

__version__ = "0.1"


def load_tool_config(config_path: Path | None = None) -> dict:
    """Load cli_tool.json (word for --w, output_filename for the context file, ...)."""

    if config_path is None:
        config_path = TOOL_CONFIG_PATH
    try:
        text = config_path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise SystemExit(f"Cannot read tool configuration {config_path}: {error}") from error
    try:
        configuration = json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"Tool configuration is not valid JSON: {config_path}: {error}") from error
    if not isinstance(configuration, dict):
        raise SystemExit(f"Tool configuration must be a JSON object: {config_path}")
    return configuration


def get_context_filename() -> str:
    """Return output_filename from cli_tool.json, defaulting to CONTEXT_FILENAME if unset/missing."""

    try:
        tool_config = load_tool_config()
    except SystemExit:
        return CONTEXT_FILENAME
    filename = tool_config.get("output_filename")
    if isinstance(filename, str) and filename.strip():
        return filename.strip()
    return CONTEXT_FILENAME


def get_context_path(project_directory: Path) -> Path:
    """Return the path to SUBDIR/<output_filename from cli_tool.json, default tools_context.txt>."""

    return project_directory / get_context_filename()


def append_context(project_directory: Path, line: str) -> Path:
    """Append one line to the context file (SUBDIR/<output_filename>), creating it if needed."""

    context_path = get_context_path(project_directory)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    with context_path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")
    return context_path


def clear_context(project_directory: Path) -> Path:
    """Clear (empty) the context file (SUBDIR/<output_filename>)."""

    context_path = get_context_path(project_directory)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("", encoding="utf-8")
    return context_path


def run_ping(project_directory: Path, host: str = "8.8.8.8") -> int:
    """Send a single ping to host, print and log the result, and return the process exit code."""

    ping_command = ["ping", "-n", "1", host] if sys.platform.startswith("win") else ["ping", "-c", "1", host]
    result = subprocess.run(ping_command, capture_output=True, text=True, check=False)
    output = result.stdout.strip() or result.stderr.strip()
    if output:
        print(output)
    summary = output.splitlines()[-1] if output else f"no response (exit code {result.returncode})"
    append_context(project_directory, f"[ping] {summary}")
    return result.returncode


def fetch_url(project_directory: Path, url: str) -> str:
    """Fetch url, log a truncated copy to the context file, and return the response body."""

    request = urllib.request.Request(url, headers={"User-Agent": "cli_tool.py"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
    except urllib.error.URLError as error:
        raise SystemExit(f"Cannot fetch {url}: {error}") from error
    truncated_body = body[:MAX_LOGGED_RESPONSE_CHARS]
    append_context(project_directory, f"[url_response] {truncated_body}")
    return body


def write_output_file(project_directory: Path, filename: str, content: str) -> Path:
    """Save content to filename inside project_directory (guarded like read_context_file)."""

    candidate = (project_directory / filename).resolve()
    try:
        candidate.relative_to(project_directory.resolve())
    except ValueError as error:
        raise SystemExit(f"File must stay inside the project directory: {filename}") from error
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(content, encoding="utf-8")
    return candidate


def read_context_file(project_directory: Path, filename: str) -> tuple[Path, str]:
    """Resolve filename inside project_directory and return (path, text content)."""

    candidate = (project_directory / filename).resolve()
    try:
        candidate.relative_to(project_directory.resolve())
    except ValueError as error:
        raise SystemExit(f"File must stay inside the project directory: {filename}") from error
    if not candidate.is_file():
        raise SystemExit(f"File not found: {candidate}")
    try:
        content = candidate.read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"Cannot read {candidate}: {error}") from error
    except UnicodeDecodeError as error:
        raise SystemExit(f"Cannot read {candidate} as text: {error}") from error
    return candidate, content


def count_file_stats(project_directory: Path, filename: str) -> tuple[Path, dict[str, int]]:
    """Resolve filename inside project_directory and return (path, {lines, words, chars})."""

    file_path, content = read_context_file(project_directory, filename)
    stats = {"lines": len(content.splitlines()), "words": len(content.split()), "chars": len(content)}
    return file_path, stats


def read_context(project_directory: Path) -> str:
    """Return the current context file content, or '' if it does not exist yet."""

    context_path = get_context_path(project_directory)
    if not context_path.is_file():
        return ""
    return context_path.read_text(encoding="utf-8")


def get_context_stats(project_directory: Path) -> dict[str, int]:
    """Return {chars, lines} for the current context file."""

    content = read_context(project_directory)
    return {"chars": len(content), "lines": len(content.splitlines())}


def trim_context(project_directory: Path, max_chars: int) -> tuple[int, int]:
    """Keep only the last max_chars characters of the context file. Return (old_len, new_len)."""

    if max_chars < 0:
        raise SystemExit("--trim N requires N to be zero or a positive number of characters.")
    content = read_context(project_directory)
    old_len = len(content)
    trimmed = content[-max_chars:] if max_chars else ""
    context_path = get_context_path(project_directory)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(trimmed, encoding="utf-8")
    return old_len, len(trimmed)


def resolve_project_path(project_directory: Path, filename: str) -> Path:
    """Resolve filename inside project_directory, raising if it would escape it."""

    candidate = (project_directory / filename).resolve()
    try:
        candidate.relative_to(project_directory.resolve())
    except ValueError as error:
        raise SystemExit(f"File must stay inside the project directory: {filename}") from error
    return candidate


def copy_context_file(project_directory: Path, source_filename: str, destination_filename: str) -> tuple[Path, Path]:
    """Copy source_filename to destination_filename, both resolved inside project_directory."""

    source_path = resolve_project_path(project_directory, source_filename)
    if not source_path.is_file():
        raise SystemExit(f"File not found: {source_path}")
    destination_path = resolve_project_path(project_directory, destination_filename)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_path)
    return source_path, destination_path


def parse_arguments() -> argparse.Namespace:
    """Parse the single explicit action this tool should run."""

    parser = argparse.ArgumentParser(description="Simple local utility usable as a runner.py step.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--hw", action="store_true", help="print 'hello world'")
    actions.add_argument(
        "--proj",
        "--poject",
        "--project",
        dest="project",
        action="store_true",
        help="print the current project directory (SUBDIR)",
    )
    actions.add_argument("--clr", action="store_true", help="clear the context file")
    actions.add_argument("--w", dest="word", action="store_true", help="print the test word from cli_tool.json")
    actions.add_argument("--ping", action="store_true", help="send a single ping to 8.8.8.8")
    actions.add_argument("--url", metavar="URL", help="fetch URL and print the response body")
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="used with --url: also save the full raw response body to FILE",
    )
    actions.add_argument(
        "--text",
        metavar="TEXT",
        help="log TEXT to the context file under a [tool_text] prefix",
    )
    actions.add_argument(
        "--echo",
        metavar="TEXT",
        help="print TEXT to the terminal only (not logged to the context file)",
    )
    actions.add_argument(
        "--add",
        nargs=2,
        metavar=("NAME", "FILE"),
        help="log FILE's content to the context file under a [NAME] prefix",
    )
    actions.add_argument(
        "--date-time",
        dest="date_time",
        action="store_true",
        help="print the local date and time, and log it to the context file",
    )
    actions.add_argument(
        "--wc",
        metavar="FILE",
        help="log line/word/char counts of FILE under a [wc: FILE] prefix",
    )
    actions.add_argument("--show", action="store_true", help="print the current context file content")
    actions.add_argument(
        "--size",
        action="store_true",
        help="print the current context file character and line count",
    )
    actions.add_argument(
        "--trim",
        metavar="N",
        type=int,
        help="keep only the last N characters of the context file",
    )
    actions.add_argument(
        "--env",
        metavar="VAR",
        help="print environment variable VAR and log it under a [env: VAR] prefix",
    )
    actions.add_argument(
        "--copy",
        nargs="+",
        metavar="FILE",
        help="--copy F2: copy the context file to F2. --copy F1 F2: copy F1 to F2",
    )
    parser.add_argument("-V", "--version", action="version", version=f"cli_tool.py {__version__}")
    return parser.parse_args()


def main() -> int:
    """Resolve the project directory and run the requested action."""

    arguments = parse_arguments()
    if arguments.out and not arguments.url:
        raise SystemExit("--out can only be used together with --url.")
    project_config = load_project_config(PROJECT_DIR)
    project_directory = get_project_directory(PROJECT_DIR, project_config)

    if arguments.hw:
        print("hello world")
        return 0

    if arguments.project:
        print(project_directory)
        return 0

    if arguments.clr:
        context_path = clear_context(project_directory)
        print(f"Cleared: {context_path}")
        return 0

    if arguments.word:
        tool_config = load_tool_config()
        word = tool_config.get("word")
        if not isinstance(word, str):
            raise SystemExit(f"cli_tool.json is missing a text 'word' field: {TOOL_CONFIG_PATH}")
        print(word)
        return 0

    if arguments.ping:
        return run_ping(project_directory)

    if arguments.url:
        body = fetch_url(project_directory, arguments.url)
        if arguments.out:
            output_path = write_output_file(project_directory, arguments.out, body)
            print(f"Saved: {output_path}")
        print(body)
        return 0

    if arguments.text:
        append_context(project_directory, f"[tool_text] {arguments.text}")
        print(arguments.text)
        return 0

    if arguments.echo:
        print(arguments.echo)
        return 0

    if arguments.add:
        name, filename = arguments.add
        file_path, content = read_context_file(project_directory, filename)
        append_context(project_directory, f"[{name}] {content}")
        print(f"Added {file_path} as [{name}]")
        return 0

    if arguments.date_time:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        print(timestamp)
        append_context(project_directory, f"[date-time] {timestamp}")
        return 0

    if arguments.wc:
        file_path, stats = count_file_stats(project_directory, arguments.wc)
        summary = f"lines={stats['lines']} words={stats['words']} chars={stats['chars']}"
        append_context(project_directory, f"[wc: {file_path.name}] {summary}")
        print(summary)
        return 0

    if arguments.show:
        content = read_context(project_directory)
        print(content if content else "(context file is empty)")
        return 0

    if arguments.size:
        stats = get_context_stats(project_directory)
        print(f"chars={stats['chars']} lines={stats['lines']}")
        return 0

    if arguments.trim is not None:
        old_len, new_len = trim_context(project_directory, arguments.trim)
        print(f"Trimmed context file: {old_len} -> {new_len} chars")
        return 0

    if arguments.env:
        value = os.environ.get(arguments.env)
        if value is None:
            print(f"(not set: {arguments.env})")
            return 0
        append_context(project_directory, f"[env: {arguments.env}] {value}")
        print(value)
        return 0

    if arguments.copy:
        if len(arguments.copy) > 2:
            raise SystemExit("--copy accepts at most two arguments: --copy F or --copy F1 F2")
        if len(arguments.copy) == 1:
            source_filename = get_context_filename()
            destination_filename = arguments.copy[0]
        else:
            source_filename, destination_filename = arguments.copy
        source_path, destination_path = copy_context_file(project_directory, source_filename, destination_filename)
        print(f"Copied {source_path} -> {destination_path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

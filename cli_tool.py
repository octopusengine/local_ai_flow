"""Simple local utility with a handful of standalone actions, usable as a runner.py step."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
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


def load_tool_config(config_path: Path = TOOL_CONFIG_PATH) -> dict:
    """Load cli_tool.json (currently just the --w test word)."""

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


def get_context_path(project_directory: Path) -> Path:
    """Return the path to SUBDIR/tools_context.txt."""

    return project_directory / CONTEXT_FILENAME


def append_context(project_directory: Path, line: str) -> Path:
    """Append one line to SUBDIR/tools_context.txt, creating the file if needed."""

    context_path = get_context_path(project_directory)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    with context_path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")
    return context_path


def clear_context(project_directory: Path) -> Path:
    """Clear (empty) SUBDIR/tools_context.txt."""

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
    """Fetch url, log a truncated copy to tools_context.txt, and return the response body."""

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
    actions.add_argument("--clr", action="store_true", help="clear SUBDIR/tools_context.txt")
    actions.add_argument("--w", dest="word", action="store_true", help="print the test word from cli_tool.json")
    actions.add_argument("--ping", action="store_true", help="send a single ping to 8.8.8.8")
    actions.add_argument("--url", metavar="URL", help="fetch URL and print the response body")
    actions.add_argument(
        "--text",
        metavar="TEXT",
        help="log TEXT to tools_context.txt under a [tool_text] prefix",
    )
    actions.add_argument(
        "--date-time",
        dest="date_time",
        action="store_true",
        help="print the local date and time, and log it to tools_context.txt",
    )
    parser.add_argument("--version", action="version", version=f"cli_tool.py {__version__}")
    return parser.parse_args()


def main() -> int:
    """Resolve the project directory and run the requested action."""

    arguments = parse_arguments()
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
        print(fetch_url(project_directory, arguments.url))
        return 0

    if arguments.text:
        append_context(project_directory, f"[tool_text] {arguments.text}")
        print(arguments.text)
        return 0

    if arguments.date_time:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        print(timestamp)
        append_context(project_directory, f"[date-time] {timestamp}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Simple local utility with a handful of standalone actions, usable as a runner.py step."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from lib.wrapp_web import WebFetchError, fetch_url_text

from lib.wrapp_log import get_project_directory, load_project_config
from lib.wrapp_services import network_ping, system_datetime


PROJECT_DIR = Path(__file__).resolve().parent
TOOL_CONFIG_PATH = PROJECT_DIR / "cli_tool.json"
CONTEXT_FILENAME = "tools_context.txt"
DEFAULT_CODE_SUBDIR = "sandbox"
DEFAULT_CODE_REPORT_FILENAME = "code_report.txt"
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 30
CODE_OK_MARKER_FILENAME = "code_ok.flag"
MAX_LOGGED_RESPONSE_CHARS = 1000
MAX_CODE_REPORT_CHARS = 20000
CODE_EXTRACT_EXTENSIONS = {".py", ".bat", ".sh", ".html"}
CODE_FENCE_PATTERN = re.compile(r"```[ \t]*[A-Za-z0-9_+\-]*\r?\n(.*?)```", re.DOTALL)
DEFAULT_BATCH_IN_SUBDIR = "src"
DEFAULT_BATCH_OUT_SUBDIR = "dest"
BATCH_LIST_FILENAME = "batch_list.txt"
BATCH_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
BATCH_TEXT_EXTENSIONS = {
    ".bat", ".css", ".csv", ".html", ".htm", ".ini", ".js", ".json", ".log", ".md",
    ".ps1", ".py", ".rst", ".sh", ".sql", ".toml", ".ts", ".tsv", ".txt", ".xml", ".yaml", ".yml",
}

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


def get_code_subdir_name() -> str:
    """Return code_subdir from cli_tool.json, defaulting to DEFAULT_CODE_SUBDIR if unset/missing."""

    try:
        tool_config = load_tool_config()
    except SystemExit:
        return DEFAULT_CODE_SUBDIR
    subdir_name = tool_config.get("code_subdir")
    if isinstance(subdir_name, str) and subdir_name.strip():
        return subdir_name.strip()
    return DEFAULT_CODE_SUBDIR


def get_code_report_filename() -> str:
    """Return code_report from cli_tool.json, defaulting to DEFAULT_CODE_REPORT_FILENAME if unset/missing."""

    try:
        tool_config = load_tool_config()
    except SystemExit:
        return DEFAULT_CODE_REPORT_FILENAME
    report_filename = tool_config.get("code_report")
    if isinstance(report_filename, str) and report_filename.strip():
        return report_filename.strip()
    return DEFAULT_CODE_REPORT_FILENAME


def get_code_timeout_seconds() -> int:
    """Return code_timeout from cli_tool.json, defaulting to DEFAULT_SCRIPT_TIMEOUT_SECONDS if unset/invalid."""

    try:
        tool_config = load_tool_config()
    except SystemExit:
        return DEFAULT_SCRIPT_TIMEOUT_SECONDS
    timeout_value = tool_config.get("code_timeout")
    if isinstance(timeout_value, int) and not isinstance(timeout_value, bool) and timeout_value > 0:
        return timeout_value
    return DEFAULT_SCRIPT_TIMEOUT_SECONDS


def get_batch_in_subdir() -> str:
    """Return batch_in from cli_tool.json, defaulting to DEFAULT_BATCH_IN_SUBDIR if unset/missing."""

    try:
        tool_config = load_tool_config()
    except SystemExit:
        return DEFAULT_BATCH_IN_SUBDIR
    subdir_name = tool_config.get("batch_in")
    if isinstance(subdir_name, str) and subdir_name.strip():
        return subdir_name.strip()
    return DEFAULT_BATCH_IN_SUBDIR


def get_batch_out_subdir() -> str:
    """Return batch_out from cli_tool.json, defaulting to DEFAULT_BATCH_OUT_SUBDIR if unset/missing."""

    try:
        tool_config = load_tool_config()
    except SystemExit:
        return DEFAULT_BATCH_OUT_SUBDIR
    subdir_name = tool_config.get("batch_out")
    if isinstance(subdir_name, str) and subdir_name.strip():
        return subdir_name.strip()
    return DEFAULT_BATCH_OUT_SUBDIR


def list_batch_files(
    project_directory: Path,
    allowed_extensions: set[str] | None = None,
) -> tuple[Path, Path, list[str]]:
    """List files (non-recursive) in SUBDIR/<batch_in>, and ensure SUBDIR/<batch_out> exists.

    Returns (batch_in_dir, batch_out_dir, sorted filenames).
    """

    batch_in_dir = resolve_project_path(project_directory, get_batch_in_subdir())
    if not batch_in_dir.is_dir():
        raise SystemExit(f"batch_in directory not found: {batch_in_dir}")
    batch_out_dir = resolve_project_path(project_directory, get_batch_out_subdir())
    batch_out_dir.mkdir(parents=True, exist_ok=True)
    normalized_extensions = (
        {extension.casefold() for extension in allowed_extensions} if allowed_extensions is not None else None
    )
    filenames = sorted(
        entry.name
        for entry in batch_in_dir.iterdir()
        if entry.is_file() and (normalized_extensions is None or entry.suffix.casefold() in normalized_extensions)
    )
    return batch_in_dir, batch_out_dir, filenames


def write_batch_list(project_directory: Path, filenames: list[str]) -> Path:
    """Write one filename per line to SUBDIR/batch_list.txt for runner.py batch loops."""

    batch_list_path = project_directory / BATCH_LIST_FILENAME
    batch_list_path.parent.mkdir(parents=True, exist_ok=True)
    batch_list_path.write_text("\n".join(filenames) + ("\n" if filenames else ""), encoding="utf-8")
    return batch_list_path


def get_sandbox_directory(project_directory: Path) -> Path:
    """Return SUBDIR/<code_subdir from cli_tool.json, default sandbox>, creating it if needed."""

    sandbox_dir = resolve_project_path(project_directory, get_code_subdir_name())
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    return sandbox_dir


def get_code_report_path(project_directory: Path) -> Path:
    """Return the path to SUBDIR/<code_report from cli_tool.json, default code_report.txt>."""

    return project_directory / get_code_report_filename()


def get_code_ok_marker_path(project_directory: Path) -> Path:
    """Return the path to SUBDIR/code_ok.flag."""

    return project_directory / CODE_OK_MARKER_FILENAME


def update_code_ok_marker(project_directory: Path, success: bool) -> Path:
    """Create SUBDIR/code_ok.flag when success is True, otherwise remove any stale marker.

    This is purely mechanical (based on the script's exit code) and never
    involves the LLM, so it is a reliable, reproducible fact to branch on
    with '@if file_exists(...)' in a flow.
    """

    marker_path = get_code_ok_marker_path(project_directory)
    if success:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("", encoding="utf-8")
    else:
        marker_path.unlink(missing_ok=True)
    return marker_path


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

    result = network_ping(host)
    output = str(result["output"])
    if output:
        print(output)
    append_context(project_directory, f"[ping] {result['summary']}")
    exit_code = result["exit_code"]
    return exit_code if isinstance(exit_code, int) else 1


def fetch_url(project_directory: Path, url: str) -> str:
    """Fetch url, log a truncated copy to the context file, and return the response body."""

    try:
        body = fetch_url_text(url, timeout_seconds=10, user_agent="cli_tool.py")
    except WebFetchError as error:
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


def run_python_script(
    project_directory: Path,
    filename: str,
    timeout_seconds: int,
) -> tuple[Path, str, int | None, bool]:
    """Run filename from the sandbox with the current Python interpreter.

    Returns (script_path, combined_stdout_and_stderr, return_code, timed_out).
    return_code is None when timed_out is True.
    """

    sandbox_dir = get_sandbox_directory(project_directory)
    script_path = resolve_project_path(sandbox_dir, filename)
    if not script_path.is_file():
        raise SystemExit(f"Python script not found: {script_path}")
    try:
        result = subprocess.run(
            [sys.executable, script_path.name],
            cwd=sandbox_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return script_path, result.stdout, result.returncode, False
    except subprocess.TimeoutExpired as error:
        partial_output = error.stdout or ""
        if isinstance(partial_output, bytes):
            partial_output = partial_output.decode("utf-8", errors="replace")
        return script_path, partial_output, None, True


def write_code_report(
    project_directory: Path,
    script_path: Path,
    output: str,
    return_code: int | None,
    timed_out: bool,
    timeout_seconds: int,
) -> Path:
    """Overwrite the code report with the latest run's combined output."""

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    status_line = f"TIMEOUT after {timeout_seconds}s" if timed_out else f"exit code {return_code}"
    truncated_output = output[:MAX_CODE_REPORT_CHARS]
    if len(output) > MAX_CODE_REPORT_CHARS:
        truncated_output += f"\n...[output truncated to first {MAX_CODE_REPORT_CHARS} characters]"
    report_text = f"[code_report] {script_path.name} - {status_line} - {timestamp}\n\n{truncated_output}"

    report_path = get_code_report_path(project_directory)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    return report_path


def extract_code_block(text: str) -> str:
    """Strip markdown code fences and any surrounding prose, keeping only the code.

    If no fenced blocks are found, the text is returned unchanged (assumed already clean).
    Multiple fenced blocks are concatenated in order, separated by a blank line.
    """

    matches = CODE_FENCE_PATTERN.findall(text)
    if not matches:
        return text
    cleaned_blocks = [match.strip("\n") for match in matches]
    return "\n\n".join(cleaned_blocks) + "\n"


def code_extract_file(project_directory: Path, filename: str) -> tuple[Path, bool]:
    """Strip markdown fences/prose from filename in place. Returns (path, changed)."""

    file_path = resolve_project_path(project_directory, filename)
    if not file_path.is_file():
        raise SystemExit(f"File not found: {file_path}")
    if file_path.suffix.casefold() not in CODE_EXTRACT_EXTENSIONS:
        allowed = ", ".join(sorted(CODE_EXTRACT_EXTENSIONS))
        raise SystemExit(f"--code-extract only supports these extensions: {allowed}")
    original = file_path.read_text(encoding="utf-8")
    cleaned = extract_code_block(original)
    changed = cleaned != original
    if changed:
        file_path.write_text(cleaned, encoding="utf-8")
    return file_path, changed


def strip_html_markup(text: str) -> str:
    """Remove HTML tags, script/style blocks, comments, and decode entities."""

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    block_tags = r"(p|div|h[1-6]|li|tr|td|th|blockquote|section|article|header|footer|ul|ol|table)"
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(rf"</{block_tags}\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(rf"<{block_tags}(\s[^>]*)?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def strip_markdown_markup(text: str) -> str:
    """Remove common Markdown syntax, keeping the underlying text content."""

    text = re.sub(r"```[^\n]*\n?", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$", "", text, flags=re.MULTILINE)
    return text


def normalize_plain_text(text: str) -> str:
    """Trim trailing whitespace per line and collapse runs of blank lines."""

    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_plain_text(text: str) -> str:
    """Strip HTML tags and Markdown syntax, leaving plain readable text."""

    text = strip_html_markup(text)
    text = strip_markdown_markup(text)
    return normalize_plain_text(text)


def text_extract_file(project_directory: Path, source_filename: str, destination_filename: str) -> tuple[Path, Path]:
    """Strip HTML/Markdown markup from source_filename, saving plain text to destination_filename."""

    source_path = resolve_project_path(project_directory, source_filename)
    if not source_path.is_file():
        raise SystemExit(f"File not found: {source_path}")
    original = source_path.read_text(encoding="utf-8", errors="replace")
    cleaned = extract_plain_text(original)
    destination_path = resolve_project_path(project_directory, destination_filename)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(cleaned, encoding="utf-8")
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
    actions.add_argument(
        "--run-python",
        dest="run_python",
        metavar="FILE",
        help="run FILE from the sandbox with python and write its output to the code report",
    )
    actions.add_argument(
        "--code-extract",
        dest="code_extract",
        metavar="FILE",
        help="strip markdown code fences/prose from FILE (.py/.bat/.sh/.html), keeping only the code",
    )
    actions.add_argument(
        "--text-extract",
        dest="text_extract",
        nargs=2,
        metavar=("F1", "F2"),
        help="strip HTML tags/Markdown syntax from F1, saving plain text as F2",
    )
    actions.add_argument(
        "--batch",
        action="store_true",
        help="list files in batch_in, write batch_list.txt for '@for VAR in $batch_list' in runner.py",
    )
    actions.add_argument(
        "--batch-img",
        dest="batch_img",
        action="store_true",
        help="list .png, .jpg, and .jpeg files in batch_in, then write batch_list.txt",
    )
    actions.add_argument(
        "--batch-txt",
        dest="batch_txt",
        action="store_true",
        help="list text and source files in batch_in, then write batch_list.txt",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        help="used with --run-python: override the script timeout (default: code_timeout in cli_tool.json)",
    )
    parser.add_argument("-V", "--version", action="version", version=f"cli_tool.py {__version__}")
    return parser.parse_args()


def main() -> int:
    """Resolve the project directory and run the requested action."""

    arguments = parse_arguments()
    if arguments.out and not arguments.url:
        raise SystemExit("--out can only be used together with --url.")
    if arguments.timeout is not None and not arguments.run_python:
        raise SystemExit("--timeout can only be used together with --run-python.")
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
        timestamp = system_datetime()
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

    if arguments.run_python:
        timeout_seconds = arguments.timeout if arguments.timeout is not None else get_code_timeout_seconds()
        script_path, output, return_code, timed_out = run_python_script(
            project_directory, arguments.run_python, timeout_seconds
        )
        report_path = write_code_report(project_directory, script_path, output, return_code, timed_out, timeout_seconds)
        success = (not timed_out) and (return_code == 0)
        marker_path = update_code_ok_marker(project_directory, success)
        print(output)
        if timed_out:
            print(f"TIMEOUT after {timeout_seconds}s")
        else:
            print(f"exit code: {return_code}")
        print(f"Report: {report_path}")
        print(f"OK marker: {'created' if success else 'cleared'} ({marker_path})")
        return 0

    if arguments.code_extract:
        file_path, changed = code_extract_file(project_directory, arguments.code_extract)
        if changed:
            print(f"Cleaned: {file_path}")
        else:
            print(f"No markdown fences found, left unchanged: {file_path}")
        return 0

    if arguments.text_extract:
        source_filename, destination_filename = arguments.text_extract
        source_path, destination_path = text_extract_file(project_directory, source_filename, destination_filename)
        print(f"Saved plain text: {destination_path}")
        return 0

    if arguments.batch or arguments.batch_img or arguments.batch_txt:
        allowed_extensions = (
            BATCH_IMAGE_EXTENSIONS
            if arguments.batch_img
            else BATCH_TEXT_EXTENSIONS if arguments.batch_txt else None
        )
        batch_in_dir, batch_out_dir, filenames = list_batch_files(project_directory, allowed_extensions)
        batch_list_path = write_batch_list(project_directory, filenames)
        if not filenames:
            print(f"(no files found in {batch_in_dir})")
            print(f"0 file(s) -> {batch_list_path}")
            print(f"Destination directory ready: {batch_out_dir}")
            return 0
        for filename in filenames:
            print(filename)
        print(f"{len(filenames)} file(s) -> {batch_list_path}")
        print(f"Destination directory ready: {batch_out_dir}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

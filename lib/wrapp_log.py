"""Small, reusable console-to-file logging helper for the examples."""

import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, TextIO


__version__ = "0.26.03"


ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TEXT_INPUT_ENCODING = "utf-8-sig"
TEXT_OUTPUT_ENCODING = "utf-8-sig"
UTF8_BOM = b"\xef\xbb\xbf"


class _Tee:
    """Send text to the original console stream and a log file."""

    def __init__(self, stream: TextIO, log_file: TextIO) -> None:
        self._stream = stream
        self._log_file = log_file

    def write(self, text: str) -> int:
        written = self._stream.write(text)
        # Libraries such as Colorama can retain this stream and write an ANSI
        # reset from an atexit handler, after console_log has closed its file.
        if not self._log_file.closed:
            self._log_file.write(ANSI_ESCAPE.sub("", text))
        return written

    def flush(self) -> None:
        self._stream.flush()
        if not self._log_file.closed:
            self._log_file.flush()

    def isatty(self) -> bool:
        return self._stream.isatty()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def load_json_object(path: Path) -> Dict[str, object]:
    """Read a JSON object from ``path`` with command-line friendly errors."""

    try:
        data = json.loads(path.read_text(encoding=TEXT_INPUT_ENCODING))
    except OSError as error:
        raise ValueError(f"Cannot read configuration {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Configuration is not valid JSON: {path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Configuration must contain a JSON object: {path}")
    return data


def load_project_config(project_root: Path) -> Dict[str, object]:
    """Load the shared ``project.json`` configuration from a project root."""

    return load_json_object(project_root / "project.json")


def read_log_enabled(config_path: Path, default: bool = True) -> bool:
    """Read and validate a configuration's optional ``log`` switch."""

    data = load_json_object(config_path)
    enabled = data.get("log", default)
    if not isinstance(enabled, bool):
        raise ValueError(f"'log' must be true or false: {config_path}")
    return enabled


def read_debug_enabled(config_path: Path) -> bool | None:
    """Read and validate an optional project-level ``debug`` override."""

    data = load_json_object(config_path)
    enabled = data.get("debug")
    if enabled is not None and not isinstance(enabled, bool):
        raise ValueError(f"'debug' must be true or false: {config_path}")
    return enabled


def load_config(config_path: Path) -> Dict[str, object]:
    """Read and validate the small y3nda JSON configuration."""

    data = load_json_object(config_path)

    subdir = data.get("subdir")
    if not isinstance(subdir, str) or not subdir.strip():
        raise ValueError(f"'subdir' must be non-empty text: {config_path}")

    log_enabled = data.get("log", False)
    if not isinstance(log_enabled, bool):
        raise ValueError(f"'log' must be true or false: {config_path}")

    return data


def get_project_directory(project_root: Path, config: Dict[str, object]) -> Path:
    """Resolve the configured project directory and keep it inside the project."""

    subdir = Path(str(config["subdir"]))
    if subdir.is_absolute():
        raise ValueError("'subdir' must be a relative path")

    root = project_root.resolve()
    project_directory = (root / subdir).resolve()
    try:
        project_directory.relative_to(root)
    except ValueError as error:
        raise ValueError("'subdir' must point inside the project root") from error

    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


@contextmanager
def console_log(project_directory: Path, program_name: str, enabled: bool) -> Iterator[None]:
    """Mirror stdout and stderr to ``log.txt`` only when logging is enabled."""

    if not enabled or os.environ.get("OLLAMA_FLOW_LOG") == "1":
        yield
        return

    log_path = project_directory / "log.txt"
    if log_path.is_file() and log_path.stat().st_size:
        existing = log_path.read_bytes()
        if not existing.startswith(UTF8_BOM):
            log_path.write_bytes(UTF8_BOM + existing)
    with log_path.open("a", encoding=TEXT_OUTPUT_ENCODING) as log_file:
        if log_path.stat().st_size:
            log_file.write("\n")
        log_file.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [{program_name}]\n")
        log_file.flush()

        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout = _Tee(original_stdout, log_file)  # type: ignore[assignment]
        sys.stderr = _Tee(original_stderr, log_file)  # type: ignore[assignment]
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout, sys.stderr = original_stdout, original_stderr
            log_file.write("\n---\n")

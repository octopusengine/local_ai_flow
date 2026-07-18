"""Shared project-root console logging for command-line tools."""

from __future__ import annotations

import sys
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, TextIO


class _Tee:
    """Write console output to its original stream and to a log file."""

    def __init__(self, stream: TextIO, log_file: TextIO) -> None:
        self._stream = stream
        self._log_file = log_file

    def write(self, text: str) -> int:
        written = self._stream.write(text)
        self._log_file.write(text)
        return written

    def flush(self) -> None:
        self._stream.flush()
        self._log_file.flush()

    def isatty(self) -> bool:
        return self._stream.isatty()

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


def read_log_enabled(config_path: Path) -> bool:
    """Read the optional log switch, defaulting to enabled for CLI configurations."""

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read log configuration {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Log configuration must be a JSON object: {config_path}")
    enabled = data.get("log", True)
    if not isinstance(enabled, bool):
        raise ValueError(f"The 'log' value must be true or false: {config_path}")
    return enabled


def load_project_directory(project_root: Path) -> Path:
    """Load and create the working subdirectory named by project.json."""

    config_path = project_root / "project.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read project configuration {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Project configuration must be a JSON object: {config_path}")
    subdir = data.get("subdir")
    if not isinstance(subdir, str) or not subdir.strip():
        raise ValueError(f"The 'subdir' value must be non-empty text: {config_path}")

    configured_path = Path(subdir)
    if configured_path.is_absolute():
        raise ValueError(f"The 'subdir' value must be a relative path: {config_path}")
    project_directory = (project_root / configured_path).resolve()
    try:
        project_directory.relative_to(project_root.resolve())
    except ValueError as error:
        raise ValueError(f"The 'subdir' value must remain inside the project: {config_path}") from error

    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


@contextmanager
def project_log(project_directory: Path, cli_name: str, enabled: bool) -> Iterator[None]:
    """Mirror console output to project-root log.txt in a uniform run block."""

    if not enabled:
        yield
        return

    log_path = project_directory / "log.txt"
    with log_path.open("a", encoding="utf-8") as log_file:
        if log_path.stat().st_size:
            log_file.write("\n")
        log_file.write(f"{datetime.now():%Y-%m-%d | %H:%M} [ {cli_name}]\n")
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

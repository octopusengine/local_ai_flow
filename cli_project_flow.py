"""Manage the active working project selected by project.json.

Usage:
    python cli_project_flow.py -project project_02
    python cli_project_flow.py -clearlog
    python cli_project_flow.py -help
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lib.wrapp_cli_log import load_ollama_timeout_seconds, load_project_directory


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG_PATH = PROJECT_ROOT / "project.json"
ARCHIVE_DIRECTORY = PROJECT_ROOT / "archive"


def parse_arguments() -> argparse.Namespace:
    """Parse exactly one project-management action."""

    parser = argparse.ArgumentParser(
        description="Manage the working directory selected by project.json."
    )
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "-project",
        metavar="NAME",
        help="set and create a new project working subdirectory",
    )
    actions.add_argument(
        "-clearlog",
        action="store_true",
        help="clear the active project's log.txt file",
    )
    actions.add_argument(
        "-status",
        action="store_true",
        help="show the active project status",
    )
    actions.add_argument(
        "-archive",
        action="store_true",
        help="create a ZIP archive of the active project in ./archive",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    return parser.parse_args()


def read_project_config() -> dict[str, object]:
    """Load project.json while retaining any future project settings."""

    try:
        config = json.loads(PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Configuration file does not exist: {PROJECT_CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {PROJECT_CONFIG_PATH}: {error}") from error

    if not isinstance(config, dict):
        raise ValueError(f"Project configuration must be a JSON object: {PROJECT_CONFIG_PATH}")
    return config


def validate_project_name(name: str) -> Path:
    """Return a safe project-relative directory path."""

    name = name.strip()
    if not name:
        raise ValueError("The project name must not be empty.")

    relative_path = Path(name)
    if relative_path.is_absolute():
        raise ValueError("The project name must be a relative path inside the project.")

    project_path = (PROJECT_ROOT / relative_path).resolve()
    try:
        project_path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("The project name must remain inside the project.") from error

    if project_path == PROJECT_ROOT:
        raise ValueError("The project name must identify a project subdirectory.")
    return project_path.relative_to(PROJECT_ROOT.resolve())


def set_project(name: str) -> Path:
    """Persist the selected project directory and create it if necessary."""

    relative_path = validate_project_name(name)
    config = read_project_config()
    config["subdir"] = relative_path.as_posix()
    PROJECT_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    project_directory = load_project_directory(PROJECT_ROOT)
    return project_directory


def clear_log() -> Path:
    """Remove all entries from the active project's log file."""

    project_directory = load_project_directory(PROJECT_ROOT)
    log_path = project_directory / "log.txt"
    log_path.write_text("", encoding="utf-8")
    return log_path


def get_project_stats(project_directory: Path) -> tuple[int, int, int]:
    """Return the number of files, directories, and bytes in a project."""

    files = 0
    directories = 0
    total_bytes = 0
    for path in project_directory.rglob("*"):
        if path.is_file():
            files += 1
            total_bytes += path.stat().st_size
        elif path.is_dir():
            directories += 1
    return files, directories, total_bytes


def show_status() -> None:
    """Print a compact summary of the active project."""

    project_directory = load_project_directory(PROJECT_ROOT)
    log_path = project_directory / "log.txt"
    files, directories, total_bytes = get_project_stats(project_directory)
    log_size = log_path.stat().st_size if log_path.is_file() else 0
    ollama_timeout_seconds = load_ollama_timeout_seconds(PROJECT_ROOT)
    print(f"Active project: {project_directory.name}")
    print(f"Path: {project_directory}")
    print(f"Ollama response timeout: {ollama_timeout_seconds:g} s")
    print(f"Files: {files}; subdirectories: {directories}; size: {total_bytes:,} B")
    print(f"Log: {log_path} ({log_size:,} B)")


def archive_project() -> Path:
    """Create a timestamped ZIP archive of the active project."""

    project_directory = load_project_directory(PROJECT_ROOT)
    ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIRECTORY / f"{project_directory.name}_{datetime.now():%y%m%d_%H%M}.zip"
    if archive_path.exists():
        raise FileExistsError(
            f"Archive already exists: {archive_path}. Wait a minute or rename it first."
        )

    files = sorted(path for path in project_directory.rglob("*") if path.is_file())
    with ZipFile(archive_path, mode="x", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(project_directory.parent))
    return archive_path


def main() -> int:
    """Run one project-management operation."""

    try:
        arguments = parse_arguments()
        if arguments.project is not None:
            project_directory = set_project(arguments.project)
            print(f"Active project set: {project_directory}")
        elif arguments.clearlog:
            log_path = clear_log()
            print(f"Log cleared: {log_path}")
        elif arguments.status:
            show_status()
        else:
            archive_path = archive_project()
            print(f"Archive created: {archive_path}")
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

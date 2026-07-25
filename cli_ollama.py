"""Run batch requests against local Ollama from the command line."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_project_config,
    read_log_enabled,
)
from lib.wrapp_ffmpeg import __version__ as WRAPP_FFMPEG_VERSION
from lib.wrapp_log import __version__ as WRAPP_LOG_VERSION
from lib.wrapp_ollama import __version__ as WRAPP_OLLAMA_VERSION
from lib.wrapp_piper import __version__ as WRAPP_PIPER_VERSION
from lib.wrapp_system import print_system_info
from lib.wrapp_system import __version__ as WRAPP_SYSTEM_VERSION
from lib.wrapp_terminal import Terminal
from lib.wrapp_terminal import __version__ as WRAPP_TERMINAL_VERSION
from lib.wrapp_whisper import __version__ as WRAPP_WHISPER_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_FILENAME = "cli_ollama.json"
CONFIG_FILE = PROJECT_DIR / "lib" / "config.json"
__version__ = "0.2"
MODULE_VERSIONS = (
    ("wrapp_log", WRAPP_LOG_VERSION),
    ("wrapp_ffmpeg", WRAPP_FFMPEG_VERSION),
    ("wrapp_ollama", WRAPP_OLLAMA_VERSION),
    ("wrapp_piper", WRAPP_PIPER_VERSION),
    ("wrapp_terminal", WRAPP_TERMINAL_VERSION),
    ("wrapp_system", WRAPP_SYSTEM_VERSION),
    ("wrapp_whisper", WRAPP_WHISPER_VERSION),
)
VERSION_LABEL_WIDTH = max(len(name) for name, _version in MODULE_VERSIONS) + 1


class VersionAction(argparse.Action):
    """Print a colorized, aligned version overview."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, nargs=0, default=default, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        terminal = Terminal()
        print(terminal.color("y", f"cli_ollama.py {__version__} (Python 3.10+)"))
        for name, version in MODULE_VERSIONS:
            label = f"{name}:".ljust(VERSION_LABEL_WIDTH)
            print(f"{terminal.color('g', label)} {version}")
        parser.exit()


def parse_arguments() -> argparse.Namespace:
    """Return input JSON and an optional output text-file path."""
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    parser = argparse.ArgumentParser(description="Process requests from a JSON file through Ollama.")
    parser.add_argument(
        "-v",
        "--ver",
        "--version",
        action=VersionAction,
        help="show cli_ollama.py and all wrapper versions",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        help="input JSON file in the active project directory (default: cli_ollama.json)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        type=Path,
        help="output TXT file in the active project directory (default: cli_out_yymmdd_hhmm.txt)",
    )
    parser.add_argument(
        "-s",
        "--system",
        "--status",
        dest="status",
        action="store_true",
        help="show project.json and local system information",
    )
    return parser.parse_args()


def resolve_project_file(path: Path | None, project_directory: Path, default_name: str, label: str) -> Path:
    """Resolve a file name in the active project directory."""

    candidate = path or Path(default_name)
    resolved_directory = project_directory.resolve()
    resolved_path = candidate.resolve() if candidate.is_absolute() else (resolved_directory / candidate).resolve()
    try:
        resolved_path.relative_to(resolved_directory)
    except ValueError as error:
        raise ValueError(f"The {label} must be inside the active project directory.") from error
    if resolved_path.parent != resolved_directory:
        raise ValueError(f"The {label} must be directly in the active project directory.")
    return resolved_path


def print_status(project_directory: Path) -> None:
    """Print the shared project configuration and local system overview."""

    terminal = Terminal()
    config = load_project_config(PROJECT_DIR)
    print(terminal.color("y", "Project status"))
    print(
        "{0} {1}".format(
            terminal.color("g", "Configuration:"),
            json.dumps(config, ensure_ascii=False),
        )
    )
    print("{0} {1}".format(terminal.color("g", "Project directory:"), project_directory))
    print()
    print_system_info(project_directory)


def main() -> int:
    arguments = parse_arguments()
    try:
        project_directory = get_project_directory(PROJECT_DIR, load_project_config(PROJECT_DIR))
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    if arguments.status:
        try:
            print_status(project_directory)
        except ValueError as error:
            print(f"ERROR: {error}")
            return 1
        return 0

    try:
        input_path = resolve_project_file(
            arguments.input_file,
            project_directory,
            DEFAULT_INPUT_FILENAME,
            "input JSON file",
        )
        output_path = resolve_project_file(
            arguments.output_file,
            project_directory,
            f"cli_out_{datetime.now():%y%m%d_%H%M}.txt",
            "output TXT file",
        )
        log_enabled = read_log_enabled(input_path)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    with console_log(project_directory, "cli_ollama.py", log_enabled):
        from lib.wrapp_ollama import ollama_api

        app = ollama_api(config_path=CONFIG_FILE)
        return app.run(
            input_path=input_path,
            output_path=output_path,
            compact_report=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())

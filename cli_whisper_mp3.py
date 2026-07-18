"""Transcribe the first MP3 file from the project directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from lib.wrapp_cli_log import project_log, read_log_enabled
from lib.wrapp_whisper import load_project_directory, main


PROJECT_ROOT = Path(__file__).resolve().parent
CLI_CONFIG_PATH = PROJECT_ROOT / "cli_whisper_mp3.json"


# Optional per-test overrides. Set to None to use lib/whisper.json.
debug = None
language = "cs"  # Use "auto" for automatic language detection.
model = "base"


def parse_arguments() -> argparse.Namespace:
    """Parse the command line solely to provide CLI help."""

    parser = argparse.ArgumentParser(
        description=(
            "Transcribe a selected MP3 file, or the first MP3 file when no argument is given, "
            "from the project directory selected by project.json. The transcript is saved with a .txt suffix."
        )
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        help="optional MP3 file from the project directory root",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    try:
        project_directory = load_project_directory()
        log_enabled = read_log_enabled(CLI_CONFIG_PATH)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1) from None

    with project_log(project_directory, "cli_whisper_mp3.py", log_enabled):
        main(
            "mp3",
            "cli_whisper_mp3",
            debug=debug,
            language=language,
            model=model,
            source_file=(
                arguments.input_file
                if arguments.input_file is None or arguments.input_file.is_absolute()
                else project_directory / arguments.input_file
            ),
        )

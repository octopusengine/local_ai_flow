"""Run batch requests against local Ollama from the command line."""

import argparse
from datetime import datetime
from pathlib import Path

from lib.wrapp_cli_log import load_project_directory, project_log, read_log_enabled
from lib.wrapp_ollama import ollama_api


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_FILE = PROJECT_DIR / "cli_input.json"
CONFIG_FILE = PROJECT_DIR / "lib" / "config.json"


def parse_arguments() -> argparse.Namespace:
    """Return input JSON and an optional output text-file path."""
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    parser = argparse.ArgumentParser(description="Process requests from a JSON file through Ollama.")
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="input JSON file (default: cli_input.json)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        type=Path,
        default=PROJECT_DIR / f"cli_out_{timestamp}.txt",
        help="output TXT file (default: cli_out_yymmdd_hhmm.txt)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        project_directory = load_project_directory(PROJECT_DIR)
        log_enabled = read_log_enabled(arguments.input_file)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    with project_log(project_directory, "cli_ollama.py", log_enabled):
        app = ollama_api(config_path=CONFIG_FILE)
        return app.run(
            input_path=arguments.input_file,
            output_path=arguments.output_file,
            compact_report=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())

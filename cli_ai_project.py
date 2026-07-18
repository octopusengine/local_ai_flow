"""Run a project-root audio or image workflow through the local AI CLI tools."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from lib.wrapp_cli_log import load_project_directory, project_log, read_log_enabled


PROJECT_ROOT = Path(__file__).resolve().parent
CLI_CONFIG_PATH = PROJECT_ROOT / "cli_ai_project.json"
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def parse_arguments() -> argparse.Namespace:
    """Parse the input source and optional translation and speech stages."""

    parser = argparse.ArgumentParser(
        description=(
            "Process a recording, MP3 file, or image from the project directory root: "
            "create text, optionally translate it, and optionally create narrated MP3 output."
        )
    )
    parser.add_argument("source_type", choices=("record", "audio", "image"))
    parser.add_argument(
        "source_file",
        nargs="?",
        type=Path,
        help="MP3 file for audio or image file for image; record does not accept a file",
    )
    parser.add_argument(
        "--translate",
        nargs="?",
        const="c2e",
        choices=("c2e", "e2c"),
        help="optionally translate text; use c2e when no direction is supplied",
    )
    parser.add_argument(
        "--speech",
        nargs="?",
        const="cz",
        choices=("cz", "en"),
        help="optionally create an MP3; use the Czech voice when no voice is supplied",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    return parser.parse_args()


def project_root_file(value: Path, project_directory: Path, extensions: set[str]) -> Path:
    """Return a validated input file directly inside the project directory root."""

    path = value if value.is_absolute() else project_directory / value
    path = path.resolve()
    try:
        path.relative_to(project_directory)
    except ValueError as error:
        raise ValueError("The input file must be inside the project directory from project.json.") from error
    if path.parent != project_directory:
        raise ValueError("The input file must be directly in the project directory root.")
    if path.suffix.casefold() not in extensions:
        accepted = ", ".join(sorted(extensions))
        raise ValueError(f"The input file must have one of these extensions: {accepted}.")
    if not path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    return path


def run_cli(script_name: str, arguments: list[str]) -> None:
    """Run one project CLI and fail the workflow if that stage fails."""

    command = [sys.executable, str(PROJECT_ROOT / script_name), *arguments]
    print(f"Running {script_name}: {' '.join(arguments) if arguments else '(no arguments)'}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"{script_name} exited with code {completed.returncode}.")


def run_workflow(arguments: argparse.Namespace, project_directory: Path) -> int:
    """Execute the requested recognition, translation, and speech stages."""

    if arguments.source_type == "record":
        if arguments.source_file is not None:
            raise ValueError("Do not provide an input file for record mode.")
        run_cli("cli_record_mp3.py", [])
        source_path = project_directory / "record.mp3"
        if not source_path.is_file():
            raise FileNotFoundError(f"Recording was not created: {source_path}")
        run_cli("cli_whisper_mp3.py", [source_path.name])
        text_path = source_path.with_suffix(".txt")
    elif arguments.source_type == "audio":
        if arguments.source_file is None:
            raise ValueError("Provide an MP3 file for audio mode.")
        source_path = project_root_file(arguments.source_file, project_directory, {".mp3"})
        run_cli("cli_whisper_mp3.py", [source_path.name])
        text_path = source_path.with_suffix(".txt")
    else:
        if arguments.source_file is None:
            raise ValueError("Provide an image file for image mode.")
        source_path = project_root_file(arguments.source_file, project_directory, IMAGE_EXTENSIONS)
        run_cli("cli_ocr_ollama.py", [source_path.name])
        text_path = source_path.with_suffix(".txt")

    if not text_path.is_file():
        raise FileNotFoundError(f"Text output was not created: {text_path}")
    print(f"Text output: {text_path}")

    if arguments.translate:
        run_cli("cli_translate.py", [arguments.translate, text_path.name])
        text_path = project_directory / "translate.txt"
        if not text_path.is_file():
            raise FileNotFoundError(f"Translation was not created: {text_path}")
        print(f"Translation: {text_path}")

    if arguments.speech:
        run_cli("cli_speech_mp3.py", [arguments.speech, text_path.name])
        speech_path = text_path.with_suffix(".mp3")
        if not speech_path.is_file():
            raise FileNotFoundError(f"Narrated output was not created: {speech_path}")
        print(f"Narrated output: {speech_path}")
    return 0


def main() -> int:
    """Run the selected AI workflow with uniform project logging."""

    arguments = parse_arguments()
    try:
        project_directory = load_project_directory(PROJECT_ROOT)
        log_enabled = read_log_enabled(CLI_CONFIG_PATH)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with project_log(project_directory, "cli_ai_project.py", log_enabled):
        try:
            return run_workflow(arguments, project_directory)
        except (FileNotFoundError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

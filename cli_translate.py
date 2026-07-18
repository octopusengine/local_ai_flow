"""Translate one text through local Ollama and save the translation."""

import argparse
import json
import tempfile
from pathlib import Path

from lib.wrapp_cli_log import project_log, read_log_enabled
from lib.wrapp_ollama import ollama_api


PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_CONFIG_FILE = PROJECT_DIR / "project.json"
OLLAMA_CONFIG_FILE = PROJECT_DIR / "lib" / "config.json"
TRANSLATE_CONFIG_FILE = PROJECT_DIR / "cli_translate.json"

INSTRUCTIONS = {
    "c2e": "Translate from Czech to English. Return only the translation.",
    "e2c": "Translate from English to Czech. Return only the translation.",
}
DEFAULT_DIRECTION = "c2e"


def load_project_directory() -> Path:
    """Load the working subdirectory configured in project.json."""

    try:
        data = json.loads(PROJECT_CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Configuration file does not exist: {PROJECT_CONFIG_FILE}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {PROJECT_CONFIG_FILE}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be an object: {PROJECT_CONFIG_FILE}")

    subdir = data.get("subdir")
    if not isinstance(subdir, str) or not subdir.strip():
        raise ValueError("The 'subdir' setting in project.json must be non-empty text.")

    configured_path = Path(subdir)
    if configured_path.is_absolute():
        raise ValueError("The 'subdir' setting in project.json must be a relative path.")

    project_directory = (PROJECT_DIR / configured_path).resolve()
    try:
        project_directory.relative_to(PROJECT_DIR)
    except ValueError as error:
        raise ValueError("The 'subdir' setting in project.json must remain inside the project.") from error

    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


def parse_arguments() -> tuple[str, str | None]:
    """Parse optional c2e/e2c direction and a text or file argument."""

    parser = argparse.ArgumentParser(
        description=(
            "Translate text between Czech and English through Ollama in the project directory "
            "selected by project.json. The default direction is c2e."
        )
    )
    parser.add_argument("arguments", nargs="*", metavar="[c2e|e2c] [text|file.txt]")
    parser.add_argument("-help", action="help", help="show this help message and exit")
    values = parser.parse_args().arguments

    if not values:
        return DEFAULT_DIRECTION, None
    if len(values) == 1:
        if values[0].casefold() in INSTRUCTIONS:
            return values[0].casefold(), None
        return DEFAULT_DIRECTION, values[0]
    if len(values) == 2 and values[0].casefold() in INSTRUCTIONS:
        return values[0].casefold(), values[1]
    parser.error("usage: cli_translate.py [c2e|e2c] [text|file.txt]")
    raise AssertionError("argparse parser.error always exits")


def read_translate_config(path: Path) -> dict:
    """Load and validate translator settings."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read configuration {path.name}: {error}") from error

    if not isinstance(config, dict):
        raise ValueError(f"Configuration {path.name} must be a JSON object.")
    if not isinstance(config.get("model"), str) or not config["model"].strip():
        raise ValueError('The "model" item must be non-empty text.')
    if not isinstance(config.get("debug"), bool):
        raise ValueError('The "debug" item must be true or false.')
    if not isinstance(config.get("think"), bool):
        raise ValueError('The "think" item must be true or false.')
    temperature = config.get("temperature")
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        raise ValueError('The "temperature" item must be a number.')
    if not isinstance(config.get("input_file"), str) or not config["input_file"].strip():
        raise ValueError('The "input_file" item must be non-empty text.')
    if not isinstance(config.get("output_file"), str) or not config["output_file"].strip():
        raise ValueError('The "output_file" item must be non-empty text.')
    if not isinstance(config.get("log"), bool):
        raise ValueError('The "log" item must be true or false.')
    return config


def read_prompt(
    prompt_or_file: str | None, default_input_file: str, project_directory: Path
) -> str:
    """Return text from an argument or the specified UTF-8 file."""
    if prompt_or_file is None:
        input_path = project_directory / default_input_file
    else:
        input_path = Path(prompt_or_file)
        candidate_path = input_path if input_path.is_absolute() else project_directory / input_path
        if candidate_path.is_file():
            input_path = candidate_path.resolve()
            try:
                input_path.relative_to(project_directory)
            except ValueError as error:
                raise ValueError("The input file must be inside the project directory from project.json.") from error
            if input_path.parent != project_directory:
                raise ValueError("The input file must be directly in the project directory root.")
        else:
            if input_path.suffix.lower() == ".txt":
                raise ValueError(f"Input file does not exist: {candidate_path}")
            return prompt_or_file

    input_path = input_path.resolve()
    try:
        input_path.relative_to(project_directory)
    except ValueError as error:
        raise ValueError("The input file must be inside the project directory from project.json.") from error
    if input_path.parent != project_directory:
        raise ValueError("The input file must be directly in the project directory root.")

    try:
        prompt = input_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not read input file {input_path}: {error}") from error
    if not prompt.strip():
        raise ValueError(f"Input file {input_path} is empty.")
    return prompt


def create_input_file(path: Path, config: dict, direction: str, prompt: str) -> None:
    """Write a request in the format expected by the Ollama wrapper."""
    request = {
        "model": config["model"],
        "debug": config["debug"],
        "think": config["think"],
        "temperature": config["temperature"],
        "instruction": INSTRUCTIONS[direction],
        "prompt": prompt,
        "queries": [{}],
    }
    path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_output_path(filename: str, project_directory: Path) -> Path:
    """Return a safe output file directly in the project directory root."""

    output_path = project_directory / filename
    output_path = output_path.resolve()
    try:
        output_path.relative_to(project_directory)
    except ValueError as error:
        raise ValueError("The output file must be inside the project directory from project.json.") from error
    if output_path.parent != project_directory:
        raise ValueError("The output file must be directly in the project directory root.")
    return output_path


def main() -> int:
    direction, prompt_or_file = parse_arguments()
    try:
        project_directory = load_project_directory()
        log_enabled = read_log_enabled(TRANSLATE_CONFIG_FILE)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    with project_log(project_directory, "cli_translate.py", log_enabled):
        try:
            config = read_translate_config(TRANSLATE_CONFIG_FILE)
            prompt = read_prompt(prompt_or_file, config["input_file"], project_directory)
        except ValueError as error:
            print(f"ERROR: {error}")
            return 2

        try:
            output_path = resolve_output_path(config["output_file"], project_directory)
        except ValueError as error:
            print(f"ERROR: {error}")
            return 2

        with tempfile.TemporaryDirectory(
            prefix="cli_translate_", dir=project_directory
        ) as temporary_directory:
            input_path = Path(temporary_directory) / "translate_input.json"
            report_path = Path(temporary_directory) / "ollama_report.txt"
            response_path = Path(temporary_directory) / "translate.txt"
            create_input_file(input_path, config, direction, prompt)
            app = ollama_api(config_path=OLLAMA_CONFIG_FILE)
            exit_code = app.run(
                input_path=input_path,
                output_path=report_path,
                response_path=response_path,
            )
            if exit_code == 0:
                response_path.replace(output_path)
                translation = output_path.read_text(encoding="utf-8")
                print(f"Translation saved: {output_path}")
                print("Translation:")
                print(translation)
            return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

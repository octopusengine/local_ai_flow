"""Standalone image OCR CLI using local Ollama."""

import argparse
import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from lib.wrapp_cli_log import (
    load_ollama_timeout_seconds,
    project_log,
    read_log_enabled,
)


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG_FILE = PROJECT_ROOT / "project.json"
CONFIG_FILE = PROJECT_ROOT / "cli_ocr_ollama.json"
DEFAULT_PROMPT = "Extract all text from this image. Return only the recognized text, preserving line breaks."


def report(message: str) -> None:
    """Print a timestamped processing update."""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def debug(message: str, enabled: bool) -> None:
    if enabled:
        report(f"DEBUG: {message}")


def load_project_directory() -> Path:
    """Load the working subdirectory configured in project.json."""

    try:
        project = json.loads(PROJECT_CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Configuration file was not found: {PROJECT_CONFIG_FILE}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {PROJECT_CONFIG_FILE}: {error}") from error

    if not isinstance(project, dict):
        raise ValueError(f"Configuration root must be an object: {PROJECT_CONFIG_FILE}")

    subdir = project.get("subdir")
    if not isinstance(subdir, str) or not subdir.strip():
        raise ValueError("project.json is missing a non-empty 'subdir' value.")

    configured_path = Path(subdir)
    if configured_path.is_absolute():
        raise ValueError("The 'subdir' value in project.json must be a relative path.")

    project_directory = (PROJECT_ROOT / configured_path).resolve()
    try:
        project_directory.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("The 'subdir' value in project.json must remain inside the project.") from error

    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


def load_config() -> dict:
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Configuration file was not found: {CONFIG_FILE.resolve()}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {CONFIG_FILE}: {error}") from error

    for name in ("model", "default_input_file", "default_output_file"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"The required non-empty value {name!r} is missing from {CONFIG_FILE}.")
    if "options" in config and not isinstance(config["options"], dict):
        raise ValueError(f"The 'options' value in {CONFIG_FILE} must be a JSON object.")
    if "debug" in config and not isinstance(config["debug"], bool):
        raise ValueError(f"The 'debug' value in {CONFIG_FILE} must be true or false.")
    if not isinstance(config.get("log"), bool):
        raise ValueError(f"The 'log' value in {CONFIG_FILE} must be true or false.")
    if "image_extensions" in config and (
        not isinstance(config["image_extensions"], list)
        or not all(isinstance(extension, str) and extension.startswith(".") for extension in config["image_extensions"])
    ):
        raise ValueError(f"The 'image_extensions' value in {CONFIG_FILE} must be a list of image extensions.")
    return config


def resolve_working_file(filename: str, working_directory: Path, description: str) -> Path:
    """Resolve a filename directly in the working directory from project.json."""
    file_path = Path(filename)
    if file_path.is_absolute() or file_path.name != filename:
        raise ValueError(f"The {description} must be a filename without a path.")
    return working_directory / file_path


def run_ocr(
    input_file_override: str | None = None,
    output_file_override: str | None = None,
) -> int:
    report("Starting OCR through local Ollama.")
    report(f"Loading settings from: {CONFIG_FILE.resolve()}")
    try:
        config = load_config()
        ocr_directory = load_project_directory()
        ollama_timeout_seconds = load_ollama_timeout_seconds(PROJECT_ROOT)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    debug_enabled = config.get("debug", False)
    report(f"Configured model: {config['model']}")
    report(f"Ollama response timeout: {ollama_timeout_seconds:g} s")
    debug(f"Model parameters: {json.dumps(config.get('options', {}), ensure_ascii=False)}", debug_enabled)

    input_file = Path(input_file_override or config["default_input_file"])
    input_image = input_file if input_file.is_absolute() else ocr_directory / input_file
    try:
        output_text = resolve_working_file(
            output_file_override or str(config["default_output_file"]),
            ocr_directory,
            "output file",
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report(f"OCR working directory: {ocr_directory.resolve()}")
    ocr_directory.mkdir(parents=True, exist_ok=True)

    report(f"Checking input image: {input_image.resolve()}")
    if not input_image.is_file():
        print(f"ERROR: Input image was not found: {input_image.resolve()}", file=sys.stderr)
        return 1

    image_bytes = input_image.read_bytes()
    report(f"Loading image ({len(image_bytes):,} bytes).")
    report("Converting the image to the format required by Ollama.")
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": config["model"],
        "prompt": config.get("prompt", DEFAULT_PROMPT),
        "images": [image_base64],
        "stream": False,
        "options": config.get("options", {}),
    }
    ollama_url = config.get("ollama_url", "http://localhost:11434/api/generate")
    version_url = ollama_url.removesuffix("/api/generate") + "/api/version"

    try:
        report(f"Checking that Ollama is running: {version_url}")
        version_response = requests.get(version_url, timeout=10)
        version_response.raise_for_status()
        version = version_response.json().get("version", "unknown version")
        report(f"Ollama responded (version {version}).")

        report(f"Loading model {config['model']} and sending the OCR request.")
        debug(f"API URL: {ollama_url}", debug_enabled)
        debug(f"OCR prompt length: {len(payload['prompt'])} characters", debug_enabled)
        debug("The image is attached as Base64; its content is not written to the output.", debug_enabled)
        scan_started_at = datetime.now()
        evaluation_started_at = time.monotonic()
        response = requests.post(
            ollama_url,
            json=payload,
            timeout=(10, ollama_timeout_seconds),
        )
        evaluation_seconds = time.monotonic() - evaluation_started_at
        debug(f"API responded with HTTP {response.status_code}.", debug_enabled)
        response.raise_for_status()
        report("Ollama completed OCR; processing the response.")
        result = response.json()
    except requests.RequestException as error:
        print(f"ERROR: Could not connect to Ollama: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"ERROR: Ollama did not return valid JSON: {error}", file=sys.stderr)
        return 1

    text = result.get("response")
    if not isinstance(text, str):
        print(f"ERROR: The response does not contain OCR text: {result}", file=sys.stderr)
        return 1

    report(f"Recognized text has {len(text)} characters.")
    report(f"Model used: {config['model']}")
    report(f"Model parameters: {json.dumps(config.get('options', {}), ensure_ascii=False)}")
    report(f"Scan date: {scan_started_at:%Y-%m-%d %H:%M:%S}")
    report(f"Evaluation duration: {evaluation_seconds:.1f} s")
    report(f"Saving OCR output to: {output_text.resolve()}")
    output_text.write_text(text, encoding="utf-8")
    report("Done. Recognized text was saved successfully.")
    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recognize text from images using the model configured in cli_ocr_ollama.json. "
            "Relative image names, the configured default_input_file, and -all are resolved in "
            "the working directory selected by the 'subdir' value in project.json. A final "
            ".txt argument overrides default_output_file from cli_ocr_ollama.json."
        ),
        epilog=(
            "The OCR text file is saved in the same working directory. "
            "Example: cli_ocr_ollama.py avatar_py.jpg output.txt"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="image_or_output",
        help="optional image and a final optional .txt output filename",
    )
    parser.add_argument(
        "-all",
        action="store_true",
        help="process all supported images in the working directory from project.json",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    arguments = parser.parse_args()

    files = list(arguments.files)
    arguments.output_file = None
    if files and Path(files[-1]).suffix.lower() == ".txt":
        arguments.output_file = files.pop()
    if len(files) > 1:
        parser.error("provide at most one image and an optional final .txt output file")
    arguments.image = files[0] if files else None
    return arguments


def process_all_images() -> int:
    try:
        config = load_config()
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        ocr_directory = load_project_directory()
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    extensions = {extension.lower() for extension in config.get("image_extensions", [])}
    images = sorted(
        path for path in ocr_directory.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    ) if ocr_directory.is_dir() else []

    if not images:
        print(f"No images were found in {ocr_directory.resolve()}.")
        return 0

    print(f"Images found for processing: {len(images)}", flush=True)
    failed = 0
    for index, image in enumerate(images, start=1):
        print(f"\n{'=' * 60}\n[{index}/{len(images)}] Processing: {image.name}", flush=True)
        failed += run_ocr(image.name, f"{image.stem}.txt") != 0

    print(f"\nBatch complete. Succeeded: {len(images) - failed}; failed: {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    arguments = parse_arguments()
    try:
        project_directory = load_project_directory()
        log_enabled = read_log_enabled(CONFIG_FILE)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    with project_log(project_directory, "cli_ocr_ollama.py", log_enabled):
        if arguments.all and (arguments.image or arguments.output_file):
            print("ERROR: Use -all without an image name or output file.", file=sys.stderr)
            raise SystemExit(2)
        if arguments.all:
            raise SystemExit(process_all_images())
        raise SystemExit(run_ocr(arguments.image, arguments.output_file))

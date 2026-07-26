"""Standalone image OCR CLI using local Ollama."""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from lib.wrapp_img import (
    image_bytes_to_ollama_base64,
    resolve_image_path,
    resolve_project_file,
    resize_image_for_request,
)
from lib.wrapp_log import console_log, get_project_directory, load_project_config, read_log_enabled
from lib.wrapp_ollama import get_ollama_endpoint_urls, load_ollama_timeout_seconds
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_ROOT / "cli_ocr_ollama.json"
DEFAULT_PROMPT = "Extract all text from this image. Return only the recognized text, preserving line breaks."


def report(message: str) -> None:
    """Print a timestamped processing update."""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def debug(message: str, enabled: bool) -> None:
    if enabled:
        report(f"DEBUG: {message}")


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
    max_image_size = config.get("max_image_size")
    if (
        not isinstance(max_image_size, int)
        or isinstance(max_image_size, bool)
        or max_image_size <= 0
    ):
        raise ValueError(f"The 'max_image_size' value in {CONFIG_FILE} must be a positive whole number.")
    return config


def run_ocr(
    input_file_override: str | None = None,
    output_file_override: str | None = None,
    *,
    log_enabled: bool = False,
) -> int:
    report("Starting OCR through local Ollama.")
    report(f"Loading settings from: {CONFIG_FILE.resolve()}")
    try:
        config = load_config()
        ocr_directory = get_project_directory(PROJECT_ROOT, load_project_config(PROJECT_ROOT))
        ollama_timeout_seconds = load_ollama_timeout_seconds(PROJECT_ROOT)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    debug_enabled = config.get("debug", False)
    report(f"Configured model: {config['model']}")
    report(f"Ollama response timeout: {ollama_timeout_seconds:g} s")
    debug(f"Model parameters: {json.dumps(config.get('options', {}), ensure_ascii=False)}", debug_enabled)

    try:
        supported_extensions = {str(extension) for extension in config.get("image_extensions", [])}
        input_image = resolve_image_path(
            input_file_override,
            ocr_directory,
            str(config["default_input_file"]),
            supported_extensions,
        )
        output_text = resolve_project_file(
            output_file_override or str(config["default_output_file"]),
            ocr_directory,
            "output file",
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report(f"OCR working directory: {ocr_directory.resolve()}")
    ocr_directory.mkdir(parents=True, exist_ok=True)

    try:
        image_bytes = input_image.read_bytes()
        request_image_bytes, original_size, request_size = resize_image_for_request(
            image_bytes,
            int(config["max_image_size"]),
        )
        if log_enabled:
            binary_log_path = input_image.with_suffix(".bin")
            binary_log_path.write_bytes(request_image_bytes)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: Could not prepare input image: {error}", file=sys.stderr)
        return 1

    report(f"Loading image ({len(image_bytes):,} bytes, {original_size[0]}x{original_size[1]} px).")
    if request_size != original_size:
        report(
            f"Image resized for Ollama: {request_size[0]}x{request_size[1]} px "
            f"({len(request_image_bytes):,} bytes; max side {config['max_image_size']} px)."
        )
    else:
        report(f"Image size is within the configured {config['max_image_size']} px limit; original is used.")
    if log_enabled:
        report(f"Ollama image bytes saved: {binary_log_path.resolve()}")
    report("Converting the image to the format required by Ollama.")
    image_base64 = image_bytes_to_ollama_base64(request_image_bytes)
    payload = {
        "model": config["model"],
        "prompt": config.get("prompt", DEFAULT_PROMPT),
        "images": [image_base64],
        "stream": False,
        "options": config.get("options", {}),
    }
    configured_ollama_url = str(config.get("ollama_url", "http://localhost:11434/api/generate"))
    version_url, ollama_url, _ = get_ollama_endpoint_urls(configured_ollama_url)

    try:
        report(f"Checking that Ollama is running: {version_url}")
        version_response = requests.get(version_url, timeout=10)
        version_response.raise_for_status()
        version = version_response.json().get("version", "unknown version")
        report(f"Ollama responded (version {version}).")

        report(f"Loading model {config['model']} and sending the OCR request.")
        debug(f"API URL: {ollama_url}", debug_enabled)
        debug(f"OCR prompt length: {len(payload['prompt'])} characters", debug_enabled)
        debug("The image is attached as Base64 in the Ollama request.", debug_enabled)
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
    print("Recognized text:", flush=True)
    Terminal().print("g", text)
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
            "the working directory selected by the 'subdir' value in project.json. Use --in and "
            "--out to override the input and output file from cli_ocr_ollama.json."
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
        "--in",
        "--input",
        dest="input_file",
        metavar="IMAGE",
        help="input image in the active project directory; overrides default_input_file",
    )
    parser.add_argument(
        "--out",
        "--output",
        dest="output_file",
        metavar="TEXT",
        help="output text file in the active project directory; overrides default_output_file",
    )
    parser.add_argument(
        "-all",
        action="store_true",
        help="process all supported images in the working directory from project.json",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    arguments = parser.parse_args()

    files = list(arguments.files)
    positional_output_file = None
    if files and Path(files[-1]).suffix.lower() == ".txt":
        positional_output_file = files.pop()
    if len(files) > 1:
        parser.error("provide at most one image and an optional final .txt output file")
    positional_image = files[0] if files else None
    if arguments.input_file and positional_image:
        parser.error("use either --in or a positional image, not both")
    if arguments.output_file and positional_output_file:
        parser.error("use either --out or a positional output file, not both")
    arguments.image = arguments.input_file or positional_image
    arguments.output_file = arguments.output_file or positional_output_file
    return arguments


def process_all_images(*, log_enabled: bool) -> int:
    try:
        config = load_config()
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        ocr_directory = get_project_directory(PROJECT_ROOT, load_project_config(PROJECT_ROOT))
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
        failed += run_ocr(image.name, f"{image.stem}.txt", log_enabled=log_enabled) != 0

    print(f"\nBatch complete. Succeeded: {len(images) - failed}; failed: {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    arguments = parse_arguments()
    try:
        project_directory = get_project_directory(PROJECT_ROOT, load_project_config(PROJECT_ROOT))
        log_enabled = read_log_enabled(CONFIG_FILE)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    with console_log(project_directory, "cli_ocr_ollama.py", log_enabled):
        if arguments.all and (arguments.image or arguments.output_file):
            print("ERROR: Use -all without an image name or output file.", file=sys.stderr)
            raise SystemExit(2)
        if arguments.all:
            raise SystemExit(process_all_images(log_enabled=log_enabled))
        raise SystemExit(run_ocr(arguments.image, arguments.output_file, log_enabled=log_enabled))

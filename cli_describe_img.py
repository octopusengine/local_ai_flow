"""Describe one PNG image through local Ollama and save the result."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests

from lib.wrapp_cli_log import (
    load_ollama_timeout_seconds,
    load_project_directory,
    project_log,
    read_log_enabled,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_ROOT / "cli_describe_img.json"
SUPPORTED_INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def report(message: str) -> None:
    """Print a timestamped processing update."""

    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def load_config() -> dict[str, object]:
    """Load and validate the image-description configuration."""

    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read configuration {CONFIG_FILE}: {error}") from error

    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a JSON object: {CONFIG_FILE}")
    for name in ("model", "prompt", "default_image", "output_file"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"The {name!r} value must be non-empty text: {CONFIG_FILE}")
    max_image_size = config.get("max_image_size")
    if (
        not isinstance(max_image_size, int)
        or isinstance(max_image_size, bool)
        or max_image_size <= 0
    ):
        raise ValueError(f"The 'max_image_size' value must be a positive whole number: {CONFIG_FILE}")
    if "ollama_url" in config and (
        not isinstance(config["ollama_url"], str) or not config["ollama_url"].strip()
    ):
        raise ValueError(f"The 'ollama_url' value must be non-empty text: {CONFIG_FILE}")
    for name in ("think", "verbose"):
        if name in config and not isinstance(config[name], bool):
            raise ValueError(f"The {name!r} value must be true or false: {CONFIG_FILE}")
    if "options" in config and not isinstance(config["options"], dict):
        raise ValueError(f"The 'options' value must be a JSON object: {CONFIG_FILE}")
    return config


def resolve_project_file(filename: str, project_directory: Path, description: str) -> Path:
    """Return a file path directly in the configured work directory."""

    resolved_directory = project_directory.resolve()
    file_path = (resolved_directory / filename).resolve()
    try:
        file_path.relative_to(resolved_directory)
    except ValueError as error:
        raise ValueError(f"The {description} must be inside the project directory from project.json.") from error
    if file_path.parent != resolved_directory:
        raise ValueError(f"The {description} must be directly in the project directory root.")
    return file_path


def resolve_image_path(
    image_argument: str | None, project_directory: Path, default_image_name: str
) -> Path:
    """Choose the requested, default, or first PNG image in the work directory."""

    resolved_directory = project_directory.resolve()
    if image_argument:
        candidate = Path(image_argument)
        image_path = candidate.resolve() if candidate.is_absolute() else (resolved_directory / candidate).resolve()
        try:
            image_path.relative_to(resolved_directory)
        except ValueError as error:
            raise ValueError("The input image must be inside the project directory from project.json.") from error
        if image_path.parent != resolved_directory:
            raise ValueError("The input image must be directly in the project directory root.")
        if image_path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            extensions = ", ".join(sorted(SUPPORTED_INPUT_EXTENSIONS))
            raise ValueError(f"The input image must use one of these extensions: {extensions}.")
        if not image_path.is_file():
            raise ValueError(f"Input image was not found: {image_path}")
        return image_path

    default_image = resolve_project_file(default_image_name, resolved_directory, "default image")
    if default_image.is_file():
        return default_image

    images = sorted(
        path for path in resolved_directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".png"
    )
    if not images:
        raise ValueError(
            f"No PNG image was found in {resolved_directory}. Expected {default_image_name} or another .png file."
        )
    return images[0]


def resize_image_for_request(image_bytes: bytes, max_image_size: int) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    """Resize an image only when its longest side exceeds the configured limit."""

    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Could not decode the input image.")
    height, width = image.shape[:2]
    original_size = (width, height)
    if max(width, height) <= max_image_size:
        return image_bytes, original_size, original_size

    scale = max_image_size / max(width, height)
    target_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized = cv2.resize(image, target_size, interpolation=cv2.INTER_AREA)
    encoded, resized_bytes = cv2.imencode(".png", resized)
    if not encoded:
        raise ValueError("Could not encode the resized image.")
    return resized_bytes.tobytes(), original_size, target_size


def describe_image(
    image_path: Path, project_directory: Path, config: dict[str, object], model: str
) -> int:
    """Send one image to Ollama and save its description as describe.txt."""

    try:
        timeout_seconds = load_ollama_timeout_seconds(PROJECT_ROOT)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    prompt = str(config["prompt"])
    ollama_url = str(config.get("ollama_url", "http://localhost:11434/api/generate"))
    output_path = resolve_project_file(str(config["output_file"]), project_directory, "output file")
    try:
        image_bytes = image_path.read_bytes()
        request_image_bytes, original_size, request_size = resize_image_for_request(
            image_bytes, int(config["max_image_size"])
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: Could not prepare input image: {error}", file=sys.stderr)
        return 2
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "images": [base64.b64encode(request_image_bytes).decode("ascii")],
        "stream": True,
        "think": bool(config.get("think", False)),
        "options": config.get("options", {}),
    }
    version_url = ollama_url.removesuffix("/api/generate") + "/api/version"

    report(f"Working directory: {project_directory}")
    report(f"Input image: {image_path.name} ({len(image_bytes):,} bytes, {original_size[0]}x{original_size[1]} px)")
    if request_size != original_size:
        report(
            f"Image resized for Ollama: {request_size[0]}x{request_size[1]} px "
            f"({len(request_image_bytes):,} bytes; max side {config['max_image_size']} px)"
        )
    else:
        report(f"Image size is within the configured {config['max_image_size']} px limit; original is used.")
    report(f"Model: {model}")
    report(f"Prompt: {prompt}")
    report(f"Ollama response timeout: {timeout_seconds:g} s")

    verbose = bool(config.get("verbose", True))
    description_parts: list[str] = []
    result: dict[str, object] = {}
    thinking_started = False
    description_started = False

    try:
        report(f"Checking that Ollama is running: {version_url}")
        version_response = requests.get(version_url, timeout=10)
        version_response.raise_for_status()
        version = version_response.json().get("version", "unknown version")
        report(f"Ollama responded (version {version}).")

        report("Sending image-description request to Ollama; waiting for streamed output.")
        started_at = datetime.now()
        started = time.monotonic()
        with requests.post(
            ollama_url,
            json=payload,
            stream=True,
            timeout=(10, timeout_seconds),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Ollama sent invalid streaming JSON: {error}") from error
                if not isinstance(chunk, dict):
                    raise ValueError("Ollama sent a streaming response that is not a JSON object.")
                if isinstance(chunk.get("error"), str):
                    raise ValueError(f"Ollama reported an error: {chunk['error']}")

                thinking = chunk.get("thinking")
                if isinstance(thinking, str) and thinking:
                    if verbose:
                        if not thinking_started:
                            print("Thinking:", flush=True)
                        print(thinking, end="", flush=True)
                    thinking_started = True

                text = chunk.get("response")
                if isinstance(text, str) and text:
                    description_parts.append(text)
                    if verbose:
                        if not description_started:
                            if thinking_started:
                                print("\n", flush=True)
                            print("Description:", flush=True)
                        print(text, end="", flush=True)
                    description_started = True

                if chunk.get("done") is True:
                    result = chunk
                    break
        elapsed = time.monotonic() - started
        if verbose and (thinking_started or description_started):
            print(flush=True)
    except requests.RequestException as error:
        print(f"ERROR: Could not connect to Ollama: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"ERROR: Ollama stream failed: {error}", file=sys.stderr)
        return 1

    description = "".join(description_parts)
    if not description:
        print("ERROR: Ollama did not return an image description.", file=sys.stderr)
        return 1

    output_path.write_text(description, encoding="utf-8")
    report(f"Description has {len(description)} characters.")
    report(f"Request date: {started_at:%Y-%m-%d %H:%M:%S}")
    report(f"Evaluation duration: {elapsed:.1f} s")
    for name, label in (
        ("total_duration", "Ollama total duration"),
        ("load_duration", "Model load duration"),
        ("prompt_eval_duration", "Input evaluation duration"),
        ("eval_duration", "Output evaluation duration"),
    ):
        value = result.get(name)
        if isinstance(value, int):
            report(f"{label}: {value / 1_000_000_000:.1f} s")
    for name, label in (("prompt_eval_count", "Input tokens"), ("eval_count", "Output tokens")):
        value = result.get(name)
        if isinstance(value, int):
            report(f"{label}: {value}")
    report(f"Description saved: {output_path}")
    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Describe an image with local Ollama. Without an argument, use describe.png "
            "or the first PNG file in the project directory selected by project.json."
        )
    )
    parser.add_argument("image", nargs="?", help="optional image in the project directory")
    parser.add_argument(
        "-model2",
        action="store_true",
        help="use model2 from cli_describe_img.json instead of the default model",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        config = load_config()
        project_directory = load_project_directory(PROJECT_ROOT)
        log_enabled = read_log_enabled(CONFIG_FILE)
        image_path = resolve_image_path(
            arguments.image, project_directory, str(config["default_image"])
        )
        model_name = "model2" if arguments.model2 else "model"
        configured_model = config.get(model_name)
        if not isinstance(configured_model, str) or not configured_model.strip():
            raise ValueError(f"The {model_name!r} value must be non-empty text: {CONFIG_FILE}")
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    with project_log(project_directory, "cli_describe_img.py", log_enabled):
        return describe_image(image_path, project_directory, config, configured_model)


if __name__ == "__main__":
    raise SystemExit(main())

"""Describe one PNG image through local Ollama and save the result."""

from __future__ import annotations

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
    for name in (
        "model",
        "prompt",
        "prompt_long",
        "default_input_file",
        "default_output_file",
    ):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"The {name!r} value must be non-empty text: {CONFIG_FILE}")
    max_image_size = config.get("max_image_size")
    if (
        not isinstance(max_image_size, int)
        or isinstance(max_image_size, bool)
        or max_image_size <= 0
    ):
        raise ValueError(f"The 'max_image_size' value must be a positive whole number: {CONFIG_FILE}")
    temperature = config.get("temperature")
    if (
        not isinstance(temperature, (int, float))
        or isinstance(temperature, bool)
        or temperature < 0
    ):
        raise ValueError(f"The 'temperature' value must be a non-negative number: {CONFIG_FILE}")
    temperature_long = config.get("temperature_long")
    if (
        not isinstance(temperature_long, (int, float))
        or isinstance(temperature_long, bool)
        or temperature_long < 0
    ):
        raise ValueError(
            f"The 'temperature_long' value must be a non-negative number: {CONFIG_FILE}"
        )
    repeat_penalty = config.get("repeat_penalty")
    if (
        not isinstance(repeat_penalty, (int, float))
        or isinstance(repeat_penalty, bool)
        or repeat_penalty <= 0
    ):
        raise ValueError(f"The 'repeat_penalty' value must be a positive number: {CONFIG_FILE}")
    num_predict = config.get("num_predict")
    if (
        not isinstance(num_predict, int)
        or isinstance(num_predict, bool)
        or num_predict <= 0
    ):
        raise ValueError(f"The 'num_predict' value must be a positive whole number: {CONFIG_FILE}")
    num_predict_long = config.get("num_predict_long")
    if (
        not isinstance(num_predict_long, int)
        or isinstance(num_predict_long, bool)
        or num_predict_long <= 0
    ):
        raise ValueError(
            f"The 'num_predict_long' value must be a positive whole number: {CONFIG_FILE}"
        )
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


def describe_image(
    image_path: Path,
    project_directory: Path,
    config: dict[str, object],
    model: str,
    output_path: Path,
) -> int:
    """Send one image to Ollama and save its description as describe.txt."""

    try:
        timeout_seconds = load_ollama_timeout_seconds(PROJECT_ROOT)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    prompt = str(config["prompt"])
    ollama_url = str(config.get("ollama_url", "http://localhost:11434/api/generate"))
    options = dict(config.get("options", {}))
    options["temperature"] = config["temperature"]
    options["repeat_penalty"] = config["repeat_penalty"]
    options["num_predict"] = config["num_predict"]
    try:
        image_bytes = image_path.read_bytes()
        request_image_bytes, original_size, request_size = resize_image_for_request(
            image_bytes, int(config["max_image_size"])
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: Could not prepare input image: {error}", file=sys.stderr)
        return 2
    payload: dict[str, object] = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [image_bytes_to_ollama_base64(request_image_bytes)],
        }],
        "stream": True,
        "think": bool(config.get("think", False)),
        "options": options,
    }
    version_url, _, chat_url = get_ollama_endpoint_urls(ollama_url)

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
    report(f"Temperature: {config['temperature']}")
    report(f"Repeat penalty: {config['repeat_penalty']}")
    report(f"Maximum output tokens: {config['num_predict']}")
    report(f"Thinking enabled: {config.get('think', False)}")
    report(f"Ollama response timeout: {timeout_seconds:g} s")

    verbose = bool(config.get("verbose", True))
    terminal = Terminal()
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

        report(f"Sending image-description request to Ollama chat endpoint: {chat_url}")
        started_at = datetime.now()
        started = time.monotonic()
        with requests.post(
            chat_url,
            json=payload,
            stream=True,
            timeout=(10, timeout_seconds),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=False):
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as error:
                    raise ValueError(f"Ollama sent invalid streaming JSON: {error}") from error
                if not isinstance(chunk, dict):
                    raise ValueError("Ollama sent a streaming response that is not a JSON object.")
                if isinstance(chunk.get("error"), str):
                    raise ValueError(f"Ollama reported an error: {chunk['error']}")

                message = chunk.get("message")
                if not isinstance(message, dict):
                    raise ValueError("Ollama chat response does not contain a message object.")

                thinking = message.get("thinking")
                if isinstance(thinking, str) and thinking:
                    if verbose:
                        if not thinking_started:
                            print("Thinking:", flush=True)
                        print(thinking, end="", flush=True)
                    thinking_started = True

                text = message.get("content")
                if isinstance(text, str) and text:
                    description_parts.append(text)
                    if verbose:
                        if not description_started:
                            if thinking_started:
                                print("\n", flush=True)
                            print("Description:", flush=True)
                        print(terminal.color("g", text), end="", flush=True)
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
    if not verbose:
        print("Description:", flush=True)
        terminal.print("g", description)

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


def positive_integer(value: str) -> int:
    """Parse a positive integer for an Ollama token limit."""

    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def non_negative_float(value: str) -> float:
    """Parse a non-negative temperature override."""

    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Describe an image with local Ollama. Without an image argument, use "
            "default_input_file from cli_describe_img.json or the first PNG file in the "
            "project directory selected by project.json. Use --in and --out to override "
            "the input and output file from cli_describe_img.json."
        ),
        epilog="Example: cli_describe_img.py image.png output.txt",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="image_or_output",
        help="optional image; a final .txt filename sets the output file",
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
        "-model2",
        action="store_true",
        help="use model2 from cli_describe_img.json instead of the default model",
    )
    parser.add_argument(
        "-long",
        dest="long",
        action="store_true",
        help="use prompt_long, num_predict_long, and temperature_long from JSON for this run",
    )
    parser.add_argument(
        "--long",
        dest="long_tokens",
        type=positive_integer,
        metavar="TOKENS",
        help=(
            "use prompt_long and temperature_long from JSON, and override num_predict_long"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Ollama random seed; overrides any seed in JSON options",
    )
    parser.add_argument(
        "--temp",
        type=non_negative_float,
        metavar="TEMPERATURE",
        help="Ollama temperature; overrides temperature from JSON",
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


def main() -> int:
    arguments = parse_arguments()
    try:
        config = load_config()
        if arguments.long or arguments.long_tokens is not None:
            config = {
                **config,
                "prompt": config["prompt_long"],
                "num_predict": (
                    arguments.long_tokens
                    if arguments.long_tokens is not None
                    else config["num_predict_long"]
                ),
                "temperature": config["temperature_long"],
            }
        if arguments.temp is not None:
            config = {**config, "temperature": arguments.temp}
        if arguments.seed is not None:
            config = {
                **config,
                "options": {**dict(config.get("options", {})), "seed": arguments.seed},
            }
        project_directory = get_project_directory(PROJECT_ROOT, load_project_config(PROJECT_ROOT))
        log_enabled = read_log_enabled(CONFIG_FILE)
        image_path = resolve_image_path(
            arguments.image,
            project_directory,
            str(config["default_input_file"]),
            SUPPORTED_INPUT_EXTENSIONS,
            fallback_extensions={".png"},
        )
        output_filename = arguments.output_file or str(config["default_output_file"])
        output_path = resolve_project_file(output_filename, project_directory, "output file")
        model_name = "model2" if arguments.model2 else "model"
        configured_model = config.get(model_name)
        if not isinstance(configured_model, str) or not configured_model.strip():
            raise ValueError(f"The {model_name!r} value must be non-empty text: {CONFIG_FILE}")
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    with console_log(project_directory, "cli_describe_img.py", log_enabled):
        return describe_image(image_path, project_directory, config, configured_model, output_path)


if __name__ == "__main__":
    raise SystemExit(main())

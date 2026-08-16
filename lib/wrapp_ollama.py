"""Client for batch request processing through the local Ollama API."""

from __future__ import annotations

import json
import socket
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit

from lib.wrapp_img import image_bytes_to_ollama_base64, resize_image_for_request
from lib.wrapp_terminal import Terminal, colors_enabled

try:
    import requests
except ImportError:
    requests = None

DEFAULT_MODEL = "deepseek-r1:14b"
__version__ = "0.25.10"
APPLICATION_VERSION = __version__
CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 900
MODEL_UNAVAILABLE_EXIT_CODE = 3
OPTION_NAMES = ("seed", "num_predict", "num_ctx", "temperature", "repeat_penalty")
INTEGER_OPTIONS = {"seed", "num_predict", "num_ctx"}
THINKING_LEVELS = {"low", "medium", "high"}
TEXT_INPUT_ENCODING = "utf-8-sig"
TEXT_OUTPUT_ENCODING = "utf-8-sig"
UTF8_BOM = b"\xef\xbb\xbf"


class ModelUnavailableError(RuntimeError):
    """Raised when Ollama reports that the requested model is not installed."""


def load_ollama_timeout_seconds(project_root: Path, default: float = DEFAULT_OLLAMA_TIMEOUT_SECONDS) -> float:
    """Load the Ollama response timeout from the project's project.json."""

    config_path = project_root / "project.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read project configuration {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Project configuration must be a JSON object: {config_path}")

    timeout = data.get("ollama_timeout_seconds", default)
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or timeout <= 0
    ):
        raise ValueError(
            f"The 'ollama_timeout_seconds' value must be a positive number: {config_path}"
        )
    return float(timeout)


def get_ollama_endpoint_urls(generate_url: str) -> tuple[str, str, str]:
    """Return the version, generate, and chat endpoints for an Ollama generate URL."""

    base_url = generate_url.removesuffix("/api/generate")
    return (
        f"{base_url}/api/version",
        f"{base_url}/api/generate",
        f"{base_url}/api/chat",
    )


class Reporter:
    """Write messages to both the terminal and a report file."""

    GRAY = "\033[90m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    def __init__(
        self,
        output_path: Path | None,
        *,
        append: bool = False,
        time_trace: bool = False,
    ) -> None:
        if output_path and append and output_path.is_file() and output_path.stat().st_size:
            existing = output_path.read_bytes()
            if not existing.startswith(UTF8_BOM):
                output_path.write_bytes(UTF8_BOM + existing)
        self.file = (
            output_path.open("a" if append else "w", encoding=TEXT_OUTPUT_ENCODING)
            if output_path
            else None
        )
        self.use_colors = colors_enabled()
        self.time_trace = time_trace
        self.started_at = time.monotonic()

    def write(
        self,
        message: str = "",
        end: str = "\n",
        flush: bool = True,
        color: str = GRAY,
        trace: bool = True,
        highlight: str | None = None,
        white_highlights: tuple[str, ...] = (),
    ) -> None:
        output_message = message
        if self.time_trace and trace and message and end == "\n":
            timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
            elapsed_seconds = time.monotonic() - self.started_at
            output_message = f"[{timestamp} +{elapsed_seconds:7.1f}s] {message}"
        terminal_message = output_message
        if highlight and self.use_colors:
            highlighted = Terminal().color("g", highlight)
            terminal_message = terminal_message.replace(
                highlight,
                f"{highlighted}{self.GRAY}",
                1,
            )
        if self.use_colors:
            for value in white_highlights:
                if value and value != "-":
                    highlighted = Terminal().color("w", value)
                    terminal_message = terminal_message.replace(
                        value,
                        f"{highlighted}{self.GRAY}",
                        1,
                    )
        if self.use_colors and output_message:
            terminal_message = f"{color}{terminal_message}{self.RESET}"
        print(terminal_message, end=end, flush=flush)
        if self.file:
            self.file.write(output_message + end)
            if flush:
                self.file.flush()

    def close(self) -> None:
        if self.file:
            self.file.close()


class ollama_api:
    """Load configuration and send all input.json requests to Ollama."""

    def __init__(
        self,
        config_path: Path,
        debug_enabled: bool | None = None,
        on_response_text: Callable[[str], None] | None = None,
        on_prompt: Callable[[str], None] | None = None,
        on_output_path: Callable[[Path], None] | None = None,
        time_trace: bool = False,
    ) -> None:
        self.config_path = config_path
        self.on_response_text = on_response_text
        self.on_prompt = on_prompt
        self.on_output_path = on_output_path
        self.time_trace = time_trace
        project_root = config_path.resolve().parent.parent
        self.read_timeout_seconds = load_ollama_timeout_seconds(project_root)
        config = self._read_config(config_path)
        self.base_url = config["url"]
        if debug_enabled is not None and not isinstance(debug_enabled, bool):
            raise ValueError("The project debug override must be true or false.")
        # project.json is the explicit, project-wide verbosity choice. A task
        # setting is a fallback only when the project does not define one.
        self.project_debug_enabled = debug_enabled
        self.default_debug_enabled = config["debug"]
        self.debug_enabled = config["debug"] if debug_enabled is None else debug_enabled
        self.default_options = config["default_options"]
        self.api_url = f"{self.base_url}/api/generate"
        self.version_url = f"{self.base_url}/api/version"
        self.tags_url = f"{self.base_url}/api/tags"

    @staticmethod
    def _read_json(path: Path) -> dict:
        with path.open(encoding=TEXT_INPUT_ENCODING) as source_file:
            return json.load(source_file)

    @classmethod
    def _read_config(cls, config_path: Path) -> dict:
        data = cls._read_json(config_path)
        url = data.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError('ollama.json must contain a non-empty "url" field.')
        if not isinstance(data.get("debug"), bool):
            raise ValueError('The "debug" field in ollama.json must be true or false.')
        default_options = cls._read_options(
            data.get("default_options"),
            source="default_options v ollama.json",
            require_all=True,
        )
        return {
            "url": url.rstrip("/"),
            "debug": data["debug"],
            "default_options": default_options,
        }

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @classmethod
    def _read_options(cls, data: object, source: str, require_all: bool = False) -> dict:
        if not isinstance(data, dict):
            raise ValueError(f"{source} must be a JSON object.")

        options = {}
        for option_name in OPTION_NAMES:
            if option_name not in data:
                if require_all:
                    raise ValueError(f"The {option_name!r} option is missing from {source}.")
                continue

            value = data[option_name]
            if option_name in INTEGER_OPTIONS:
                is_valid = isinstance(value, int) and not isinstance(value, bool)
            else:
                is_valid = cls._is_number(value)
            if not is_valid:
                raise ValueError(f"The {option_name!r} option in {source} must be a number.")
            options[option_name] = value
        return options

    @classmethod
    def _read_input(cls, input_path: Path) -> dict:
        data = cls._read_json(input_path)
        queries = data.get("queries")
        if not isinstance(queries, list) or not queries:
            raise ValueError('input.json must contain a non-empty "queries" field.')
        shared_prompt = data.get("prompt")
        if shared_prompt is not None and (
            not isinstance(shared_prompt, str) or not shared_prompt.strip()
        ):
            raise ValueError('The "prompt" field in input.json must be non-empty text.')
        shared_instruction = data.get("instruction", "")
        if not isinstance(shared_instruction, str):
            raise ValueError('The "instruction" field in input.json must be text.')

        normalized_queries = []
        for index, query in enumerate(queries, start=1):
            if not isinstance(query, dict):
                raise ValueError(f'Query {index} in "queries" must be a JSON object.')
            normalized_query = query.copy()
            normalized_query.setdefault("prompt", shared_prompt)
            normalized_query.setdefault("instruction", shared_instruction)
            if not isinstance(normalized_query.get("prompt"), str) or not normalized_query[
                "prompt"
            ].strip():
                raise ValueError(
                    f'Every item in "queries" must have a non-empty "prompt" field '
                    'or a shared root-level "prompt" field must be present.'
                )
            normalized_queries.append(normalized_query)
        data["queries"] = normalized_queries
        if "debug" in data and not isinstance(data["debug"], bool):
            raise ValueError('The "debug" field in input.json must be true or false.')
        if "appendix" in data and (
            not isinstance(data["appendix"], str) or not data["appendix"]
        ):
            raise ValueError('The "appendix" field in input.json must be non-empty text.')
        if "hlas" in data and data["hlas"] not in {"honza", "jirka"}:
            raise ValueError('The "hlas" field in input.json must be "honza" or "jirka".')
        if "mp3" in data and not isinstance(data["mp3"], bool):
            raise ValueError('Pole "mp3" v input.json musi byt true nebo false.')
        cls._read_options(data, source="input.json")
        for index, query in enumerate(normalized_queries, start=1):
            cls._read_options(query, source=f"dotaz {index} v input.json")
        return data

    def _debug(self, reporter: Reporter, message: str) -> None:
        if self.debug_enabled:
            reporter.write(f"[DEBUG] {message}")

    def effective_task_debug_enabled(self, task_config: dict) -> bool:
        """Return the verbosity selected for one task."""

        if self.project_debug_enabled is not None:
            return self.project_debug_enabled
        return task_config.get("debug", self.default_debug_enabled)

    def _configure_task_debug(self, task_config: dict) -> None:
        """Apply the effective verbosity before a task starts."""

        self.debug_enabled = self.effective_task_debug_enabled(task_config)

    def _check_server(self, reporter: Reporter, session: requests.Session) -> bool:
        if self.debug_enabled:
            reporter.write(f"Trying to connect to the Ollama server: {self.version_url}")
        self._debug(reporter, f"Connection timeout: {CONNECT_TIMEOUT_SECONDS} s")
        self._debug(reporter, f"Ollama response timeout: {self.read_timeout_seconds:g} s")
        try:
            response = session.get(self.version_url, timeout=CONNECT_TIMEOUT_SECONDS)
            if self.debug_enabled:
                reporter.write(f"Server response: HTTP {response.status_code} {response.reason}")
            self._debug(reporter, f"Response headers: {dict(response.headers)}")
            self._debug(reporter, f"Server response body: {response.text}")
            response.raise_for_status()
            if self.debug_enabled:
                reporter.write("Connection to Ollama is working.")
            return True
        except requests.RequestException as error:
            reporter.write(f"Connection to Ollama failed: {error}")
            reporter.write("Check that Ollama is running and listening at the configured address.")
            return False

    @staticmethod
    def _missing_model_message(response: object) -> str | None:
        """Return Ollama's missing-model error text, if this response reports one."""

        if getattr(response, "status_code", None) != 404:
            return None
        try:
            data = response.json()  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            return None
        error_text = data.get("error") if isinstance(data, dict) else None
        if (
            isinstance(error_text, str)
            and "model" in error_text.casefold()
            and "not found" in error_text.casefold()
        ):
            return error_text
        return None

    def test_connection(self) -> int:
        """Print a detailed, model-free diagnostic of the Ollama connection."""

        reporter = Reporter(None, time_trace=self.time_trace)
        try:
            reporter.write("Ollama connection diagnostic")
            reporter.write(f"Configuration file: {self.config_path}")
            reporter.write(f"Configured server URL: {self.base_url}")
            reporter.write(f"Version endpoint: {self.version_url}")
            reporter.write(f"Generate endpoint: {self.api_url}")
            reporter.write(f"Connection timeout: {CONNECT_TIMEOUT_SECONDS} s")
            reporter.write(f"Response timeout: {self.read_timeout_seconds:g} s")

            try:
                parsed_url = urlsplit(self.base_url)
                hostname = parsed_url.hostname
                if parsed_url.scheme not in {"http", "https"} or not hostname:
                    raise ValueError("URL must use http:// or https:// and include a host name.")
                port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
            except ValueError as error:
                reporter.write(f"FAIL: The configured server URL is invalid: {error}")
                return 2

            reporter.write(f"Parsed URL: scheme={parsed_url.scheme}, host={hostname}, port={port}")
            reporter.write(f"DNS lookup: resolving {hostname}:{port} ...")
            try:
                addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            except OSError as error:
                reporter.write(f"FAIL: DNS lookup failed ({type(error).__name__}): {error}")
                return 1

            resolved_addresses = []
            for family, _socktype, _protocol, _canonical_name, address in addresses:
                family_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
                address_text = f"{family_name} {address[0]}:{address[1]}"
                if address_text not in resolved_addresses:
                    resolved_addresses.append(address_text)
            reporter.write(f"DNS lookup succeeded: {', '.join(resolved_addresses)}")

            if requests is None:
                reporter.write("FAIL: The 'requests' package is not installed.")
                return 2

            reporter.write(f"HTTP request: GET {self.version_url}")
            reporter.write("HTTP client: requests; environment proxy settings are enabled.")
            started_at = time.monotonic()
            try:
                with requests.Session() as session:
                    response = session.get(
                        self.version_url,
                        timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
                    )
            except requests.RequestException as error:
                elapsed = time.monotonic() - started_at
                reporter.write(
                    f"FAIL: HTTP request failed after {elapsed:.2f} s "
                    f"({type(error).__name__}): {error}"
                )
                reporter.write("Check that Ollama is running and that its configured address is reachable.")
                return 1

            elapsed = time.monotonic() - started_at
            reporter.write(f"HTTP response after {elapsed:.2f} s: {response.status_code} {response.reason}")
            reporter.write(f"Response headers: {dict(response.headers)}")
            reporter.write(f"Response body: {response.text}")
            try:
                response.raise_for_status()
            except requests.RequestException as error:
                reporter.write(f"FAIL: Ollama returned an HTTP error ({type(error).__name__}): {error}")
                return 1

            try:
                response_data = response.json()
            except json.JSONDecodeError as error:
                reporter.write(f"FAIL: The version endpoint did not return JSON: {error}")
                return 1
            version = response_data.get("version") if isinstance(response_data, dict) else None
            if not isinstance(version, str) or not version:
                reporter.write("FAIL: The version response does not contain a non-empty 'version' field.")
                return 1

            reporter.write(f"Version endpoint validated: Ollama version {version}.")

            reporter.write(f"Model list request: GET {self.tags_url}")
            try:
                with requests.Session() as session:
                    tags_response = session.get(
                        self.tags_url,
                        timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
                    )
            except requests.RequestException as error:
                reporter.write(f"FAIL: Model list request failed ({type(error).__name__}): {error}")
                return 1
            reporter.write(
                f"Model list response: HTTP {tags_response.status_code} {tags_response.reason}"
            )
            if self.debug_enabled:
                reporter.write(f"Model list body: {tags_response.text}")
            try:
                tags_response.raise_for_status()
                tags_data = tags_response.json()
            except (requests.RequestException, json.JSONDecodeError) as error:
                reporter.write(f"FAIL: Could not read the Ollama model list ({type(error).__name__}): {error}")
                return 1
            models = tags_data.get("models") if isinstance(tags_data, dict) else None
            if not isinstance(models, list):
                reporter.write("FAIL: The model list response does not contain a 'models' array.")
                return 1
            model_names = [model.get("name") for model in models if isinstance(model, dict)]
            model_names = [name for name in model_names if isinstance(name, str) and name]
            reporter.write(
                f"Installed models ({len(model_names)}): "
                f"{', '.join(model_names) if model_names else '(none)'}"
            )

            reporter.write(f"Generate endpoint probe: POST {self.api_url} with an empty JSON object")
            reporter.write("Expected result: a model-validation error; no model is loaded or run.")
            try:
                with requests.Session() as session:
                    generate_response = session.post(
                        self.api_url,
                        json={},
                        timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
                    )
            except requests.RequestException as error:
                reporter.write(f"FAIL: Generate endpoint probe failed ({type(error).__name__}): {error}")
                return 1
            reporter.write(
                f"Generate endpoint response: HTTP {generate_response.status_code} "
                f"{generate_response.reason}"
            )
            reporter.write(f"Generate endpoint body: {generate_response.text}")
            try:
                generate_data = generate_response.json()
            except json.JSONDecodeError:
                generate_data = None
            generate_error = generate_data.get("error") if isinstance(generate_data, dict) else None
            if (
                generate_response.status_code not in {400, 404}
                or not isinstance(generate_error, str)
                or "model" not in generate_error.casefold()
            ):
                reporter.write("FAIL: The generate endpoint did not return the expected model-validation error.")
                return 1

            reporter.write(
                "SUCCESS: Version, model-list, and generate endpoints are available. "
                "The generate endpoint rejected the intentionally missing model as expected."
            )
            return 0
        finally:
            reporter.close()

    def list_models(self) -> int:
        """Print the models registered in the configured Ollama server."""

        reporter = Reporter(None, time_trace=self.time_trace)
        try:
            if requests is None:
                reporter.write("The 'requests' package is required to contact Ollama.")
                return 2

            if self.debug_enabled:
                reporter.write(f"Ollama model list: {self.tags_url}")
                reporter.write(f"Connection timeout: {CONNECT_TIMEOUT_SECONDS} s")
            else:
                reporter.write("Requesting available Ollama models...")
            try:
                with requests.Session() as session:
                    response = session.get(
                        self.tags_url,
                        timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
                    )
            except requests.RequestException as error:
                reporter.write(f"Could not request the model list ({type(error).__name__}): {error}")
                return 1

            if self.debug_enabled:
                reporter.write(f"Server response: HTTP {response.status_code} {response.reason}")
            try:
                response.raise_for_status()
                response_data = response.json()
            except (requests.RequestException, json.JSONDecodeError) as error:
                reporter.write(f"Could not read the model list ({type(error).__name__}): {error}")
                reporter.write(f"Server response body: {response.text}")
                return 1

            models = response_data.get("models") if isinstance(response_data, dict) else None
            if not isinstance(models, list):
                reporter.write("The model list response does not contain a 'models' array.")
                return 1
            if not models:
                reporter.write("No Ollama models are installed.")
                return 0

            model_rows = [self._model_list_row(model) for model in models if isinstance(model, dict)]
            model_rows = [row for row in model_rows if row is not None]
            if not model_rows:
                reporter.write("No usable model names were returned by Ollama.")
                return 1

            reporter.write(f"Available Ollama models ({len(model_rows)}):")
            for index, row in enumerate(model_rows):
                reporter.write(
                    f"{row['name']}  |  Size: {row['size']}  |  "
                    f"Parameters: {row['parameters']}  |  "
                    f"Quantization: {row['quantization']}",
                    trace=False,
                    highlight=row["name"],
                    white_highlights=(row["size"],),
                )
                reporter.write(
                    f"  Family: {row['family']}  |  Context: {row['context']}  |  "
                    f"Embedding: {row['embedding']}  |  "
                    f"Capabilities: {row['capabilities']}",
                    trace=False,
                )
                reporter.write(
                    f"  {row['digest']}  |  {row['modified']}",
                    trace=False,
                    white_highlights=(row["modified"],),
                )
                if index < len(model_rows) - 1:
                    reporter.write(trace=False)
            reporter.write(f"Listed {len(model_rows)} Ollama model(s).")
            return 0
        finally:
            reporter.close()

    @staticmethod
    def _model_list_row(model: dict) -> dict[str, str] | None:
        """Extract display-ready fields from one item returned by ``/api/tags``."""

        name = model.get("name")
        if not isinstance(name, str) or not name:
            return None
        details = model.get("details")
        details = details if isinstance(details, dict) else {}

        def text(value: object, default: str = "-") -> str:
            return value if isinstance(value, str) and value else default

        size = model.get("size")
        size_text = f"{size / 1024 ** 3:.1f} GiB" if isinstance(size, int) else "-"
        context_length = details.get("context_length")
        context = f"{context_length:,}" if isinstance(context_length, int) else "-"
        embedding_length = details.get("embedding_length")
        embedding = f"{embedding_length:,}" if isinstance(embedding_length, int) else "-"
        capabilities = model.get("capabilities")
        capabilities_text = (
            ",".join(item for item in capabilities if isinstance(item, str))
            if isinstance(capabilities, list)
            else "-"
        ) or "-"
        families = details.get("families")
        family = text(details.get("family"))
        if family == "-" and isinstance(families, list):
            family = ",".join(item for item in families if isinstance(item, str)) or "-"
        modified = text(model.get("modified_at"))
        if modified != "-":
            modified = modified.replace("T", " ").removesuffix("Z")[:19]
        digest = text(model.get("digest"))
        if digest != "-":
            digest = digest[:12]
        return {
            "name": name,
            "size": size_text,
            "parameters": text(details.get("parameter_size")),
            "quantization": text(details.get("quantization_level")),
            "family": family,
            "context": context,
            "embedding": embedding,
            "capabilities": capabilities_text,
            "modified": modified,
            "digest": digest,
        }

    def _query(
        self,
        reporter: Reporter,
        session: requests.Session,
        prompt: str,
        model_name: str,
        options: dict,
        think: bool,
        instruction: str = "",
        compact_report: bool = False,
        response_file: TextIO | None = None,
        report_response: bool = True,
    ) -> bool:
        payload = self._build_generate_payload(
            model_name=model_name,
            prompt=prompt,
            options=options,
            think=think,
            instruction=instruction,
            stream=True,
        )

        if self.debug_enabled:
            reporter.write(f"Trying to send a request to: {self.api_url}")
            reporter.write(f"Model: {model_name}; parametry: {json.dumps(options, ensure_ascii=False)}")
        elif not compact_report:
            reporter.write(f"Model: {model_name}")
        else:
            reporter.write(f"Seed: {options['seed']}")
        if not compact_report:
            reporter.write(f"Prompt: {prompt}")
        if instruction and not compact_report:
            reporter.write(f"Instruction: {instruction}")
        if not self.debug_enabled and not compact_report:
            reporter.write(f"Parametry: {json.dumps(options, ensure_ascii=False)}")
        self._debug(reporter, f"Outgoing JSON: {json.dumps(payload, ensure_ascii=False)}")

        try:
            response = session.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
            )
            if self.debug_enabled:
                reporter.write(f"Server response: HTTP {response.status_code} {response.reason}")
            self._debug(reporter, f"Response headers: {dict(response.headers)}")
            missing_model_message = self._missing_model_message(response)
            if missing_model_message:
                raise ModelUnavailableError(missing_model_message)
            response.raise_for_status()
        except requests.HTTPError as error:
            reporter.write(f"Sending the request failed: {error}")
            if error.response is not None:
                reporter.write(
                    f"Server response: HTTP {error.response.status_code} {error.response.reason}"
                )
                reporter.write(f"Server response body: {error.response.text}")
            return False
        except requests.RequestException as error:
            reporter.write(f"Sending the request failed: {error}")
            return False

        if not compact_report:
            reporter.write("Receiving response stream:" if self.debug_enabled else "Stream:")
        final_chunk = None
        response_parts = []
        received_tokens = 0
        in_thinking = False
        prompt_announced = False
        try:
            response.encoding = "utf-8"
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                chunk = json.loads(line)
                thinking_text = chunk.get("thinking", "")
                if think and thinking_text and report_response:
                    if not in_thinking:
                        reporter.write("Thinking:")
                        in_thinking = True
                    reporter.write(thinking_text, end="", color=Reporter.GREEN)
                text = chunk.get("response", "")
                if text:
                    if self.on_prompt and not prompt_announced and text.strip():
                        self.on_prompt(prompt)
                        prompt_announced = True
                    if in_thinking:
                        reporter.write("\nResponse:")
                        in_thinking = False
                    response_parts.append(text)
                    received_tokens += 1
                    if response_file:
                        response_file.write(text)
                        response_file.flush()
                    if report_response:
                        reporter.write(text, end="", color=Reporter.GREEN)
                    if self.on_response_text:
                        self.on_response_text(text)
                    if self.debug_enabled and report_response and received_tokens % 30 == 0:
                        time_text = datetime.now().strftime("%H:%M")
                        token_text = json.dumps(text, ensure_ascii=False)
                        is_done = str(bool(chunk.get("done"))).lower()
                        reporter.write(
                            f"\n{{time {time_text},\"response\":{token_text},\"done\":{is_done}}}"
                        )
                if chunk.get("done"):
                    final_chunk = chunk
        except (requests.RequestException, json.JSONDecodeError) as error:
            reporter.write(f"Error while reading the stream: {error}")
            return False

        if final_chunk is None:
            reporter.write("The stream ended without final information from the server.")
            return False

        reporter.write()
        if self.debug_enabled:
            if report_response:
                reporter.write(f"Combined model response: {''.join(response_parts)}")
            else:
                reporter.write("The combined model response was saved to separate output.")
            reporter.write(f"Stream complete. Reason: {final_chunk.get('done_reason', 'not provided')}")
        else:
            reporter.write("Ollama response complete.")
        self._debug(reporter, f"Final server data: {json.dumps(final_chunk, ensure_ascii=False)}")
        return True

    @classmethod
    def _read_task(cls, task: object) -> dict:
        """Validate a single text task loaded from a ``task_*.json`` file."""

        if not isinstance(task, dict):
            raise ValueError("Task configuration must be a JSON object.")
        if "queries" in task:
            raise ValueError("Task configuration must describe one task and must not contain 'queries'.")
        model = task.get("model")
        prompt = task.get("prompt")
        if not isinstance(model, str) or not model.strip():
            raise ValueError('Task configuration requires a non-empty "model" field.')
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError('Task configuration requires a non-empty "prompt" field.')
        for name in ("instruction",):
            if name in task and not isinstance(task[name], str):
                raise ValueError(f'The "{name}" field in a task must be text.')
        if "debug" in task and not isinstance(task["debug"], bool):
            raise ValueError('The "debug" field in a task must be true or false.')
        think = task.get("think", False)
        if not isinstance(think, bool) and think not in THINKING_LEVELS:
            raise ValueError(
                'The "think" field in a task must be true, false, "low", "medium", or "high".'
            )
        cls._read_options(task, source="task configuration")
        nested_options = task.get("options", {})
        cls._read_options(nested_options, source="task options")
        return task

    def _task_options(self, task_config: dict) -> dict:
        """Merge shared, task-root, and task-nested Ollama options."""

        task_options = self._read_options(task_config, source="task configuration")
        nested_options = self._read_options(task_config.get("options", {}), source="task options")
        return self.default_options | task_options | nested_options

    def effective_task_options(self, task_config: dict) -> dict:
        """Return the final generation options for a validated task configuration."""

        return self._task_options(task_config)

    @staticmethod
    def _build_generate_payload(
        *,
        model_name: str,
        prompt: str,
        options: dict,
        think: bool | str,
        instruction: str = "",
        images: list[str] | None = None,
        stream: bool,
    ) -> dict:
        """Build the exact request body for Ollama's generate endpoint."""

        payload = {
            "model": model_name,
            "prompt": prompt,
        }
        if images:
            payload["images"] = images
        payload["stream"] = stream
        payload["think"] = think
        payload["options"] = options
        if instruction:
            payload["system"] = instruction
        return payload

    @staticmethod
    def _build_chat_payload(
        *,
        model_name: str,
        prompt: str,
        options: dict,
        think: bool | str,
        instruction: str = "",
        images: list[str] | None = None,
        stream: bool,
    ) -> dict:
        """Build the exact request body for Ollama's chat endpoint."""

        messages = []
        if instruction:
            messages.append({"role": "system", "content": instruction})
        user_message = {"role": "user", "content": prompt}
        if images:
            user_message["images"] = images
        messages.append(user_message)
        return {
            "model": model_name,
            "messages": messages,
            "stream": stream,
            "think": think,
            "options": options,
        }

    def build_task_payload(
        self,
        task: object,
        task_kind: str,
        *,
        image_path: Path | None = None,
    ) -> dict:
        """Return the request body a typed task would send, without network I/O."""

        task_config = self._read_task(task)
        instruction = task_config.get("instruction", "")
        options = self._task_options(task_config)
        if task_kind in {"prompt", "translate"}:
            return self._build_generate_payload(
                model_name=task_config["model"],
                prompt=task_config["prompt"],
                options=options,
                think=task_config.get("think", False),
                instruction=instruction,
                stream=True,
            )
        if task_kind not in {"ocr", "describe"}:
            raise ValueError(f"Unsupported task type for request building: {task_kind!r}")
        if image_path is None:
            raise ValueError(f"An image path is required for a {task_kind} task.")
        image_base64, _original_size, _request_size = self._prepare_image(task_config, image_path)
        if task_kind == "ocr":
            return self._build_generate_payload(
                model_name=task_config["model"],
                prompt=task_config["prompt"],
                options=options,
                think=task_config.get("think", False),
                instruction=instruction,
                images=[image_base64],
                stream=False,
            )
        return self._build_chat_payload(
            model_name=task_config["model"],
            prompt=task_config["prompt"],
            options=options,
            think=task_config.get("think", False),
            instruction=instruction,
            images=[image_base64],
            stream=True,
        )

    @staticmethod
    def _prepare_image(task_config: dict, image_path: Path) -> tuple[str, tuple[int, int], tuple[int, int]]:
        """Read, resize, and Base64-encode one image for an Ollama request."""

        max_image_size = task_config.get("max_image_size")
        if (
            not isinstance(max_image_size, int)
            or isinstance(max_image_size, bool)
            or max_image_size <= 0
        ):
            raise ValueError('Image task requires a positive whole-number "max_image_size" field.')
        image_bytes = image_path.read_bytes()
        request_bytes, original_size, request_size = resize_image_for_request(
            image_bytes,
            max_image_size,
        )
        return image_bytes_to_ollama_base64(request_bytes), original_size, request_size

    def run_ocr_task(self, task: object, image_path: Path, response_path: Path) -> int:
        """Run one image OCR task through Ollama's generate endpoint."""

        reporter = Reporter(None, time_trace=self.time_trace)
        try:
            if requests is None:
                reporter.write("The 'requests' package is required to contact Ollama.")
                return 1

            task_config = self._read_task(task)
            self._configure_task_debug(task_config)
            payload = self.build_task_payload(task_config, "ocr", image_path=image_path)

            with requests.Session() as session:
                if not self._check_server(reporter, session):
                    return 1
                if not self.debug_enabled:
                    reporter.write("Sending OCR request to Ollama...")
                response = session.post(
                    self.api_url,
                    json=payload,
                    timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
                )
                missing_model_message = self._missing_model_message(response)
                if missing_model_message:
                    raise ModelUnavailableError(missing_model_message)
                response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or not isinstance(result.get("response"), str):
                raise ValueError("Ollama OCR response does not contain text.")
            text = result["response"]
            response_path.write_text(text, encoding=TEXT_OUTPUT_ENCODING)
            reporter.write(text, color=Reporter.GREEN, trace=False)
            if self.on_response_text:
                self.on_response_text(text)
            if not self.debug_enabled:
                reporter.write("OCR response complete.")
            return 0
        except ModelUnavailableError as error:
            reporter.write(f"ERROR: OCR task skipped because the model is unavailable: {error}")
            return MODEL_UNAVAILABLE_EXIT_CODE
        except (OSError, ValueError, json.JSONDecodeError, requests.RequestException) as error:
            reporter.write(f"OCR task failed: {error}")
            return 1
        finally:
            reporter.close()

    def run_describe_task(self, task: object, image_path: Path, response_path: Path) -> int:
        """Run one image-description task through Ollama's chat endpoint."""

        reporter = Reporter(None, time_trace=self.time_trace)
        response_file: TextIO | None = None
        try:
            if requests is None:
                reporter.write("The 'requests' package is required to contact Ollama.")
                return 1

            task_config = self._read_task(task)
            self._configure_task_debug(task_config)
            payload = self.build_task_payload(task_config, "describe", image_path=image_path)
            response_file = response_path.open("w", encoding=TEXT_OUTPUT_ENCODING)
            response_parts: list[str] = []

            with requests.Session() as session:
                if not self._check_server(reporter, session):
                    return 1
                if not self.debug_enabled:
                    reporter.write("Sending image-description request to Ollama...")
                with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    stream=True,
                    timeout=(CONNECT_TIMEOUT_SECONDS, self.read_timeout_seconds),
                ) as response:
                    missing_model_message = self._missing_model_message(response)
                    if missing_model_message:
                        raise ModelUnavailableError(missing_model_message)
                    response.raise_for_status()
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if not isinstance(chunk, dict):
                            raise ValueError("Ollama describe response must be a JSON object.")
                        if isinstance(chunk.get("error"), str):
                            raise ValueError(f"Ollama reported an error: {chunk['error']}")
                        message = chunk.get("message")
                        if not isinstance(message, dict):
                            raise ValueError("Ollama describe response does not contain a message.")
                        text = message.get("content")
                        if isinstance(text, str) and text:
                            response_parts.append(text)
                            response_file.write(text)
                            response_file.flush()
                            reporter.write(text, end="", color=Reporter.GREEN)
                            if self.on_response_text:
                                self.on_response_text(text)
            if not response_parts:
                raise ValueError("Ollama did not return an image description.")
            reporter.write()
            if not self.debug_enabled:
                reporter.write("Image-description response complete.")
            return 0
        except ModelUnavailableError as error:
            reporter.write(f"ERROR: Describe task skipped because the model is unavailable: {error}")
            return MODEL_UNAVAILABLE_EXIT_CODE
        except (OSError, ValueError, json.JSONDecodeError, requests.RequestException) as error:
            reporter.write(f"Describe task failed: {error}")
            return 1
        finally:
            if response_file:
                response_file.close()
            reporter.close()

    def run_task(
        self,
        task: object,
        response_path: Path | None = None,
        *,
        append_response: bool = False,
        response_header: str | None = None,
    ) -> int:
        """Run one text task and stream its response to the terminal.

        The task supplies the model, instruction, prompt, and optional Ollama
        options. Values in the task override defaults from ``ollama.json``.
        """

        reporter = Reporter(None, time_trace=self.time_trace)
        response_file: TextIO | None = None
        try:
            if requests is None:
                reporter.write("The 'requests' package is required to contact Ollama.")
                return 1

            task_config = self._read_task(task)
            self._configure_task_debug(task_config)
            options = self._task_options(task_config)
            self._debug(reporter, "Input prompt:")
            if self.debug_enabled:
                reporter.write(task_config["prompt"])
            instruction = task_config.get("instruction", "")
            if instruction:
                self._debug(reporter, "Input instruction:")
                if self.debug_enabled:
                    reporter.write(instruction)

            with requests.Session() as session:
                if not self._check_server(reporter, session):
                    return 1
                if not self.debug_enabled:
                    reporter.write("Sending request to Ollama...")
                if response_path is not None:
                    separator = "\n\n" if append_response and response_path.is_file() and response_path.stat().st_size else ""
                    response_file = response_path.open(
                        "a" if append_response else "w",
                        encoding=TEXT_OUTPUT_ENCODING,
                    )
                    if separator:
                        response_file.write(separator)
                    if response_header is not None:
                        response_file.write(f"{response_header.strip()}\n")
                return 0 if self._query(
                    reporter=reporter,
                    session=session,
                    prompt=task_config["prompt"],
                    model_name=task_config["model"],
                    options=options,
                    think=task_config.get("think", False),
                    instruction=instruction,
                    compact_report=True,
                    response_file=response_file,
                    report_response=True,
                ) else 1
        except ModelUnavailableError as error:
            reporter.write(f"ERROR: Task skipped because the model is unavailable: {error}")
            return MODEL_UNAVAILABLE_EXIT_CODE
        except (OSError, ValueError, json.JSONDecodeError) as error:
            reporter.write(f"Error while preparing the task: {error}")
            return 1
        finally:
            if response_file:
                response_file.close()
            reporter.close()

    def run(
        self,
        input_path: Path,
        output_path: Path | None = None,
        compact_report: bool = False,
        response_path: Path | None = None,
        append_report: bool = False,
    ) -> int:
        """Process all queries and return the application exit code."""
        started_at = time.monotonic()
        timestamp = datetime.now().strftime("%y%m%d_%H%M")
        report_suffix = DEFAULT_MODEL[0].lower()
        try:
            raw_input_data = self._read_json(input_path)
            if isinstance(raw_input_data, dict):
                raw_model_name = raw_input_data.get("model", DEFAULT_MODEL)
                if isinstance(raw_model_name, str) and raw_model_name:
                    report_suffix = raw_model_name[0].lower()
                raw_appendix = raw_input_data.get("appendix")
                if isinstance(raw_appendix, str) and raw_appendix:
                    report_suffix = raw_appendix
                if self.project_debug_enabled is None and isinstance(raw_input_data.get("debug"), bool):
                    self.debug_enabled = raw_input_data["debug"]
        except (OSError, ValueError, json.JSONDecodeError):
            pass

        if output_path is None:
            output_path = Path(f"output_{timestamp}{report_suffix}.txt")
        else:
            output_path = Path(output_path)
        reporter = Reporter(output_path, append=append_report, time_trace=self.time_trace)
        if self.on_output_path:
            self.on_output_path(output_path)

        if requests is None:
            reporter.write("The 'requests' package is required to contact Ollama.")
            reporter.close()
            return 1

        response_file: TextIO | None = None
        try:
            if response_path is not None:
                response_file = Path(response_path).open("w", encoding=TEXT_OUTPUT_ENCODING)
            if not compact_report:
                reporter.write(f"Ollama API – verze {APPLICATION_VERSION}")
            if self.debug_enabled:
                reporter.write(f"Run record: {datetime.now().isoformat(timespec='seconds')}")
                reporter.write(f"Output file: {output_path.resolve()}")
                reporter.write(f"Loading configuration file: {self.config_path.resolve()}")
                reporter.write(f"Adresa Ollamy: {self.base_url}")
                reporter.write(f"DEBUG = {self.debug_enabled}")
                reporter.write(f"Loading input file: {input_path.resolve()}")
            input_data = self._read_input(input_path)
            queries = input_data["queries"]
            model_name = input_data.get("model", DEFAULT_MODEL)
            if not isinstance(model_name, str) or not model_name:
                raise ValueError('The "model" field in input.json must be non-empty text.')
            if self.project_debug_enabled is None:
                self.debug_enabled = input_data.get("debug", self.default_debug_enabled)
            session_options = self.default_options | self._read_options(input_data, source="input.json")
            think = input_data.get("think", False)
            if self.debug_enabled:
                reporter.write(f"Queries loaded: {len(queries)}")
            self._debug(reporter, f"Default session options: {json.dumps(session_options, ensure_ascii=False)}")

            with requests.Session() as session:
                if not self._check_server(reporter, session):
                    return 1

                succeeded = 0
                for index, query in enumerate(queries, start=1):
                    query_model_name = query.get("model", model_name)
                    query_options = session_options | self._read_options(
                        query,
                        source=f"dotaz {index} v input.json",
                    )
                    if compact_report:
                        reporter.write(f"[{index}] Model name: {query_model_name}")
                        reporter.write(f"Temperature: {query_options['temperature']}")
                        reporter.write("Output:")
                    elif self.debug_enabled:
                        reporter.write(f"\n{'=' * 60}\nDotaz {index} z {len(queries)}")
                    elif index > 1:
                        reporter.write()
                    query_started_at = time.monotonic()
                    if self._query(
                        reporter=reporter,
                        session=session,
                        prompt=query["prompt"],
                        model_name=query_model_name,
                        options=query_options,
                        think=query.get("think", think),
                        instruction=query.get("instruction", ""),
                        compact_report=compact_report,
                        response_file=response_file,
                        report_response=response_file is None,
                    ):
                        succeeded += 1
                    if compact_report:
                        query_elapsed_seconds = time.monotonic() - query_started_at
                        reporter.write(f"Processing time: {query_elapsed_seconds:.1f} s")
                        if index < len(queries):
                            reporter.write("----")

            elapsed_seconds = int(time.monotonic() - started_at)
            minutes, seconds = divmod(elapsed_seconds, 60)
            if compact_report:
                pass
            elif self.debug_enabled:
                reporter.write(f"\nDone: successfully processed {succeeded} of {len(queries)} queries.")
                reporter.write(f"Total time: {minutes} minutes {seconds} seconds.")
            else:
                reporter.write(f"Total time: {minutes} minutes {seconds} seconds.")
            return 0 if succeeded == len(queries) else 1
        except ModelUnavailableError as error:
            reporter.write(f"ERROR: Run skipped because the model is unavailable: {error}")
            return MODEL_UNAVAILABLE_EXIT_CODE
        except (OSError, ValueError, json.JSONDecodeError) as error:
            reporter.write(f"Error while preparing the run: {error}")
            return 1
        finally:
            if response_file:
                response_file.close()
            reporter.close()


OllamaApi = ollama_api

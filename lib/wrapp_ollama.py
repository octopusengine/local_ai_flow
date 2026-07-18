"""Client for batch request processing through the local Ollama API."""

import json
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

import requests


DEFAULT_MODEL = "deepseek-r1:14b"
APPLICATION_VERSION = "0.2"
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 300
OPTION_NAMES = ("seed", "num_predict", "num_ctx", "temperature", "repeat_penalty")
INTEGER_OPTIONS = {"seed", "num_predict", "num_ctx"}


class Reporter:
    """Write messages to both the terminal and a report file."""

    GRAY = "\033[90m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    def __init__(self, output_path: Path, *, append: bool = False) -> None:
        self.file = output_path.open("a" if append else "w", encoding="utf-8")
        self.use_colors = sys.stdout.isatty()

    def write(
        self,
        message: str = "",
        end: str = "\n",
        flush: bool = True,
        color: str = GRAY,
    ) -> None:
        terminal_message = message
        if self.use_colors and message:
            terminal_message = f"{color}{message}{self.RESET}"
        print(terminal_message, end=end, flush=flush)
        self.file.write(message + end)
        if flush:
            self.file.flush()

    def close(self) -> None:
        self.file.close()


class ollama_api:
    """Load configuration and send all input.json requests to Ollama."""

    def __init__(
        self,
        config_path: Path,
        on_response_text: Callable[[str], None] | None = None,
        on_prompt: Callable[[str], None] | None = None,
        on_output_path: Callable[[Path], None] | None = None,
    ) -> None:
        self.config_path = config_path
        self.on_response_text = on_response_text
        self.on_prompt = on_prompt
        self.on_output_path = on_output_path
        config = self._read_config(config_path)
        self.base_url = config["url"]
        self.debug_enabled = config["debug"]
        self.default_options = config["default_options"]
        self.api_url = f"{self.base_url}/api/generate"
        self.version_url = f"{self.base_url}/api/version"

    @staticmethod
    def _read_json(path: Path) -> dict:
        with path.open(encoding="utf-8") as source_file:
            return json.load(source_file)

    @classmethod
    def _read_config(cls, config_path: Path) -> dict:
        data = cls._read_json(config_path)
        url = data.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError('config.json must contain a non-empty "url" field.')
        if not isinstance(data.get("debug"), bool):
            raise ValueError('The "debug" field in config.json must be true or false.')
        if not isinstance(data.get("ffmpeg"), str) or not data["ffmpeg"].strip():
            raise ValueError('Pole "ffmpeg" v config.json musi byt neprazdny text.')
        default_options = cls._read_options(
            data.get("default_options"),
            source="default_options v config.json",
            require_all=True,
        )
        return {
            "url": url.rstrip("/"),
            "ffmpeg": data["ffmpeg"],
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

    def _check_server(self, reporter: Reporter, session: requests.Session) -> bool:
        if self.debug_enabled:
            reporter.write(f"Trying to connect to the Ollama server: {self.version_url}")
        self._debug(reporter, f"Connection timeout: {CONNECT_TIMEOUT_SECONDS} s")
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
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "think": think,
            "options": options,
        }
        if instruction:
            payload["system"] = instruction

        if self.debug_enabled:
            reporter.write(f"Trying to send a request to: {self.api_url}")
            reporter.write(f"Model: {model_name}; parametry: {json.dumps(options, ensure_ascii=False)}")
        elif not compact_report:
            reporter.write(f"Model: {model_name}")
        if not compact_report:
            reporter.write(f"Prompt: {prompt}")
        if instruction and self.debug_enabled:
            reporter.write(f"Additional instruction: {instruction}")
        if not self.debug_enabled and not compact_report:
            reporter.write(f"Parametry: {json.dumps(options, ensure_ascii=False)}")
        self._debug(reporter, f"Outgoing JSON: {json.dumps(payload, ensure_ascii=False)}")

        try:
            response = session.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            )
            if self.debug_enabled:
                reporter.write(f"Server response: HTTP {response.status_code} {response.reason}")
            self._debug(reporter, f"Response headers: {dict(response.headers)}")
            response.raise_for_status()
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
        self._debug(reporter, f"Final server data: {json.dumps(final_chunk, ensure_ascii=False)}")
        return True

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
                if isinstance(raw_input_data.get("debug"), bool):
                    self.debug_enabled = raw_input_data["debug"]
        except (OSError, ValueError, json.JSONDecodeError):
            pass

        if output_path is None:
            output_path = Path(f"output_{timestamp}{report_suffix}.txt")
        else:
            output_path = Path(output_path)
        reporter = Reporter(output_path, append=append_report)
        if self.on_output_path:
            self.on_output_path(output_path)

        response_file: TextIO | None = None
        try:
            if response_path is not None:
                response_file = Path(response_path).open("w", encoding="utf-8")
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
            self.debug_enabled = input_data.get("debug", self.debug_enabled)
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
        except (OSError, ValueError, json.JSONDecodeError) as error:
            reporter.write(f"Error while preparing the run: {error}")
            return 1
        finally:
            if response_file:
                response_file.close()
            reporter.close()


OllamaApi = ollama_api

"""Reusable local wrapper around OpenAI Whisper."""

from __future__ import annotations

import contextlib
import json
import logging
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.wrapp_ffmpeg import prepare_ffmpeg


LIBRARY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = LIBRARY_DIR.parent
CONFIG_PATH = LIBRARY_DIR / "whisper.json"
PROJECT_CONFIG_PATH = PROJECT_ROOT / "project.json"


@dataclass(frozen=True)
class WhisperConfig:
    """Runtime settings loaded from lib/whisper.json."""

    debug: bool
    language: str | None
    model: str
    model_directory: Path
    source_directory: Path
    export_directory: Path


class StreamToLogger:
    """Send output written by a library to the application log."""

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger = logger
        self.level = level
        self._buffer = ""

    def write(self, message: str) -> int:
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.logger.log(self.level, "WHISPER: %s", line.rstrip())
        return len(message)

    def flush(self) -> None:
        if self._buffer.strip():
            self.logger.log(self.level, "WHISPER: %s", self._buffer.rstrip())
        self._buffer = ""


def _resolve_config_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (LIBRARY_DIR / path).resolve()


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration key '{key}' must be a non-empty string.")
    return value


def load_project_directory() -> Path:
    """Load the working subdirectory configured in project.json."""

    try:
        data = json.loads(PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Project configuration does not exist: {PROJECT_CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {PROJECT_CONFIG_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Project configuration root must be an object: {PROJECT_CONFIG_PATH}")

    subdir = _required_string(data, "subdir")
    configured_path = Path(subdir)
    if configured_path.is_absolute():
        raise ValueError("Project configuration key 'subdir' must be a relative path.")

    project_directory = (PROJECT_ROOT / configured_path).resolve()
    try:
        project_directory.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("Project configuration key 'subdir' must remain inside the project.") from error

    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


def load_config() -> WhisperConfig:
    """Load and validate the central project configuration."""

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Configuration file does not exist: {CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {CONFIG_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be an object: {CONFIG_PATH}")

    debug = data.get("debug", False)
    if not isinstance(debug, bool):
        raise ValueError("Configuration key 'debug' must be true or false.")

    language = data.get("language")
    if language is not None and (not isinstance(language, str) or not language.strip()):
        raise ValueError("Configuration key 'language' must be a language code or null.")

    project_directory = load_project_directory()
    return WhisperConfig(
        debug=debug,
        language=language,
        model=_required_string(data, "model"),
        model_directory=_resolve_config_path(_required_string(data, "model_directory")),
        source_directory=project_directory,
        export_directory=project_directory,
    )


def create_logger(application_name: str, export_directory: Path) -> tuple[logging.Logger, Path]:
    """Create console and detailed file logging for one transcription run."""

    export_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%y%m%d_%H%M")
    log_path = export_directory / f"log_{timestamp}.txt"
    sequence = 1
    while log_path.exists():
        log_path = export_directory / f"log_{timestamp}_{sequence:02d}.txt"
        sequence += 1

    logger = logging.getLogger(application_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger, log_path


def find_first_media_file(source_directory: Path, extension: str) -> Path:
    """Return the first alphabetically sorted media file with the required extension."""

    if not source_directory.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_directory}")

    normalized_extension = f".{extension.lstrip('.').casefold()}"
    media_files = sorted(
        (
            path
            for path in source_directory.iterdir()
            if path.is_file() and path.suffix.casefold() == normalized_extension
        ),
        key=lambda path: path.name.casefold(),
    )
    if not media_files:
        raise FileNotFoundError(
            f"No {normalized_extension} file found in: {source_directory}"
        )
    return media_files[0]


def write_transcript(transcript_path: Path, source_path: Path, result: dict[str, Any]) -> None:
    """Write the recognized text and basic processing metadata."""

    text = str(result.get("text", "")).strip()
    transcript_path.write_text(
        f"Source file: {source_path.name}\n"
        f"Whisper language: {result.get('language', 'unknown')}\n\n"
        f"{text}\n",
        encoding="utf-8",
    )


def apply_runtime_overrides(
    config: WhisperConfig,
    *,
    debug: bool | None,
    language: str | None,
    model: str | None,
) -> WhisperConfig:
    """Apply the three values that a test script may override."""

    if debug is not None and not isinstance(debug, bool):
        raise ValueError("The test override 'debug' must be true, false, or None.")
    if language is not None and not isinstance(language, str):
        raise ValueError("The test override 'language' must be a string or None.")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("The test override 'model' must be a non-empty string or None.")

    effective_language = None if language == "auto" else language
    return replace(
        config,
        debug=config.debug if debug is None else debug,
        language=config.language if language is None else effective_language,
        model=config.model if model is None else model,
    )


def run_transcription(
    extension: str,
    application_name: str,
    *,
    debug: bool | None = None,
    language: str | None = None,
    model: str | None = None,
    source_file: Path | None = None,
) -> int:
    """Transcribe the first selected media type and return a process exit code."""

    config = apply_runtime_overrides(
        load_config(), debug=debug, language=language, model=model
    )
    logger, log_path = create_logger(application_name, config.export_directory)
    logger.info("Started transcription test")
    logger.info("Configuration file: %s", CONFIG_PATH)
    logger.info(
        "Test overrides: debug=%r, language=%r, model=%r", debug, language, model
    )
    logger.info("Log file: %s", log_path)

    try:
        if source_file is None:
            source_path = find_first_media_file(config.source_directory, extension)
        else:
            source_path = source_file.resolve()
            try:
                source_path.relative_to(config.source_directory)
            except ValueError as error:
                raise ValueError(
                    f"Source file must be inside the project directory: {source_path}"
                ) from error
            if source_path.parent != config.source_directory:
                raise ValueError(
                    f"Source file must be directly in the project directory root: {source_path}"
                )
            if source_path.suffix.casefold() != f".{extension.lstrip('.').casefold()}":
                raise ValueError(f"Source file must have the .{extension.lstrip('.')} extension.")
            if not source_path.is_file():
                raise FileNotFoundError(f"Source file does not exist: {source_path}")
        transcript_path = config.export_directory / f"{source_path.stem}.txt"
        logger.info("Selected %s: %s", extension.upper(), source_path)
        logger.info("Source file size: %d bytes", source_path.stat().st_size)
        logger.info("Transcript destination: %s", transcript_path)
        logger.info("Using FFmpeg from central configuration: %s", prepare_ffmpeg())

        logger.info("Importing Whisper package")
        try:
            import whisper
        except ModuleNotFoundError as error:
            if error.name == "whisper":
                raise RuntimeError(
                    "The 'openai-whisper' package is missing. "
                    "Install project dependencies with: python -m pip install -r requirements.txt"
                ) from error
            raise

        logger.info("Loading Whisper model: %s", config.model)
        logger.info("Whisper model directory: %s", config.model_directory)
        with contextlib.redirect_stdout(StreamToLogger(logger, logging.INFO)), contextlib.redirect_stderr(
            StreamToLogger(logger, logging.WARNING)
        ):
            model = whisper.load_model(config.model, download_root=str(config.model_directory))
            logger.info("Starting transcription; language=%s", config.language or "auto-detect")
            result = model.transcribe(
                str(source_path), language=config.language, verbose=config.debug
            )

        write_transcript(transcript_path, source_path, result)
        logger.info("Transcript written successfully")
        logger.info("Finished successfully")
        return 0
    except Exception:
        logger.exception("Transcription failed")
        logger.error("Finished with an error. See this log for the complete report: %s", log_path)
        return 1
    finally:
        for handler in logger.handlers:
            handler.flush()
            handler.close()


def main(
    extension: str,
    application_name: str,
    *,
    debug: bool | None = None,
    language: str | None = None,
    model: str | None = None,
    source_file: Path | None = None,
) -> None:
    """Run a small test script and exit with its result."""

    sys.exit(
        run_transcription(
            extension,
            application_name,
            debug=debug,
            language=language,
            model=model,
            source_file=source_file,
        )
    )

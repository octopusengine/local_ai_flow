"""Shared FFmpeg configuration and execution helpers for audio and video tasks."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


LIBRARY_DIR = Path(__file__).resolve().parent
CONFIG_PATH = LIBRARY_DIR / "ffmpeg.json"


@dataclass(frozen=True)
class FFmpegConfig:
    """Location of the FFmpeg executable shared by project tools."""

    executable: Path


def load_config() -> FFmpegConfig:
    """Load and validate the central FFmpeg executable path."""

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"FFmpeg configuration does not exist: {CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {CONFIG_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"FFmpeg configuration root must be an object: {CONFIG_PATH}")

    configured_path = data.get("ffmpeg")
    if not isinstance(configured_path, str) or not configured_path.strip():
        raise ValueError(f"Configuration key 'ffmpeg' must be a non-empty string: {CONFIG_PATH}")

    executable = Path(configured_path)
    if not executable.is_absolute():
        executable = (LIBRARY_DIR / executable).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"FFmpeg executable was not found: {executable}")
    return FFmpegConfig(executable=executable)


def get_ffmpeg_path() -> Path:
    """Return the configured FFmpeg executable path."""

    return load_config().executable


def prepare_ffmpeg() -> Path:
    """Make the configured FFmpeg discoverable to libraries that call it by name."""

    executable = get_ffmpeg_path()
    executable_directory = str(executable.parent)
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if executable_directory not in path_entries:
        os.environ["PATH"] = f"{executable_directory}{os.pathsep}{os.environ.get('PATH', '')}"
    return executable


def run_ffmpeg(
    arguments: Sequence[str | Path], *, check: bool = True
) -> subprocess.CompletedProcess:
    """Run configured FFmpeg with caller-supplied audio or video arguments."""

    command = [str(get_ffmpeg_path()), *(str(argument) for argument in arguments)]
    return subprocess.run(command, check=check)

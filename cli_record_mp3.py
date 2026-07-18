"""Record a microphone message to an MP3 file.

Usage:
    python record_mp3.py
    python record_mp3.py rec_123.mp3
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from lib.wrapp_cli_log import project_log, read_log_enabled
from lib.wrapp_ffmpeg import get_ffmpeg_path


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG_PATH = PROJECT_ROOT / "project.json"
CLI_CONFIG_PATH = PROJECT_ROOT / "cli_record_mp3.json"
RECORD_CONFIG_PATH = PROJECT_ROOT / "lib" / "record.json"
SAMPLE_RATE = 44_100
CHANNELS = 1
BITRATE = "128k"
BLOCK_SIZE = 1_024


@dataclass(frozen=True)
class RecordConfig:
    """Settings loaded from lib/record.json."""

    gain_db: float


def load_project_directory() -> Path:
    """Load the working subdirectory configured in project.json."""

    try:
        data = json.loads(PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Configuration file does not exist: {PROJECT_CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {PROJECT_CONFIG_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be an object: {PROJECT_CONFIG_PATH}")

    subdir = data.get("subdir")
    if not isinstance(subdir, str) or not subdir.strip():
        raise ValueError("The 'subdir' setting in project.json must be non-empty text.")

    configured_path = Path(subdir)
    if configured_path.is_absolute():
        raise ValueError("The 'subdir' setting in project.json must be a relative path.")

    project_directory = (PROJECT_ROOT / configured_path).resolve()
    try:
        project_directory.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError("The 'subdir' setting in project.json must remain inside the project.") from error

    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


def parse_arguments(project_directory: Path) -> argparse.Namespace:
    """Return command-line options."""

    parser = argparse.ArgumentParser(
        description="Record the microphone to MP3; press any key to stop recording."
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=project_directory / "record.mp3",
        help=(
            "MP3 destination directly in the project directory root "
            f"{project_directory.name!r} from project.json (default: record.mp3)"
        ),
    )
    parser.add_argument(
        "--gain-db",
        type=float,
        help="software gain in dB; overrides the value in lib/record.json",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    return parser.parse_args()


def validate_gain_db(value: object) -> float:
    """Return a safe software gain value for the FFmpeg volume filter."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("The 'gain_db' setting must be a number.")
    gain_db = float(value)
    if not math.isfinite(gain_db) or not -30.0 <= gain_db <= 30.0:
        raise ValueError("The 'gain_db' setting must be between -30 and 30 dB.")
    return gain_db


def load_record_config() -> RecordConfig:
    """Load and validate microphone recording settings."""

    try:
        data = json.loads(RECORD_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Configuration file does not exist: {RECORD_CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {RECORD_CONFIG_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be an object: {RECORD_CONFIG_PATH}")
    return RecordConfig(gain_db=validate_gain_db(data.get("gain_db")))


def find_ffmpeg() -> str:
    """Return the executable configured in lib/ffmpeg.json."""

    return str(get_ffmpeg_path())


def normalize_output_path(output: Path, project_directory: Path) -> Path:
    """Ensure the destination is an MP3 path and its directory exists."""

    output = output.expanduser()
    if output.suffix.lower() != ".mp3":
        raise ValueError("The destination file must have a .mp3 extension.")
    if not output.is_absolute():
        output = project_directory / output
    output = output.resolve()
    try:
        output.relative_to(project_directory)
    except ValueError as error:
        raise ValueError("The destination file must be inside the project directory from project.json.") from error
    if output.parent != project_directory:
        raise ValueError("The destination file must be directly in the project directory root.")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def record(output: Path, ffmpeg: str, gain_db: float) -> float:
    """Record mono 16-bit PCM from the default microphone and encode it to MP3."""

    try:
        import sounddevice as sd
    except ImportError as error:
        raise RuntimeError(
            "The sounddevice package is missing. Run: python -m pip install -r requirements.txt"
        ) from error

    if os.name != "nt":
        raise RuntimeError("This version supports keyboard-controlled recording only on Windows.")

    import msvcrt

    ffmpeg_process = subprocess.Popen(
        [
            ffmpeg,
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            str(CHANNELS),
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            BITRATE,
            "-af",
            f"volume={gain_db:+g}dB",
            str(output),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if ffmpeg_process.stdin is None or ffmpeg_process.stderr is None:
        raise RuntimeError("Could not create input for FFmpeg.")

    print(f"Destination: {output}")
    print(f"Software gain: {gain_db:+g} dB")
    print("Recording started. Speak into the microphone; press any key to stop.")
    started_at = time.monotonic()

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=CHANNELS,
            dtype="int16",
        ) as microphone:
            while True:
                audio, overflowed = microphone.read(BLOCK_SIZE)
                if overflowed:
                    print("WARNING: Some audio could not be processed in time.", file=sys.stderr)
                ffmpeg_process.stdin.write(audio)
                if msvcrt.kbhit():
                    msvcrt.getwch()
                    break
    except KeyboardInterrupt:
        print("\nRecording stopped with Ctrl+C.")
    finally:
        ffmpeg_process.stdin.close()

    stderr = ffmpeg_process.stderr.read().decode("utf-8", errors="replace")
    exit_code = ffmpeg_process.wait()
    if exit_code != 0:
        raise RuntimeError(f"FFmpeg did not finish saving the MP3:\n{stderr.strip()}")

    return time.monotonic() - started_at


def main() -> int:
    """Run the recorder CLI."""

    try:
        project_directory = load_project_directory()
        log_enabled = read_log_enabled(CLI_CONFIG_PATH)
        args = parse_arguments(project_directory)
    except (FileNotFoundError, RuntimeError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with project_log(project_directory, "cli_record_mp3.py", log_enabled):
        try:
            output = normalize_output_path(args.output, project_directory)
            config = load_record_config()
            gain_db = config.gain_db if args.gain_db is None else validate_gain_db(args.gain_db)
            duration = record(output, find_ffmpeg(), gain_db)
        except (FileNotFoundError, RuntimeError, ValueError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

        print(f"Saved: {output} ({duration:.1f} s)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

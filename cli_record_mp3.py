"""Record a microphone message to an MP3 file.

Usage:
    python record_mp3.py
    python record_mp3.py rec_123.mp3
"""

from __future__ import annotations

import argparse
import array
import json
import math
import os
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from lib.wrapp_log import console_log, read_log_enabled
from lib.wrapp_ffmpeg import get_ffmpeg_path
from lib.wrapp_system import get_platform_system


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG_PATH = PROJECT_ROOT / "project.json"
RECORD_CONFIG_PATH = PROJECT_ROOT / "lib" / "record.json"
SAMPLE_RATE = 44_100
CHANNELS = 1
BITRATE = "128k"
BLOCK_SIZE = 1_024


@dataclass(frozen=True)
class RecordConfig:
    """Settings loaded from lib/record.json."""

    gain_db: float


class StopKeyReader:
    """Read one stop key without changing Windows recording behavior."""

    def __init__(self, system: str) -> None:
        self.system = system
        self._msvcrt = None
        self._termios = None
        self._stdin_settings = None

    def __enter__(self) -> "StopKeyReader":
        if self.system == "Windows":
            import msvcrt

            self._msvcrt = msvcrt
            return self
        if self.system == "Linux":
            if not sys.stdin.isatty():
                raise RuntimeError("Linux recording requires an interactive terminal; use Ctrl+C to stop it.")
            import termios
            import tty

            self._termios = termios
            self._stdin_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            return self
        raise RuntimeError(f"Microphone recording is not supported on {self.system}.")

    def key_pressed(self) -> bool:
        if self.system == "Windows":
            assert self._msvcrt is not None
            if self._msvcrt.kbhit():
                self._msvcrt.getwch()
                return True
            return False
        if self.system == "Linux":
            readable, _unused_write, _unused_error = select.select([sys.stdin], [], [], 0)
            if readable:
                sys.stdin.read(1)
                return True
            return False
        return False

    def __exit__(self, _exception_type: object, _exception: object, _traceback: object) -> None:
        if self._termios is not None and self._stdin_settings is not None:
            self._termios.tcsetattr(sys.stdin.fileno(), self._termios.TCSADRAIN, self._stdin_settings)


def list_input_devices(sd: object) -> list[tuple[int, str, int, int]]:
    """Return available input devices as index, name, channels, and rate."""

    try:
        devices = sd.query_devices()  # type: ignore[attr-defined]
    except Exception as error:
        raise RuntimeError(f"Could not query microphone devices: {error}") from error

    result: list[tuple[int, str, int, int]] = []
    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            continue
        channels = int(device.get("max_input_channels", 0))
        if channels < 1:
            continue
        try:
            sample_rate = round(float(device.get("default_samplerate", 0)))
        except (TypeError, ValueError):
            sample_rate = 0
        result.append((index, str(device.get("name") or f"input {index}"), channels, sample_rate))
    return result


def get_input_device(sd: object, system: str, requested_device: str | None) -> tuple[object | None, str, int]:
    """Return the selected input device, its name, and a capture sample rate."""

    try:
        device_id: object | None = None if requested_device is None else requested_device
        if requested_device is not None and requested_device.isdecimal():
            device_id = int(requested_device)
        device = sd.query_devices(device_id, kind="input")  # type: ignore[attr-defined]
    except Exception as error:
        selected = "the selected microphone" if requested_device is not None else "the default microphone"
        raise RuntimeError(f"Could not query {selected}: {error}") from error
    if not isinstance(device, dict) or int(device.get("max_input_channels", 0)) < 1:
        raise RuntimeError("The selected device is not an input microphone.")

    device_name = str(device.get("name") or "default input device")
    if system == "Linux":
        try:
            sample_rate = round(float(device["default_samplerate"]))
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("The default Linux microphone has no usable sample rate.") from None
        if sample_rate <= 0:
            raise RuntimeError("The default Linux microphone has no usable sample rate.")
        return device_id, device_name, sample_rate
    return device_id, device_name, SAMPLE_RATE


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
    parser.add_argument(
        "--device",
        help="input device index or name; use --list-devices to see available microphones",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="list available input microphones and exit",
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


def peak_dbfs(peak: int) -> float:
    """Convert a signed 16-bit peak sample value to dBFS."""

    return -math.inf if peak <= 0 else 20 * math.log10(peak / 32767)


def record(output: Path, ffmpeg: str, gain_db: float, requested_device: str | None) -> tuple[float, int]:
    """Record mono 16-bit PCM from the default microphone and encode it to MP3."""

    try:
        import sounddevice as sd
    except ImportError as error:
        raise RuntimeError(
            "The sounddevice package is missing. Run: python -m pip install -r requirements.txt"
        ) from error

    system = get_platform_system()
    device, device_name, sample_rate = get_input_device(sd, system, requested_device)

    ffmpeg_process = subprocess.Popen(
        [
            ffmpeg,
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(sample_rate),
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
    print(f"Platform: {system}; microphone: {device_name}; sample rate: {sample_rate} Hz")
    print(f"Software gain: {gain_db:+g} dB")
    print("Recording started. Speak into the microphone; press any key to stop.")
    started_at = time.monotonic()
    peak = 0
    last_meter_at = started_at

    try:
        with StopKeyReader(system) as stop_keys:
            with sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=BLOCK_SIZE,
                channels=CHANNELS,
                dtype="int16",
                device=device,
            ) as microphone:
                while True:
                    audio, overflowed = microphone.read(BLOCK_SIZE)
                    if overflowed:
                        print("WARNING: Some audio could not be processed in time.", file=sys.stderr)
                    ffmpeg_process.stdin.write(audio)
                    samples = array.array("h")
                    samples.frombytes(bytes(audio))
                    if samples:
                        peak = max(peak, max(abs(sample) for sample in samples))
                    now = time.monotonic()
                    if now - last_meter_at >= 0.4:
                        level = "silence" if peak == 0 else f"{peak_dbfs(peak):.1f} dBFS peak"
                        print(f"\rInput level: {level}   ", end="", flush=True)
                        last_meter_at = now
                    if stop_keys.key_pressed():
                        break
    except KeyboardInterrupt:
        print("\nRecording stopped with Ctrl+C.")
    finally:
        ffmpeg_process.stdin.close()

    stderr = ffmpeg_process.stderr.read().decode("utf-8", errors="replace")
    exit_code = ffmpeg_process.wait()
    if exit_code != 0:
        raise RuntimeError(f"FFmpeg did not finish saving the MP3:\n{stderr.strip()}")

    print()
    return time.monotonic() - started_at, peak


def main() -> int:
    """Run the recorder CLI."""

    try:
        project_directory = load_project_directory()
        log_enabled = read_log_enabled(PROJECT_CONFIG_PATH)
        args = parse_arguments(project_directory)
    except (FileNotFoundError, RuntimeError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with console_log(project_directory, "cli_record_mp3.py", log_enabled):
        try:
            if args.list_devices:
                try:
                    import sounddevice as sd
                except ImportError as error:
                    raise RuntimeError(
                        "The sounddevice package is missing. Run: python -m pip install -r requirements.txt"
                    ) from error

                devices = list_input_devices(sd)
                if not devices:
                    raise RuntimeError("No input microphones are available.")
                print("Available input microphones:")
                for index, name, channels, sample_rate in devices:
                    print(f"  {index}: {name} ({channels} channel(s), {sample_rate} Hz)")
                return 0
            output = normalize_output_path(args.output, project_directory)
            config = load_record_config()
            gain_db = config.gain_db if args.gain_db is None else validate_gain_db(args.gain_db)
            duration, peak = record(output, find_ffmpeg(), gain_db, args.device)
        except (FileNotFoundError, RuntimeError, ValueError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

        level = "silence" if peak == 0 else f"{peak_dbfs(peak):.1f} dBFS peak"
        print(f"Saved: {output} ({duration:.1f} s; input level: {level})")
        if peak_dbfs(peak) < -50:
            print(
                "WARNING: The input signal was nearly silent. Run with --list-devices, then choose "
                "the correct microphone with --device INDEX."
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

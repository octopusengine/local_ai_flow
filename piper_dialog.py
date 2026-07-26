"""Přehrává dialog ze zvoleného textového souboru českými hlasy Piperu."""

import argparse
import subprocess
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path

import winsound

from ollama_piper import read_ffmpeg_path


PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_DIR / "lib" / "ollama.json"
DIALOG_FILE = PROJECT_DIR / "dialog.txt"
ASSETS_DIR = PROJECT_DIR / "assets"

VOICE1CZ = "honza"
VOICE2CZ = "jirka"
MP3 = True
SHORT_PAUSE_SECONDS = 1.5
LONG_PAUSE_SECONDS = 4.5

VOICE_MODELS = {
    "honza": ASSETS_DIR / "cs_CZ-honza-medium.onnx",
    "jirka": ASSETS_DIR / "cs_CZ-jirka-medium.onnx",
}
SPEAKERS = {
    "voice1cz": VOICE1CZ,
    "voice2cz": VOICE2CZ,
}


def read_dialog(path: Path) -> list[tuple[str, str | float]]:
    """Načte repliky; prázdné řádky vloží prodlevu mezi jednotlivé repliky."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(f"Nelze načíst dialog {path}: {error}") from error

    events: list[tuple[str, str | float]] = []
    speaker: str | None = None
    text_parts: list[str] = []
    blank_lines = 0

    def flush_speech() -> None:
        nonlocal speaker, text_parts
        if speaker is None:
            return
        text = " ".join(part.strip() for part in text_parts).strip()
        if not text:
            raise ValueError(f"Mluvčí {speaker} nemá text repliky.")
        events.append((speaker, text))
        speaker = None
        text_parts = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            flush_speech()
            blank_lines += 3 if len(raw_line) >= 3 else 1
            continue

        if blank_lines and events:
            pause_seconds = LONG_PAUSE_SECONDS if blank_lines >= 3 else SHORT_PAUSE_SECONDS
            events.append(("pause", pause_seconds))
        blank_lines = 0

        if ":" in line:
            flush_speech()
            speaker, text = (part.strip() for part in line.split(":", maxsplit=1))
            if speaker not in SPEAKERS:
                raise ValueError(f"Řádek {line_number} používá neznámého mluvčího: {speaker}")
            if text:
                text_parts.append(text)
        elif speaker is not None:
            text_parts.append(line)
        else:
            raise ValueError(f"Řádek {line_number} nemá formát 'mluvčí: text'.")
    flush_speech()

    if not any(event_type != "pause" for event_type, _ in events):
        raise ValueError("dialog.txt neobsahuje žádnou repliku.")
    return events


def trim_leading_silence(wav_path: Path) -> None:
    """Odstraní ticho na začátku první repliky."""
    with wave.open(str(wav_path), "rb") as wav_file:
        params = wav_file.getparams()
        frames = wav_file.readframes(wav_file.getnframes())

    if params.sampwidth not in {1, 2, 3, 4} or params.nchannels < 1:
        return
    frame_width = params.sampwidth * params.nchannels
    max_amplitude = (1 << (params.sampwidth * 8 - 1)) - 1
    threshold = max(1, max_amplitude // 180)
    signed = params.sampwidth != 1
    for offset in range(0, len(frames) - frame_width + 1, frame_width):
        for channel in range(params.nchannels):
            start = offset + channel * params.sampwidth
            sample = int.from_bytes(
                frames[start : start + params.sampwidth], "little", signed=signed
            )
            if params.sampwidth == 1:
                sample -= 128
            if abs(sample) >= threshold:
                with wave.open(str(wav_path), "wb") as wav_file:
                    wav_file.setparams(params)
                    wav_file.writeframes(frames[offset:])
                return
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setparams(params)
        wav_file.writeframes(b"")


def create_silence_wav(seconds: float, params) -> Path:
    """Vytvoří WAV ticha se stejnými parametry jako předchozí replika."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
        wav_path = Path(temporary_file.name)
    frame_count = round(seconds * params.framerate)
    frame_width = params.sampwidth * params.nchannels
    silence_sample = b"\x80" if params.sampwidth == 1 else b"\x00"
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setparams(params)
        wav_file.writeframes(silence_sample * frame_count * frame_width)
    return wav_path


def save_mp3(segment_paths: list[Path], output_path: Path) -> None:
    """Spojí repliky a prodlevy do jednoho MP3; sjednotí i rozdílné formáty hlasů."""
    ffmpeg_path = read_ffmpeg_path(CONFIG_FILE)
    if not ffmpeg_path.is_file():
        raise RuntimeError(f"MP3 nelze vytvořit: nebyl nalezen ffmpeg: {ffmpeg_path}")

    command = [str(ffmpeg_path), "-y", "-loglevel", "error"]
    for segment_path in segment_paths:
        command.extend(("-i", str(segment_path)))
    inputs = "".join(f"[{index}:a]" for index in range(len(segment_paths)))
    command.extend(
        (
            "-filter_complex",
            f"{inputs}concat=n={len(segment_paths)}:v=0:a=1[audio]",
            "-map",
            "[audio]",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_path),
        )
    )
    subprocess.run(command, check=True)


def parse_arguments() -> Path:
    """Vrátí zadaný dialog, nebo výchozí dialog.txt."""
    parser = argparse.ArgumentParser(
        description="Přehrává dialog z textového souboru českými hlasy Piperu."
    )
    parser.add_argument(
        "dialog_file",
        nargs="?",
        type=Path,
        default=DIALOG_FILE,
        help="vstupní dialog (výchozí: dialog.txt)",
    )
    return parser.parse_args().dialog_file


def main() -> int:
    try:
        from piper import PiperVoice
    except ImportError as error:
        print(f"Piper se nepodařilo načíst: {error}")
        return 1

    segment_paths: list[Path] = []
    try:
        dialog_path = parse_arguments()
        dialog = read_dialog(dialog_path)
        voices = {}
        for voice_name in set(SPEAKERS.values()):
            model_path = VOICE_MODELS.get(voice_name)
            if not model_path or not model_path.is_file():
                raise RuntimeError(f"Chybí hlasový model: {model_path}")
            voices[voice_name] = PiperVoice.load(str(model_path))

        first_speech = True
        previous_params = None
        for event_type, value in dialog:
            if event_type == "pause":
                pause_seconds = float(value)
                if MP3 and previous_params is not None:
                    segment_paths.append(create_silence_wav(pause_seconds, previous_params))
                time.sleep(pause_seconds)
                continue

            speaker, text = event_type, str(value)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
                wav_path = Path(temporary_file.name)
            segment_paths.append(wav_path)
            with wave.open(str(wav_path), "wb") as wav_file:
                voices[SPEAKERS[speaker]].synthesize_wav(text, wav_file)
            if first_speech:
                trim_leading_silence(wav_path)
                first_speech = False
            with wave.open(str(wav_path), "rb") as wav_file:
                previous_params = wav_file.getparams()
            print(f"{speaker}: {text}")
            winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)

        if MP3:
            timestamp = datetime.now().strftime("%y%m%d_%H%M")
            output_path = PROJECT_DIR / f"piper_{dialog_path.stem}_{timestamp}.mp3"
            save_mp3(segment_paths, output_path)
            print(f"Vytvořeno: {output_path}")
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Dialog se nepodařilo zpracovat: {error}")
        return 1
    finally:
        for segment_path in segment_paths:
            segment_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

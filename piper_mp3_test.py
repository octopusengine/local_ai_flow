"""Kratky test Piperu: prehraje ukazky a vytvori test.mp3."""

import subprocess
import tempfile
import wave
import winsound
from pathlib import Path

from ollama_piper import read_ffmpeg_path

# ASSETS_DIR / "cs_CZ-jirka-low.onnx",

PROJECT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_DIR / "assets"
FFMPEG_PATH = read_ffmpeg_path(PROJECT_DIR / "lib" / "ollama.json")
VOICES = (
    (
        "cesky",
        ASSETS_DIR / "cs_CZ-honza-medium.onnx",
        "Dobrý den. Toto je krátká zkouška českého hlasu z programu Piper.",
    ),
    (
        "anglicky",
        ASSETS_DIR / "en_US-lessac-low.onnx",
        "Hello. This is a short English voice test using Piper.",
    ),
)


def speak(piper_voice, voice_name: str, model_path: Path, text: str) -> None:
    """Vytvori docasny WAV soubor a synchronne jej prehraje."""
    print(f"Prehravam {voice_name}: {text}")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
        wav_path = Path(temporary_file.name)
    try:
        with wave.open(str(wav_path), "wb") as wav_file:
            piper_voice.load(str(model_path)).synthesize_wav(text, wav_file)
        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
    finally:
        wav_path.unlink(missing_ok=True)


def create_mp3(piper_voice, output_path: Path) -> None:
    """Vytvori jedno testovaci MP3 ze vsech hlasovych ukazek."""
    if not FFMPEG_PATH.is_file():
        raise RuntimeError(f"MP3 nelze vytvorit: nebyl nalezen ffmpeg: {FFMPEG_PATH}")

    segment_paths = []
    try:
        for voice_name, model_path, text in VOICES:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as segment_file:
                segment_path = Path(segment_file.name)
            segment_paths.append(segment_path)
            with wave.open(str(segment_path), "wb") as segment_wav:
                piper_voice.load(str(model_path)).synthesize_wav(text, segment_wav)
            print(f"Prehravam {voice_name}: {text}")
            winsound.PlaySound(str(segment_path), winsound.SND_FILENAME)

        command = [str(FFMPEG_PATH), "-y", "-loglevel", "error"]
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
    finally:
        for segment_path in segment_paths:
            segment_path.unlink(missing_ok=True)


def main() -> int:
    try:
        from piper import PiperVoice
    except ImportError:
        print("Piper neni nainstalovany.")
        print(r".\venv\Scripts\python.exe -m pip install piper-tts")
        return 1

    missing_models = [model_path.name for _, model_path, _ in VOICES if not model_path.exists()]
    if missing_models:
        print("Chybi hlasove modely: " + ", ".join(missing_models))
        return 1

    output_path = PROJECT_DIR / "test.mp3"
    create_mp3(PiperVoice, output_path)
    print(f"Vytvoreno: {output_path}")
    print("Test dokoncen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

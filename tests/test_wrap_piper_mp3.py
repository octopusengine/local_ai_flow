"""Krátký test Piperu: přehraje ukázky a vytvoří ``test.mp3``."""

import json
import subprocess
from pathlib import Path

from lib.wrapp_ffmpeg import get_ffmpeg_path
from lib.wrapp_piper import DialogEvent, PiperWrapper, VoiceSpec


PROJECT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_DIR / "assets"
CONFIG_FILE = PROJECT_DIR / "lib" / "ollama.json"
VOICES = (
    (
        "cesky",
        ASSETS_DIR / "cs_CZ-jirka-medium.onnx",
        0.8,
        " Dobrý den. Toto je krátká zkouška českého hlasu z programu Piper.",
    ),
    (
        "anglicky",
        ASSETS_DIR / "en_US-lessac-low.onnx",
        1.1,
        "Hello. This is a short English voice test using Piper.",
    ),
)


def read_ffmpeg_path() -> Path:
    """Načte cestu k FFmpegu z lokální konfigurace projektu."""
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Nelze načíst konfiguraci FFmpegu: {error}") from error
    configured_path = config.get("ffmpeg")
    if not isinstance(configured_path, str) or not configured_path:
        raise RuntimeError(f"V {CONFIG_FILE} chybí cesta k FFmpegu.")
    return (PROJECT_DIR / configured_path).resolve()


def build_renderer() -> tuple[PiperWrapper, dict[str, str], list[DialogEvent]]:
    """Sestaví testovací dialog a renderer stejně jako ``create_audio.py``."""
    voice_specs = {
        voice_name: VoiceSpec(model_path, length_scale, voice_name)
        for voice_name, model_path, length_scale, _ in VOICES
    }
    dialog = [
        DialogEvent.speech(voice_name, text)
        for voice_name, _, _, text in VOICES
    ]
    speaker_voices = {voice_name: voice_name for voice_name, _, _, _ in VOICES}
    return PiperWrapper(voice_specs, get_ffmpeg_path()), speaker_voices, dialog


def main() -> int:
    missing_models = [
        model_path.name for _, model_path, _, _ in VOICES if not model_path.is_file()
    ]
    if missing_models:
        print("Chybí hlasové modely: " + ", ".join(missing_models))
        return 1

    output_path = PROJECT_DIR / "test.mp3"
    try:
        renderer, speaker_voices, dialog = build_renderer()
        result = renderer.render_to_mp3(
            dialog,
            speaker_voices,
            output_path,
            preview=True,
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Test se nepodařilo dokončit: {error}")
        return 1

    print(f"Vytvořeno: {result.output_path}")
    print("Test dokončen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

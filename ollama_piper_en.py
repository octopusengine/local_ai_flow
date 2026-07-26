"""Spustí Ollamu a čte anglickým hlasem pouze výslednou odpověď modelu."""

import argparse
from pathlib import Path

from lib.wrapp_ffmpeg import get_ffmpeg_path
from lib.wrapp_ollama import ollama_api
from ollama_piper import PiperSpeaker


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_FILE = PROJECT_DIR / "input_en.json"
CONFIG_FILE = PROJECT_DIR / "lib" / "ollama.json"
PIPER_MODEL = PROJECT_DIR / "assets" / "en_US-lessac-low.onnx"


def parse_arguments() -> Path:
    """Vrátí anglický vstupní JSON nebo soubor zadaný uživatelem."""
    parser = argparse.ArgumentParser(
        description="Processes English prompts through Ollama and reads answers aloud in English."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="input JSON file (default: input_en.json)",
    )
    return parser.parse_args().input_file


def main() -> int:
    try:
        speaker = PiperSpeaker(
            PIPER_MODEL, "en_US-lessac-low", "Prompt", ffmpeg_path=get_ffmpeg_path()
        )
    except RuntimeError as error:
        print(error)
        return 1

    app = ollama_api(
        config_path=CONFIG_FILE,
        on_response_text=speaker.add_response_text,
        on_prompt=speaker.add_prompt,
    )
    try:
        return app.run(input_path=parse_arguments())
    finally:
        speaker.close()


if __name__ == "__main__":
    raise SystemExit(main())

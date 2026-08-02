"""Synthesize text with Piper and optionally save it as MP3."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, replace
from pathlib import Path

from lib.wrapp_log import console_log, read_log_enabled
from lib.wrapp_audio import play_audio_file
from lib.wrapp_ffmpeg import run_ffmpeg


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_CONFIG_PATH = PROJECT_ROOT / "project.json"
SPEECH_CONFIG_PATH = PROJECT_ROOT / "cli_speech.json"


@dataclass(frozen=True)
class VoiceConfig:
    """One Piper voice configured for this CLI."""

    name: str
    language: str
    model_path: Path
    length_scale: float


@dataclass(frozen=True)
class SpeechConfig:
    """Settings loaded from cli_speech.json."""

    default_voice: str
    default_texts: dict[str, str]
    sound_enabled: bool
    text_encoding: str
    mp3_codec: str
    mp3_quality: int
    voices: dict[str, VoiceConfig]


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


def required_string(data: dict, name: str, config_path: Path) -> str:
    """Return a required non-empty configuration string."""

    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"The required non-empty value {name!r} is missing from {config_path}.")
    return value


def load_speech_config() -> SpeechConfig:
    """Load and validate voice and MP3 encoding settings."""

    try:
        data = json.loads(SPEECH_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Configuration file does not exist: {SPEECH_CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {SPEECH_CONFIG_PATH}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be an object: {SPEECH_CONFIG_PATH}")

    default_voice = required_string(data, "default_voice", SPEECH_CONFIG_PATH)
    default_texts = {
        code: required_string(data, f"text_{code}", SPEECH_CONFIG_PATH)
        for code in ("cz", "en", "es")
    }
    if not isinstance(data.get("log"), bool):
        raise ValueError(f"The 'log' value in {SPEECH_CONFIG_PATH} must be true or false.")
    sound_enabled = data.get("sound")
    if not isinstance(sound_enabled, bool):
        raise ValueError(f"The 'sound' value in {SPEECH_CONFIG_PATH} must be true or false.")
    text_encoding = required_string(data, "text_encoding", SPEECH_CONFIG_PATH)

    mp3_encoding = data.get("mp3_encoding")
    if not isinstance(mp3_encoding, dict):
        raise ValueError(f"The 'mp3_encoding' value in {SPEECH_CONFIG_PATH} must be an object.")
    mp3_codec = required_string(mp3_encoding, "codec", SPEECH_CONFIG_PATH)
    mp3_quality = mp3_encoding.get("quality")
    if isinstance(mp3_quality, bool) or not isinstance(mp3_quality, int) or not 0 <= mp3_quality <= 9:
        raise ValueError(f"The 'mp3_encoding.quality' value in {SPEECH_CONFIG_PATH} must be an integer from 0 to 9.")

    voices_data = data.get("voices")
    if not isinstance(voices_data, dict):
        raise ValueError(f"The 'voices' value in {SPEECH_CONFIG_PATH} must be an object.")

    voices: dict[str, VoiceConfig] = {}
    for code, voice_data in voices_data.items():
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"Voice keys in {SPEECH_CONFIG_PATH} must be non-empty text.")
        if not isinstance(voice_data, dict):
            raise ValueError(f"Voice configuration {code!r} is missing from {SPEECH_CONFIG_PATH}.")
        language = required_string(voice_data, "language", SPEECH_CONFIG_PATH)
        if language not in default_texts:
            raise ValueError(f"Voice {code!r} must use language cz or en.")
        model_value = Path(required_string(voice_data, "model", SPEECH_CONFIG_PATH))
        model_path = model_value if model_value.is_absolute() else (PROJECT_ROOT / model_value).resolve()
        length_scale = voice_data.get("length_scale")
        if isinstance(length_scale, bool) or not isinstance(length_scale, (int, float)) or length_scale <= 0:
            raise ValueError(f"The 'length_scale' value for voice {code!r} must be positive.")
        voices[code] = VoiceConfig(
            name=required_string(voice_data, "name", SPEECH_CONFIG_PATH),
            language=language,
            model_path=model_path,
            length_scale=float(length_scale),
        )

    if default_voice not in voices:
        raise ValueError(f"The 'default_voice' value in {SPEECH_CONFIG_PATH} must identify a configured voice.")

    return SpeechConfig(
        default_voice=default_voice,
        default_texts=default_texts,
        sound_enabled=sound_enabled,
        text_encoding=text_encoding,
        mp3_codec=mp3_codec,
        mp3_quality=mp3_quality,
        voices=voices,
    )


def positive_speed(value: str) -> float:
    """Parse a positive Piper length-scale value for ``--speed``."""

    try:
        speed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("speed must be a positive number") from error
    if speed <= 0:
        raise argparse.ArgumentTypeError("speed must be greater than zero")
    return speed


def parse_arguments() -> tuple[str | None, str | None, str | None, Path | None, float | None]:
    """Parse optional language, voice, text/file input, and MP3 output."""

    parser = argparse.ArgumentParser(
        description=(
            "Synthesize text in the project directory selected by project.json. "
            "Use --mp3 NAME.mp3 to save an MP3 in that project directory."
        )
    )
    voice_group = parser.add_mutually_exclusive_group()
    voice_group.add_argument(
        "-cz", "--cz", dest="language_option", action="store_const", const="cz", help="use Czech language"
    )
    voice_group.add_argument(
        "-en", "--en", dest="language_option", action="store_const", const="en", help="use English language"
    )
    voice_group.add_argument(
        "-es", "--es", dest="language_option", action="store_const", const="es", help="use Spanish language"
    )
    parser.add_argument("--voice", metavar="NAME", help="use a named voice from cli_speech.json")
    parser.add_argument(
        "--speed",
        metavar="SCALE",
        type=positive_speed,
        help="override the voice speed scale for this run (higher values speak slower)",
    )
    parser.add_argument(
        "--mp3",
        metavar="NAME.mp3",
        type=Path,
        help="save audio as NAME.mp3 in the active project directory",
    )
    parser.add_argument(
        "input_value",
        nargs="?",
        metavar="STRING|FILE.txt",
        help="text to speak, or a .txt file in the active project directory",
    )
    parser.add_argument("-help", action="help", help="show this help message and exit")
    parsed = parser.parse_args()
    return parsed.language_option, parsed.voice, parsed.input_value, parsed.mp3, parsed.speed


def resolve_project_text_file(value: Path, project_directory: Path) -> Path:
    """Return a .txt input that is directly in the project directory root."""

    if value.suffix.lower() != ".txt":
        raise ValueError("The input file must have a .txt extension.")
    input_path = value if value.is_absolute() else project_directory / value
    input_path = input_path.resolve()
    try:
        input_path.relative_to(project_directory)
    except ValueError as error:
        raise ValueError("The input file must be inside the project directory from project.json.") from error
    if input_path.parent != project_directory:
        raise ValueError("The input file must be directly in the project directory root.")
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    return input_path


def resolve_project_mp3_file(value: Path, project_directory: Path) -> Path:
    """Return an MP3 output directly inside the active project directory."""

    if value.suffix.lower() != ".mp3":
        raise ValueError("The --mp3 output file must have an .mp3 extension.")
    output_path = value if value.is_absolute() else project_directory / value
    output_path = output_path.resolve()
    try:
        output_path.relative_to(project_directory)
    except ValueError as error:
        raise ValueError("The --mp3 output file must be inside the active project directory.") from error
    if output_path.parent != project_directory:
        raise ValueError("The --mp3 output file must be directly in the active project directory.")
    return output_path


def select_first_available_voice(config: SpeechConfig, language: str) -> tuple[str, VoiceConfig]:
    """Return the first configured voice for a language whose model exists."""

    language_voices = [
        (code, voice) for code, voice in config.voices.items() if voice.language == language
    ]
    if not language_voices:
        raise ValueError(f"No voices are configured for language {language!r}.")
    for code, voice in language_voices:
        if voice.model_path.is_file():
            return code, voice

    models = ", ".join(str(voice.model_path) for _, voice in language_voices)
    raise FileNotFoundError(f"No configured {language} voice model is available: {models}")


def create_speech(
    text: str, voice: VoiceConfig, config: SpeechConfig, output_path: Path | None
) -> str | None:
    """Synthesize text, optionally play it, and optionally encode it as MP3."""

    if not voice.model_path.is_file():
        raise FileNotFoundError(f"Voice model is missing: {voice.model_path}")
    try:
        from piper import PiperVoice, SynthesisConfig
    except ImportError as error:
        raise RuntimeError("Piper is not installed. Install the packages from requirements.txt.") from error

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
        wav_path = Path(temporary_file.name)
    try:
        piper_voice = PiperVoice.load(str(voice.model_path))
        with wave.open(str(wav_path), "wb") as wav_file:
            piper_voice.synthesize_wav(
                text,
                wav_file,
                syn_config=SynthesisConfig(length_scale=voice.length_scale),
            )
        if output_path is not None:
            run_ffmpeg(
                [
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    wav_path,
                    "-codec:a",
                    config.mp3_codec,
                    "-q:a",
                    str(config.mp3_quality),
                    output_path,
                ]
            )
        if config.sound_enabled:
            try:
                play_audio_file(wav_path)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                # MP3 creation is the primary action. A missing optional player
                # must not discard an already-created output file.
                return f"WARNING: Audio playback skipped: {error}"
        return None
    finally:
        wav_path.unlink(missing_ok=True)


def main() -> int:
    """Create the requested project-root MP3 file."""

    requested_language, requested_voice, requested_input, requested_mp3, requested_speed = parse_arguments()
    try:
        project_directory = load_project_directory()
        log_enabled = read_log_enabled(SPEECH_CONFIG_PATH)
    except (FileNotFoundError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with console_log(project_directory, "cli_speech.py", log_enabled):
        try:
            config = load_speech_config()
            if requested_voice:
                voice_code = requested_voice
                voice = config.voices.get(voice_code)
                if voice is None:
                    available = ", ".join(sorted(config.voices))
                    raise ValueError(f"Unknown voice {voice_code!r}. Available voices: {available}")
            elif requested_language:
                voice_code, voice = select_first_available_voice(config, requested_language)
            else:
                voice_code = config.default_voice
                voice = config.voices[voice_code]
            if requested_speed is not None:
                voice = replace(voice, length_scale=requested_speed)
            input_path = None
            if requested_input is None:
                text_language = requested_language or voice.language
                text = config.default_texts[text_language]
                input_description = f"{SPEECH_CONFIG_PATH} (text_{text_language})"
            elif Path(requested_input).suffix.lower() == ".txt":
                input_path = resolve_project_text_file(Path(requested_input), project_directory)
                text = input_path.read_text(encoding=config.text_encoding).strip()
                input_description = str(input_path)
            else:
                text = requested_input.strip()
                input_description = "command-line text"
            if not text:
                source = input_path if input_path is not None else input_description
                raise ValueError(f"Speech text is empty: {source}")

            output_path = (
                resolve_project_mp3_file(requested_mp3, project_directory)
                if requested_mp3 is not None
                else None
            )
            print(f"Voice: {voice_code} ({voice.name})")
            print(f"Speed scale: {voice.length_scale:g}")
            print(f"Input: {input_description}")
            if not config.sound_enabled and output_path is None:
                print("Audio playback is disabled and --mp3 was not supplied; nothing to do.")
                return 0
            if config.sound_enabled:
                print("Audio playback: enabled")
            if output_path is not None:
                print(f"Creating: {output_path}")
            playback_warning = create_speech(text, voice, config, output_path)
        except (FileNotFoundError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

        if output_path is not None:
            print(f"Done: {output_path}")
        elif playback_warning:
            print("Done: speech was synthesized, but audio playback was skipped.")
        else:
            print("Done: audio was played, but no MP3 was created.")
        if playback_warning:
            print(playback_warning, file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

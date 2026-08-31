"""Transcribe the first MP3 file from the project's ./src directory."""

from lib.wrapp_whisper import main


# Optional per-test overrides. Set to None to use lib/whisper.json.
debug = None
language = "cs"  # Use "auto" for automatic language detection.
model = "base"


if __name__ == "__main__":
    main("mp3", "test_whisper_mp3", debug=debug, language=language, model=model)

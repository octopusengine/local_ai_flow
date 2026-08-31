"""Transcribe the audio track of the first MP4 file from ./src."""

from lib.wrapp_whisper import main


# Optional per-test overrides. Set to None to use lib/ollama.json.
debug = None
language = None
model = None


if __name__ == "__main__":
    main("mp4", "test_whisper_mp4", debug=debug, language=language, model=model)

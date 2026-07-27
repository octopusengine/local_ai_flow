"""Small cross-platform helpers for playing locally generated audio files."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def play_audio_file(audio_path: Path) -> None:
    """Play an audio file synchronously with an operating-system player.

    Piper produces WAV files, which are supported by all players below. The
    player is discovered at runtime, so no extra Python Linux dependency is
    required for the optional audio preview.
    """

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
        return

    if sys.platform == "darwin":
        commands = (("afplay", str(audio_path)),)
    else:
        commands = (
            ("pw-play", str(audio_path)),
            ("paplay", str(audio_path)),
            ("aplay", str(audio_path)),
            ("ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(audio_path)),
            ("mpv", "--no-video", "--really-quiet", str(audio_path)),
        )

    for command in commands:
        executable = shutil.which(command[0])
        if executable:
            try:
                subprocess.run((executable, *command[1:]), check=True)
            except subprocess.CalledProcessError as error:
                raise RuntimeError(
                    f"Audio player {command[0]!r} could not play {audio_path}: {error}"
                ) from error
            return

    if sys.platform == "darwin":
        hint = "Install or make the macOS command 'afplay' available."
    else:
        hint = (
            "Install an audio player such as PipeWire (pw-play), PulseAudio "
            "(paplay), ALSA (aplay), FFmpeg (ffplay), or mpv."
        )
    raise RuntimeError(f"No supported audio player was found. {hint}")

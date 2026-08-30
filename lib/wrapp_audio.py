"""Small cross-platform helpers for playing locally generated audio files."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def play_audio_file(audio_path: Path) -> None:
    """Play an audio file synchronously with an operating-system player.

    WAV and MP3 files work on Windows and Linux. The player is discovered at
    runtime, so no extra Python Linux dependency is required for the optional
    audio preview.
    """

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    if sys.platform == "win32":
        if audio_path.suffix.casefold() == ".wav":
            import winsound

            winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
            return
        _play_windows_media(audio_path)
        return

    if sys.platform == "darwin":
        commands = (("afplay", str(audio_path)),)
    else:
        if audio_path.suffix.casefold() == ".mp3":
            commands = (
                ("ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(audio_path)),
                ("mpv", "--no-video", "--really-quiet", str(audio_path)),
                ("pw-play", str(audio_path)),
                ("paplay", str(audio_path)),
            )
        else:
            commands = (
                ("pw-play", str(audio_path)),
                ("paplay", str(audio_path)),
                ("aplay", str(audio_path)),
                ("ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(audio_path)),
                ("mpv", "--no-video", "--really-quiet", str(audio_path)),
            )

    failed_players: list[str] = []
    for command in commands:
        executable = shutil.which(command[0])
        if executable:
            try:
                subprocess.run((executable, *command[1:]), check=True)
            except subprocess.CalledProcessError as error:
                failed_players.append(f"{command[0]} ({error})")
                continue
            return

    if sys.platform == "darwin":
        hint = "Install or make the macOS command 'afplay' available."
    else:
        hint = (
            "Install an audio player such as PipeWire (pw-play), PulseAudio "
            "(paplay), ALSA (aplay), FFmpeg (ffplay), or mpv."
        )
    if failed_players:
        raise RuntimeError(f"Available audio player(s) could not play {audio_path}: {', '.join(failed_players)}")
    raise RuntimeError(f"No supported audio player was found. {hint}")


def _play_windows_media(audio_path: Path) -> None:
    """Play an MP3 synchronously through Windows' built-in MCI interface."""

    import ctypes

    winmm = ctypes.windll.winmm
    alias = "wrapp_audio_preview"

    def send(command: str) -> None:
        buffer = ctypes.create_unicode_buffer(512)
        error_code = winmm.mciSendStringW(command, buffer, len(buffer), None)
        if error_code:
            error_buffer = ctypes.create_unicode_buffer(512)
            winmm.mciGetErrorStringW(error_code, error_buffer, len(error_buffer))
            raise RuntimeError(f"Windows audio player error: {error_buffer.value or error_code}")

    escaped_path = str(audio_path.resolve()).replace('"', '""')
    send(f'open "{escaped_path}" type mpegvideo alias {alias}')
    try:
        send(f"play {alias} wait")
    finally:
        try:
            send(f"close {alias}")
        except RuntimeError:
            pass

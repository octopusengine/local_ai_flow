"""Třídní rozhraní pro vytváření dialogového zvuku pomocí Piperu."""

from __future__ import annotations

import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class VoiceSpec:
    """Model Piperu a parametry jeho syntézy."""

    model_path: Path
    length_scale: float = 1.0
    display_name: str | None = None


@dataclass(frozen=True)
class DialogEvent:
    """Jedna replika nebo prodleva v dialogu."""

    type: str
    speaker: str | None = None
    text: str | None = None
    seconds: float | None = None
    length_scale: float | None = None

    @classmethod
    def speech(
        cls,
        speaker: str,
        text: str,
        *,
        length_scale: float | None = None,
    ) -> "DialogEvent":
        """Vytvoří repliku s volitelným přepsáním rychlosti pro tuto repliku."""
        if length_scale is not None and length_scale <= 0:
            raise ValueError("Rychlost repliky musí být kladné číslo.")
        return cls(type="speech", speaker=speaker, text=text, length_scale=length_scale)

    @classmethod
    def pause(cls, seconds: float) -> "DialogEvent":
        if seconds < 0:
            raise ValueError("Délka pauzy nesmí být záporná.")
        return cls(type="pause", seconds=seconds)


@dataclass(frozen=True)
class RenderResult:
    """Výsledek jedné syntézy včetně časové osy pro další zpracování."""

    output_path: Path
    duration_seconds: float
    flow_events: list[dict[str, str | float | int]]


class PiperWrapper:
    """Vytváří MP3 dialogu z nezávislých replik Piperu.

    Instance se vytváří s katalogem hlasů. Samotné modely se načtou až při
    prvním použití, takže konstruktor nevyžaduje nainstalovaný Piper.
    """

    def __init__(
        self,
        voices: Mapping[str, VoiceSpec],
        ffmpeg_path: Path,
    ) -> None:
        self.voices = dict(voices)
        self.ffmpeg_path = Path(ffmpeg_path)
        self._loaded_models: dict[Path, object] = {}

    def render_to_mp3(
        self,
        events: Iterable[DialogEvent],
        speaker_voices: Mapping[str, str],
        output_path: Path,
        *,
        preview: bool = False,
        wait_for_pauses: bool = False,
    ) -> RenderResult:
        """Vytvoří MP3 a vrátí přesnou časovou osu replik a pauz.

        Pokud je zapnutý náhled, každá replika se přehraje synchronně. Volba
        ``wait_for_pauses`` zachová reálnou prodlevu mezi přehrávanými replikami.
        """
        self._validate_speakers(speaker_voices)
        segment_paths: list[Path] = []
        flow_events: list[dict[str, str | float | int]] = []
        elapsed_seconds = 0.0
        previous_params = None
        first_speech = True

        try:
            for event in events:
                if event.type == "pause":
                    if event.seconds is None:
                        raise ValueError("Pauze chybí její délka.")
                    pause_seconds = event.seconds
                    if previous_params is not None:
                        segment_paths.append(self._create_silence_wav(pause_seconds, previous_params))
                    flow_events.append(
                        {
                            "type": "pause",
                            "start": self.format_time(elapsed_seconds),
                            "start_seconds": round(elapsed_seconds, 3),
                            "duration_seconds": round(pause_seconds, 3),
                            "end": self.format_time(elapsed_seconds + pause_seconds),
                            "end_seconds": round(elapsed_seconds + pause_seconds, 3),
                        }
                    )
                    elapsed_seconds += pause_seconds
                    if wait_for_pauses:
                        time.sleep(pause_seconds)
                    continue

                if event.type != "speech" or not event.speaker or event.text is None:
                    raise ValueError("Neplatná událost dialogu.")

                voice_key = speaker_voices.get(event.speaker)
                if voice_key is None:
                    raise ValueError(f"Neznámý mluvčí: {event.speaker}")
                voice_spec = self.voices[voice_key]
                length_scale = (
                    event.length_scale
                    if event.length_scale is not None
                    else voice_spec.length_scale
                )
                if length_scale <= 0:
                    raise ValueError("Rychlost repliky musí být kladné číslo.")
                wav_path = self._synthesize_to_wav(voice_key, event.text, length_scale)
                segment_paths.append(wav_path)
                if first_speech:
                    self._trim_leading_silence(wav_path)
                    first_speech = False

                with wave.open(str(wav_path), "rb") as wav_file:
                    previous_params = wav_file.getparams()
                duration_seconds = self._wav_duration_seconds(wav_path)
                flow_events.append(
                    {
                        "type": "speech",
                        "index": len(flow_events),
                        "start": self.format_time(elapsed_seconds),
                        "start_seconds": round(elapsed_seconds, 3),
                        "duration_seconds": round(duration_seconds, 3),
                        "end": self.format_time(elapsed_seconds + duration_seconds),
                        "end_seconds": round(elapsed_seconds + duration_seconds, 3),
                        "speaker": event.speaker,
                        "voice": voice_spec.display_name or voice_key,
                        "length_scale": length_scale,
                        "text": event.text,
                    }
                )
                elapsed_seconds += duration_seconds
                if preview:
                    self._play_wav(wav_path)

            if not segment_paths:
                raise ValueError("Dialog neobsahuje žádnou repliku.")
            self._save_mp3(segment_paths, Path(output_path))
            return RenderResult(Path(output_path), elapsed_seconds, flow_events)
        finally:
            for segment_path in segment_paths:
                segment_path.unlink(missing_ok=True)

    @staticmethod
    def format_time(seconds: float) -> str:
        """Převede sekundy na časový kód ``MM:SS.mmm``."""
        milliseconds_total = round(seconds * 1000)
        minutes, milliseconds = divmod(milliseconds_total, 60_000)
        whole_seconds, milliseconds = divmod(milliseconds, 1_000)
        return f"{minutes:02}:{whole_seconds:02}.{milliseconds:03}"

    def _validate_speakers(self, speaker_voices: Mapping[str, str]) -> None:
        unknown_voices = set(speaker_voices.values()) - self.voices.keys()
        if unknown_voices:
            names = ", ".join(sorted(unknown_voices))
            raise ValueError(f"Mluvčí odkazují na nedefinované hlasy: {names}")

    def _synthesize_to_wav(self, voice_key: str, text: str, length_scale: float) -> Path:
        voice = self._load_model(voice_key)
        syn_config = self._create_synthesis_config(length_scale)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
            wav_path = Path(temporary_file.name)
        try:
            with wave.open(str(wav_path), "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        except Exception:
            wav_path.unlink(missing_ok=True)
            raise
        return wav_path

    def _load_model(self, voice_key: str):
        spec = self.voices[voice_key]
        if not spec.model_path.is_file():
            raise RuntimeError(f"Chybí hlasový model: {spec.model_path}")
        model_path = spec.model_path.resolve()
        if model_path in self._loaded_models:
            return self._loaded_models[model_path]
        try:
            from piper import PiperVoice
        except ImportError as error:
            raise RuntimeError(f"Piper se nepodařilo načíst: {error}") from error

        self._loaded_models[model_path] = PiperVoice.load(str(model_path))
        return self._loaded_models[model_path]

    @staticmethod
    def _create_synthesis_config(length_scale: float):
        try:
            from piper import SynthesisConfig
        except ImportError as error:
            raise RuntimeError(f"Piper se nepodařilo načíst: {error}") from error
        return SynthesisConfig(length_scale=length_scale)

    @staticmethod
    def _trim_leading_silence(wav_path: Path) -> None:
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
                    PiperWrapper._write_wav(wav_path, params, frames[offset:])
                    return
        PiperWrapper._write_wav(wav_path, params, b"")

    @staticmethod
    def _write_wav(wav_path: Path, params, frames: bytes) -> None:
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setparams(params)
            wav_file.writeframes(frames)

    @staticmethod
    def _create_silence_wav(seconds: float, params) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
            wav_path = Path(temporary_file.name)
        frame_count = round(seconds * params.framerate)
        frame_width = params.sampwidth * params.nchannels
        silence_sample = b"\x80" if params.sampwidth == 1 else b"\x00"
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setparams(params)
            wav_file.writeframes(silence_sample * frame_count * frame_width)
        return wav_path

    def _save_mp3(self, segment_paths: list[Path], output_path: Path) -> None:
        if not self.ffmpeg_path.is_file():
            raise RuntimeError(f"MP3 nelze vytvořit: nebyl nalezen ffmpeg: {self.ffmpeg_path}")

        command = [str(self.ffmpeg_path), "-y", "-loglevel", "error"]
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

    @staticmethod
    def _wav_duration_seconds(wav_path: Path) -> float:
        with wave.open(str(wav_path), "rb") as wav_file:
            return wav_file.getnframes() / wav_file.getframerate()

    @staticmethod
    def _play_wav(wav_path: Path) -> None:
        try:
            import winsound
        except ImportError as error:
            raise RuntimeError("Náhled zvuku je podporován pouze ve Windows.") from error
        winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)

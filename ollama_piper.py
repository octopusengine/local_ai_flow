"""Spustí Ollamu a čte českým hlasem pouze výslednou odpověď modelu."""

import argparse
import json
import queue
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
import wave
import winsound
from pathlib import Path

from lib.wrapp_ollama import ollama_api


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_FILE = PROJECT_DIR / "input.json"
CONFIG_FILE = PROJECT_DIR / "lib" / "ollama.json"
DEFAULT_VOICE = "honza"
PIPER_MODELS = {
    "honza": PROJECT_DIR / "assets" / "cs_CZ-honza-medium.onnx",
    "jirka": PROJECT_DIR / "assets" / "cs_CZ-jirka-low.onnx",
}
MAX_SEGMENT_LENGTH = 240
HEADING_MARKER = "\ufff0"
PAUSE_SECONDS = 1.5


class PiperSpeaker:
    """Přehrává dokončené věty v samostatném vlákně."""

    def __init__(
        self,
        model_path: Path,
        voice_name: str,
        prompt_label: str,
        save_mp3: bool = False,
        ffmpeg_path: Path | None = None,
    ) -> None:
        try:
            from piper import PiperVoice
        except ImportError as error:
            raise RuntimeError(
                "Piper není nainstalovaný. Spusťte: "
                r".\venv\Scripts\python.exe -m pip install -r requirements.txt"
            ) from error

        if not model_path.is_file():
            raise RuntimeError(
                f"Chybí hlasový model {model_path.name}. Spusťte: "
                rf".\venv\Scripts\python.exe -m piper.download_voices {voice_name}"
            )

        self.voice = PiperVoice.load(str(model_path))
        self.prompt_label = prompt_label
        self._buffer = ""
        self._in_code_block = False
        self._in_legacy_thinking = False
        self._lock = threading.Lock()
        self._queue: queue.Queue[str | float | None] = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        self._closed = False
        self._save_mp3 = save_mp3
        self._ffmpeg_binary = ffmpeg_path
        self._mp3_path: Path | None = None
        self._audio_params = None
        self._audio_frames = bytearray()

    def set_output_path(self, log_path: Path) -> None:
        """Nastavi cestu k MP3 vedle textoveho zaznamu."""
        if self._save_mp3:
            self._mp3_path = log_path.with_suffix(".mp3")

    def add_response_text(self, text: str) -> None:
        """Přijme část finální odpovědi a zařadí hotové věty ke čtení."""
        with self._lock:
            text = self._remove_legacy_thinking(text)
            self._buffer += self._clean_for_speech(self._remove_code_blocks(text))
            segments = self._extract_segments()

        for segment in segments:
            self._queue.put(segment)

    def add_prompt(self, prompt: str) -> None:
        """Zařadí zadání před odpověď, aby byl poslech srozumitelný."""
        text = f"{self.prompt_label}: {prompt.strip()}"
        if text and text[-1] not in ".!?":
            text += "."
        self.add_response_text(text)

    def _remove_legacy_thinking(self, text: str) -> str:
        """Vynechá případné úvahy vložené do response mezi <think> značkami."""
        spoken_parts = []
        lowered_text = text.lower()
        position = 0
        while position < len(text):
            if self._in_legacy_thinking:
                closing_tag = lowered_text.find("</think>", position)
                if closing_tag == -1:
                    return "".join(spoken_parts)
                position = closing_tag + len("</think>")
                self._in_legacy_thinking = False
                continue

            opening_tag = lowered_text.find("<think>", position)
            if opening_tag == -1:
                spoken_parts.append(text[position:])
                break
            spoken_parts.append(text[position:opening_tag])
            position = opening_tag + len("<think>")
            self._in_legacy_thinking = True

        return "".join(spoken_parts)

    def _remove_code_blocks(self, text: str) -> str:
        """Vynechá bloky kódu ohraničené třemi zpětnými apostrofy."""
        spoken_parts = []
        while text:
            if self._in_code_block:
                closing_fence = text.find("```")
                if closing_fence == -1:
                    return ""
                text = text[closing_fence + 3 :]
                self._in_code_block = False
                continue

            opening_fence = text.find("```")
            if opening_fence == -1:
                spoken_parts.append(text)
                break
            spoken_parts.append(text[:opening_fence])
            text = text[opening_fence + 3 :]
            self._in_code_block = True

        return "".join(spoken_parts)

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Odstraní Markdown a ikony, které by syntetizátor rušivě četl."""
        text = re.sub(
            r"(?m)^\s{0,3}#{1,6}\s*(.+?)(?=\n|$)",
            rf"{HEADING_MARKER}\1{HEADING_MARKER}",
            text,
        )
        text = re.sub(
            r"(?m)^\s*\*\*(.+?)\*\*\s*:?(?=\n|$)",
            rf"{HEADING_MARKER}\1{HEADING_MARKER}",
            text,
        )
        text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"<https?://[^>]+>|https?://\S+", "", text)
        text = re.sub(r"</?[^>]+>", "", text)
        text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
        text = re.sub(r"(?m)^\s*>\s?", "", text)
        text = re.sub(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+", "", text)
        text = re.sub(r"\[[ xX]\]\s*", "", text)
        text = text.replace("\\times", "krát")
        text = re.sub(r"(?<=\d)\s*[×*]\s*(?=\d)", " krát ", text)
        text = text.replace("**", "").replace("__", "").replace("`", "")
        text = text.replace("*", "").replace("_", "").replace("$", "")
        text = text.replace("|", ", ").replace("&", " a ")
        text = "".join(
            character
            for character in text
            if unicodedata.category(character) != "So"
            and character not in {"\ufe0f", "\u200d", "\u20e3"}
        )
        return re.sub(r"\s+", " ", text)

    def _extract_segments(self) -> list[str | float]:
        segments = []
        while self._buffer:
            if self._buffer.startswith(HEADING_MARKER):
                heading_end = self._buffer.find(HEADING_MARKER, 1)
                if heading_end == -1:
                    break
                heading = self._buffer[1:heading_end].strip().rstrip(":")
                self._buffer = self._buffer[heading_end + 1 :].lstrip()
                if heading:
                    segments.extend((heading, PAUSE_SECONDS))
                continue

            line_end = self._buffer.find("\n")
            if line_end != -1:
                first_line = self._buffer[:line_end].strip()
                if 0 < len(first_line) <= 100 and first_line.endswith(":"):
                    self._buffer = self._buffer[line_end + 1 :].lstrip()
                    segments.extend((first_line.rstrip(":"), PAUSE_SECONDS))
                    continue

            match = re.match(r"^(.+?[.!?]+)(?:\s+|$)", self._buffer, re.DOTALL)
            if match:
                segments.append(match.group(1).strip())
                self._buffer = self._buffer[match.end() :].lstrip()
                continue

            if len(self._buffer) < MAX_SEGMENT_LENGTH:
                break

            split_at = self._buffer.rfind(" ", 0, MAX_SEGMENT_LENGTH)
            if split_at <= 0:
                split_at = MAX_SEGMENT_LENGTH
            segments.append(self._buffer[:split_at].strip())
            self._buffer = self._buffer[split_at:].lstrip()

        return [segment for segment in segments if segment]

    def _play(self, text: str) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
            wav_path = Path(temporary_file.name)

        try:
            with wave.open(str(wav_path), "wb") as wav_file:
                self.voice.synthesize_wav(text, wav_file)
            self._append_to_recording(wav_path)
            winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
        finally:
            wav_path.unlink(missing_ok=True)

    def _append_to_recording(self, wav_path: Path) -> None:
        """Prida syntetizovanou rec do budoucího MP3 bez uvodniho ticha."""
        if not self._mp3_path:
            return
        with wave.open(str(wav_path), "rb") as wav_file:
            params = wav_file.getparams()
            frames = wav_file.readframes(wav_file.getnframes())

        if self._audio_params is None:
            self._audio_params = params
            frames = self._trim_leading_silence(frames, params.sampwidth, params.nchannels)
        elif params[:3] != self._audio_params[:3]:
            raise RuntimeError("Zvukove useky Piperu maji odlisne parametry.")
        self._audio_frames.extend(frames)

    @staticmethod
    def _trim_leading_silence(frames: bytes, sample_width: int, channels: int) -> bytes:
        """Odstrani ticho pred prvnim slysitelnym vzorkem (priblizne -45 dB)."""
        if sample_width not in {1, 2, 3, 4} or channels < 1:
            return frames
        frame_width = sample_width * channels
        max_amplitude = (1 << (sample_width * 8 - 1)) - 1
        threshold = max(1, max_amplitude // 180)
        signed = sample_width != 1
        for offset in range(0, len(frames) - frame_width + 1, frame_width):
            for channel in range(channels):
                start = offset + channel * sample_width
                sample = int.from_bytes(frames[start : start + sample_width], "little", signed=signed)
                if sample_width == 1:
                    sample -= 128
                if abs(sample) >= threshold:
                    return frames[offset:]
        return b""

    def _save_recording(self) -> None:
        """Zapise zaznamenanou rec jako MP3 se stejnym zakladem jako log."""
        if not self._mp3_path or not self._audio_params or not self._audio_frames:
            return
        if not self._ffmpeg_binary or not self._ffmpeg_binary.is_file():
            raise RuntimeError(f"MP3 nelze vytvorit: nebyl nalezen ffmpeg: {self._ffmpeg_binary}")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
            recording_path = Path(temporary_file.name)
        try:
            with wave.open(str(recording_path), "wb") as wav_file:
                wav_file.setparams(self._audio_params)
                wav_file.writeframes(self._audio_frames)
            subprocess.run(
                [
                    str(self._ffmpeg_binary),
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(recording_path),
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(self._mp3_path),
                ],
                check=True,
            )
        finally:
            recording_path.unlink(missing_ok=True)

    def _append_silence(self, seconds: float) -> None:
        """Zapise do nahravky stejnou mezeru, ktera je pri prehravani slyset."""
        if not self._mp3_path or not self._audio_params:
            return
        frame_count = round(seconds * self._audio_params.framerate)
        frame_width = self._audio_params.sampwidth * self._audio_params.nchannels
        silence_sample = b"\x80" if self._audio_params.sampwidth == 1 else b"\x00"
        self._audio_frames.extend(silence_sample * (frame_count * frame_width))

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                if isinstance(item, float):
                    self._append_silence(item)
                    time.sleep(item)
                else:
                    self._play(item)
            except Exception as error:
                print(f"Piper nemohl přehrát text: {error}")
            finally:
                self._queue.task_done()

    def close(self) -> None:
        """Dočte zbývající text a počká na dokončení fronty."""
        if self._closed:
            return
        self._closed = True

        with self._lock:
            remaining_text = self._buffer.strip()
            self._buffer = ""
        if remaining_text:
            self._queue.put(remaining_text)

        self._queue.put(None)
        self._queue.join()
        self._worker_thread.join()
        try:
            self._save_recording()
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            print(f"Piper nemohl ulozit MP3: {error}")


def parse_arguments() -> Path:
    """Vrátí vstupní JSON zadaný uživatelem nebo výchozí input.json."""
    parser = argparse.ArgumentParser(
        description="Zpracuje dotazy z JSON souboru přes Ollamu a přečte odpovědi česky."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="vstupní JSON soubor (výchozí: input.json)",
    )
    return parser.parse_args().input_file


def read_ffmpeg_path(config_path: Path) -> Path:
    """Nacte globalni cestu k ffmpeg z ollama.json."""
    try:
        with config_path.open(encoding="utf-8") as config_file:
            config_data = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Nelze nacist config pro ffmpeg: {error}") from error

    ffmpeg_value = config_data.get("ffmpeg")
    if not isinstance(ffmpeg_value, str) or not ffmpeg_value.strip():
        raise RuntimeError('Pole "ffmpeg" v ollama.json musi byt neprazdny text.')
    ffmpeg_path = Path(ffmpeg_value)
    if not ffmpeg_path.is_absolute():
        ffmpeg_path = PROJECT_DIR / ffmpeg_path
    return ffmpeg_path.resolve()


def read_speech_settings(input_path: Path) -> tuple[str, bool]:
    """Načte volitelný hlas ze vstupu; Honza je výchozí."""
    try:
        with input_path.open(encoding="utf-8") as input_file:
            input_data = json.load(input_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Nelze načíst vstupní soubor pro výběr hlasu: {error}") from error

    voice_name = input_data.get("hlas", DEFAULT_VOICE)
    if voice_name not in PIPER_MODELS:
        raise RuntimeError('Pole "hlas" musí být "honza" nebo "jirka".')
    save_mp3 = input_data.get("mp3", False)
    if not isinstance(save_mp3, bool):
        raise RuntimeError('Pole "mp3" musi byt true nebo false.')
    return voice_name, save_mp3


def main() -> int:
    input_path = parse_arguments()
    try:
        voice_name, save_mp3 = read_speech_settings(input_path)
        ffmpeg_path = read_ffmpeg_path(CONFIG_FILE)
        speaker = PiperSpeaker(
            PIPER_MODELS[voice_name], voice_name, "Dotaz", save_mp3, ffmpeg_path
        )
    except RuntimeError as error:
        print(error)
        return 1

    app = ollama_api(
        config_path=CONFIG_FILE,
        on_response_text=speaker.add_response_text,
        on_prompt=speaker.add_prompt,
        on_output_path=speaker.set_output_path,
    )
    try:
        return app.run(input_path=input_path)
    finally:
        speaker.close()


if __name__ == "__main__":
    raise SystemExit(main())

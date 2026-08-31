"""Tests for safe console-to-file log mirroring."""

import io
from pathlib import Path
import tempfile
import unittest

from lib.wrapp_log import _Tee


class TeeTests(unittest.TestCase):
    def test_late_write_after_log_closes_keeps_console_working(self) -> None:
        console = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "log.txt"
            with log_path.open("w", encoding="utf-8") as log_file:
                tee = _Tee(console, log_file)
                tee.write("before close\n")

            tee.write("late atexit reset\n")
            tee.flush()

            self.assertEqual(log_path.read_text(encoding="utf-8"), "before close\n")
        self.assertEqual(console.getvalue(), "before close\nlate atexit reset\n")

    def test_unencodable_console_character_is_replaced_without_losing_utf8_log(self) -> None:
        class Cp1250Console:
            encoding = "cp1250"

            def __init__(self) -> None:
                self.parts: list[str] = []

            def write(self, text: str) -> int:
                text.encode(self.encoding)
                self.parts.append(text)
                return len(text)

            def flush(self) -> None:
                return None

            def isatty(self) -> bool:
                return True

        console = Cp1250Console()
        original_text = "Odpověď obsahuje matematický znak 𝙗.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "log.txt"
            with log_path.open("w", encoding="utf-8") as log_file:
                _Tee(console, log_file).write(original_text)

            self.assertEqual(log_path.read_text(encoding="utf-8"), original_text)
        self.assertEqual("".join(console.parts), "Odpověď obsahuje matematický znak ?.\n")


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

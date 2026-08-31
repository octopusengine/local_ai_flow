"""Tests for command-line text input handling in ``cli_speech.py``."""

from __future__ import annotations

from io import BytesIO, StringIO, TextIOWrapper
import sys
import unittest
from unittest.mock import patch

import cli_speech


class CliSpeechTests(unittest.TestCase):
    def test_standard_input_text_reads_piped_content(self) -> None:
        with patch.object(sys, "stdin", StringIO("  spoken text  \n")):
            self.assertEqual(cli_speech.read_standard_input_text(), "spoken text")

    def test_standard_input_text_decodes_utf8_independently_of_the_console_code_page(self) -> None:
        source = TextIOWrapper(BytesIO("Příliš žluťoučký kůň".encode("utf-8")), encoding="cp1250")
        with patch.object(sys, "stdin", source):
            self.assertEqual(cli_speech.read_standard_input_text(), "Příliš žluťoučký kůň")

    def test_standard_input_text_rejects_interactive_input(self) -> None:
        class InteractiveInput(StringIO):
            def isatty(self) -> bool:
                return True

        with patch.object(sys, "stdin", InteractiveInput("text")):
            with self.assertRaisesRegex(ValueError, "Standard input is interactive"):
                cli_speech.read_standard_input_text()

    def test_dash_is_accepted_as_speech_input(self) -> None:
        with patch.object(sys, "argv", ["cli_speech.py", "--cz", "-"]):
            language, voice, input_value, mp3, speed = cli_speech.parse_arguments()

        self.assertEqual(language, "cz")
        self.assertIsNone(voice)
        self.assertEqual(input_value, "-")
        self.assertIsNone(mp3)
        self.assertIsNone(speed)


if __name__ == "__main__":
    unittest.main()

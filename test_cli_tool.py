"""Tests for batch file selection in ``cli_tool.py``."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cli_tool


class CliToolBatchTests(unittest.TestCase):
    def test_image_batch_selects_only_supported_image_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            source_directory = project_directory / "src"
            source_directory.mkdir()
            for name in ("photo.png", "scan.JPG", "notes.md"):
                (source_directory / name).touch()

            with (
                patch.object(cli_tool, "get_batch_in_subdir", return_value="src"),
                patch.object(cli_tool, "get_batch_out_subdir", return_value="dest"),
            ):
                _, destination_directory, filenames = cli_tool.list_batch_files(
                    project_directory, {".png", ".jpg"}
                )
                destination_created = destination_directory.is_dir()

        self.assertEqual(filenames, ["photo.png", "scan.JPG"])
        self.assertTrue(destination_created)

    def test_text_batch_selects_only_supported_text_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            source_directory = project_directory / "src"
            source_directory.mkdir()
            for name in ("notes.md", "script.PY", "photo.jpg"):
                (source_directory / name).touch()

            with (
                patch.object(cli_tool, "get_batch_in_subdir", return_value="src"),
                patch.object(cli_tool, "get_batch_out_subdir", return_value="dest"),
            ):
                _, _, filenames = cli_tool.list_batch_files(
                    project_directory, cli_tool.BATCH_TEXT_EXTENSIONS
                )

        self.assertEqual(filenames, ["notes.md", "script.PY"])


if __name__ == "__main__":
    unittest.main()

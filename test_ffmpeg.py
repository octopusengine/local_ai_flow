"""Tests for platform-specific FFmpeg resolution."""

from pathlib import Path
import unittest
from unittest.mock import patch

from lib.wrapp_ffmpeg import get_ffmpeg_path


class FFmpegPathTests(unittest.TestCase):
    @patch("lib.wrapp_ffmpeg.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("lib.wrapp_ffmpeg.get_platform_system", return_value="Linux")
    @patch("lib.wrapp_ffmpeg.load_config", side_effect=FileNotFoundError("Windows FFmpeg is absent"))
    def test_linux_falls_back_to_system_ffmpeg(self, _config, _system, _which) -> None:
        self.assertEqual(get_ffmpeg_path(), Path("/usr/bin/ffmpeg"))


if __name__ == "__main__":
    unittest.main()

"""Tests for platform-specific camera backend selection."""

import unittest
from unittest.mock import patch

from cli_camera import open_camera


class FakeCapture:
    def __init__(self, opened: bool) -> None:
        self.opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def release(self) -> None:
        self.released = True


class FakeCv2:
    CAP_DSHOW = 700
    CAP_V4L2 = 200

    def __init__(self, captures: list[FakeCapture]) -> None:
        self.captures = captures
        self.calls: list[tuple[int, int | None]] = []

    def VideoCapture(self, index: int, backend: int | None = None) -> FakeCapture:
        self.calls.append((index, backend))
        return self.captures.pop(0)


class OpenCameraTests(unittest.TestCase):
    @patch("cli_camera.get_platform_system", return_value="Windows")
    def test_windows_uses_directshow(self, _system) -> None:
        capture = FakeCapture(opened=True)
        cv2 = FakeCv2([capture])

        opened_capture, backend_name = open_camera(cv2, 1)

        self.assertIs(opened_capture, capture)
        self.assertEqual(backend_name, "DirectShow")
        self.assertEqual(cv2.calls, [(1, cv2.CAP_DSHOW)])

    @patch("cli_camera.get_platform_system", return_value="Linux")
    def test_linux_falls_back_when_v4l2_cannot_open(self, _system) -> None:
        v4l2_capture = FakeCapture(opened=False)
        fallback_capture = FakeCapture(opened=True)
        cv2 = FakeCv2([v4l2_capture, fallback_capture])

        opened_capture, backend_name = open_camera(cv2, 0)

        self.assertIs(opened_capture, fallback_capture)
        self.assertTrue(v4l2_capture.released)
        self.assertEqual(backend_name, "OpenCV default backend")
        self.assertEqual(cv2.calls, [(0, cv2.CAP_V4L2), (0, None)])


if __name__ == "__main__":
    unittest.main()

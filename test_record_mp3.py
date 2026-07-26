"""Tests for platform-specific microphone settings."""

import unittest

from cli_record_mp3 import SAMPLE_RATE, get_input_device


class FakeSoundDevice:
    def __init__(self, device: dict[str, object]) -> None:
        self.device = device

    def query_devices(self, *, kind: str) -> dict[str, object]:
        if kind != "input":
            raise AssertionError("An input device was expected.")
        return self.device


class InputDeviceTests(unittest.TestCase):
    def test_windows_keeps_project_sample_rate(self) -> None:
        sounddevice = FakeSoundDevice(
            {"name": "Windows microphone", "max_input_channels": 2, "default_samplerate": 48_000}
        )

        device_name, sample_rate = get_input_device(sounddevice, "Windows")

        self.assertEqual(device_name, "Windows microphone")
        self.assertEqual(sample_rate, SAMPLE_RATE)

    def test_linux_uses_default_microphone_sample_rate(self) -> None:
        sounddevice = FakeSoundDevice(
            {"name": "PipeWire microphone", "max_input_channels": 1, "default_samplerate": 48_000}
        )

        device_name, sample_rate = get_input_device(sounddevice, "Linux")

        self.assertEqual(device_name, "PipeWire microphone")
        self.assertEqual(sample_rate, 48_000)


if __name__ == "__main__":
    unittest.main()

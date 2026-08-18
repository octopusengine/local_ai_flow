"""Tests for platform-specific microphone settings."""

import unittest

from cli_record_mp3 import get_input_device, validate_optional_duration


class FakeSoundDevice:
    def __init__(self, device: dict[str, object]) -> None:
        self.device = device

    def query_devices(self, _device: object = None, *, kind: str) -> dict[str, object]:
        if kind != "input":
            raise AssertionError("An input device was expected.")
        return self.device


class InputDeviceTests(unittest.TestCase):
    def test_configured_sample_rate_is_used(self) -> None:
        sounddevice = FakeSoundDevice(
            {"name": "Windows microphone", "max_input_channels": 2, "default_samplerate": 48_000}
        )

        _device, device_name, sample_rate = get_input_device(sounddevice, None, 44_100)

        self.assertEqual(device_name, "Windows microphone")
        self.assertEqual(sample_rate, 44_100)

    def test_null_sample_rate_uses_microphone_default(self) -> None:
        sounddevice = FakeSoundDevice(
            {"name": "PipeWire microphone", "max_input_channels": 1, "default_samplerate": 48_000}
        )

        _device, device_name, sample_rate = get_input_device(sounddevice, None, None)

        self.assertEqual(device_name, "PipeWire microphone")
        self.assertEqual(sample_rate, 48_000)

    def test_optional_duration_accepts_null_and_rejects_zero(self) -> None:
        self.assertIsNone(validate_optional_duration(None, "max_duration_seconds"))
        self.assertEqual(validate_optional_duration(120, "max_duration_seconds"), 120.0)
        with self.assertRaisesRegex(ValueError, "max_duration_seconds"):
            validate_optional_duration(0, "max_duration_seconds")


if __name__ == "__main__":
    unittest.main()

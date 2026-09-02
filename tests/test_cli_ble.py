"""Regression checks for the configured BLE devices.

These tests validate only local configuration; they never access the Bluetooth
adapter or require the ESP32 to be powered on.
"""

from __future__ import annotations

import unittest

import cli_ble


class CliBleConfigurationTests(unittest.TestCase):
    def test_test_led_configuration_is_valid_and_has_required_actions(self) -> None:
        """The ESP regression flow needs these explicitly configured actions."""
        config = cli_ble.load_devices_config()

        device = cli_ble.configured_device(config, "test-led")
        tools = device.get("tools")

        self.assertIsInstance(tools, dict)
        assert isinstance(tools, dict)
        self.assertTrue(
            {
                "led-on",
                "led-off",
                "esp-hi",
                "red-on",
                "red-off",
                "green-on",
                "green-off",
                "status",
                "temperature-read",
            }.issubset(tools)
        )


if __name__ == "__main__":
    unittest.main()

"""Tests for the small shared diagnostic services without real network access."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import wrapp_services


class WrappServicesTests(unittest.TestCase):
    def test_system_datetime_includes_an_offset(self) -> None:
        self.assertRegex(wrapp_services.system_datetime(), r"T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_network_ping_returns_a_compact_success_report(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="first line\nreply line\n", stderr="")
        with patch.object(wrapp_services.subprocess, "run", return_value=completed) as run:
            result = wrapp_services.network_ping()

        self.assertEqual(result["host"], "8.8.8.8")
        self.assertTrue(result["reachable"])
        self.assertEqual(result["summary"], "reply line")
        self.assertEqual(result["output"], "first line\nreply line")
        self.assertEqual(run.call_args.args[0][0], "ping")

    def test_network_ping_handles_a_missing_local_command(self) -> None:
        with patch.object(wrapp_services.subprocess, "run", side_effect=FileNotFoundError):
            result = wrapp_services.network_ping()

        self.assertFalse(result["reachable"])
        self.assertIsNone(result["exit_code"])
        self.assertIn("unavailable", result["summary"])


if __name__ == "__main__":
    unittest.main()

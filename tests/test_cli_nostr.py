"""Tests for local, non-network Nostr CLI diagnostics."""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import cli_nostr


class CliNostrRelayTests(unittest.TestCase):
    def test_relays_action_uses_a_separate_flag_from_the_configured_path(self) -> None:
        args = cli_nostr.build_parser().parse_args(["--relays"])

        self.assertTrue(args.list_relays)
        self.assertFalse(args.config)
        self.assertFalse(args.doctor)

    def test_show_relays_prints_each_configured_relay_without_opening_connections(self) -> None:
        output = StringIO()
        with patch.object(cli_nostr, "configured_relays", return_value=["wss://one.example", "wss://two.example"]):
            with redirect_stdout(output):
                result = cli_nostr.show_relays(SimpleNamespace())

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().splitlines(), ["Configured relays (2):", "1. wss://one.example", "2. wss://two.example"])


if __name__ == "__main__":
    unittest.main()

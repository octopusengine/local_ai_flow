"""Unit tests for the read-only OBT MCP tool implementation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lib import mcp_obt


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class ObtMcpTests(unittest.TestCase):
    def test_private_key_derives_the_documented_api_address(self) -> None:
        self.assertEqual(mcp_obt.obt_get_address(1), "0a4c")
        self.assertEqual(mcp_obt.obt_get_address(123), "cb44")

    def test_private_key_must_be_in_the_obt_scalar_range(self) -> None:
        for private_key in (0, 252, True):
            with self.subTest(private_key=private_key):
                with self.assertRaisesRegex(ValueError, "1 to 251"):
                    mcp_obt.obt_get_address(private_key)  # type: ignore[arg-type]

    def test_private_key_is_loaded_from_dotenv_when_not_provided(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            dotenv_path = Path(temporary_directory) / ".env"
            dotenv_path.write_text("obt_key=111\n", encoding="utf-8")
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(mcp_obt, "DOTENV_PATH", dotenv_path),
            ):
                self.assertEqual(mcp_obt.obt_get_address(), mcp_obt.obt_get_address(111))

    def test_explicit_private_key_has_priority_over_dotenv(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            dotenv_path = Path(temporary_directory) / ".env"
            dotenv_path.write_text("obt_key=111\n", encoding="utf-8")
            with patch.object(mcp_obt, "DOTENV_PATH", dotenv_path):
                self.assertEqual(mcp_obt.obt_get_address(1), "0a4c")

    def test_utxo_tool_uses_the_derived_address_and_returns_balance(self) -> None:
        payload = {
            "status": "ok",
            "address": "0a4c",
            "balance": 8,
            "utxo_count": 2,
            "unspent_outputs": [{"txid": 1234, "value": 3}, {"txid": 1238, "value": 5}],
        }
        with patch.object(mcp_obt, "urlopen", return_value=FakeResponse(payload)) as urlopen_mock:
            result = json.loads(mcp_obt.obt_get_utxo(1))

        self.assertEqual(result, payload)
        request = urlopen_mock.call_args.args[0]
        self.assertIn("route=get_balance/0a4c", request.full_url)
        self.assertIn("api_key=123", request.full_url)
        self.assertEqual(request.get_header("Accept"), "application/json")

    def test_balance_tool_returns_only_the_balance_number(self) -> None:
        payload = {"status": "ok", "balance": 3, "unspent_outputs": [{"txid": 1, "value": 3}]}
        with patch.object(mcp_obt, "urlopen", return_value=FakeResponse(payload)):
            result = mcp_obt.obt_get_balance(1)

        self.assertEqual(result, "3")

    def test_build_transaction_returns_a_locally_verified_signed_payload(self) -> None:
        balance_document = {
            "status": "ok",
            "address": "0a4c",
            "balance": 3,
            "utxo_count": 1,
            "unspent_outputs": [{"txid": 12, "value": 3}],
        }
        with patch.object(mcp_obt, "_balance_document", return_value=balance_document):
            result = json.loads(mcp_obt.obt_build_transaction("83ca", 1, private_key=1))

        self.assertEqual(result["raw"], "0a4c|12|83ca|1")
        self.assertEqual(result["ash24"], "759c23")
        self.assertEqual(result["api_key"], "123")
        self.assertTrue(result["signature_valid"])
        self.assertEqual(
            result["payload"],
            {"from": "0a4c", "to": "83ca", "val1": 3, "val2": 1, "sig_hex": "1d69", "utxo_txid": 12},
        )

    def test_send_transaction_requires_explicit_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "confirm=true"):
            mcp_obt.obt_send_transaction({}, confirm=False)

    def test_send_transaction_rechecks_utxo_before_posting(self) -> None:
        transaction = {"from": "0a4c", "to": "83ca", "val1": 3, "val2": 1, "sig_hex": "1d69", "utxo_txid": 12}
        latest_balance = {"address": "0a4c", "unspent_outputs": [{"txid": 12, "value": 3}]}
        response = {"status": "ok", "txid": 1001, "details": {"sent": 1, "change": 2}}
        with (
            patch.object(mcp_obt, "obt_get_address", return_value="0a4c"),
            patch.object(mcp_obt, "_balance_document", return_value=latest_balance),
            patch.object(mcp_obt, "_post_route", return_value=response) as post_route,
        ):
            result = json.loads(mcp_obt.obt_send_transaction(transaction, confirm=True))

        self.assertEqual(result, response)
        post_route.assert_called_once_with("send_transaction", transaction)


if __name__ == "__main__":
    unittest.main()

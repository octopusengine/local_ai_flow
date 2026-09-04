"""Tests for the deliberately narrow local Nostr MCP capability."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

from lib import nostr_mcp


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = PROJECT_ROOT / "mcp" / "nostr_mcp_server.py"


class NostrMcpTests(unittest.TestCase):
    def test_message_record_is_compact_and_uses_a_local_nickname(self) -> None:
        row = {"uid": 7, "sender_pubkey": "A" * 64, "saved_at": "2026-09-03T12:00:00+00:00", "content": "hello", "handled_at": None, "replied_at": None, "reply_status": ""}
        result = nostr_mcp._message_record(row, {"a" * 64: "friend"})

        self.assertEqual(result["sender"], "friend")
        self.assertEqual(result["local_status"], "pending")
        self.assertNotIn("sender_pubkey", result)
        self.assertNotIn("event_id", result)

    def test_current_message_check_excludes_a_message_older_than_last_outbound(self) -> None:
        row = {"direction": "received", "sender_pubkey": "a" * 64, "rumor_created_at": 100, "saved_at": "2026-09-04T06:00:00+00:00"}
        policy = {"allowed_senders": ["a" * 64]}
        args = types.SimpleNamespace(db=Path("message.db"))
        with patch.object(nostr_mcp.message_db, "latest_sent_message_time", return_value=(101, "2026-09-04T06:01:00+00:00")):
            self.assertFalse(nostr_mcp._current_authorized_row(row, policy, args, {}))

    def test_disabled_policy_refuses_message_work(self) -> None:
        with patch.object(nostr_mcp, "_policy", return_value={"enabled": False}):
            with self.assertRaisesRegex(nostr_mcp.NostrMcpError, "disabled"):
                nostr_mcp._require_enabled(nostr_mcp._policy())

    def test_missing_nostr_dependency_is_not_reported_as_an_invalid_whitelist_key(self) -> None:
        policy = {"allowed_senders": ["npub1example"]}
        with patch.object(nostr_mcp.cli_nostr, "friend_public_key", side_effect=nostr_mcp.cli_nostr.CliNostrError("Install message dependencies")):
            with self.assertRaisesRegex(nostr_mcp.NostrMcpError, "Install message dependencies"):
                nostr_mcp._allowed_sender_keys(policy)

    def test_sync_reports_relay_unavailability_as_an_error(self) -> None:
        policy = {"enabled": True, "allowed_senders": [], "profile": "user1", "max_receive_timeout": 30.0, "max_reply_length": 1000, "max_list_messages": 5}
        args = types.SimpleNamespace(db=Path("message.db"))
        with patch.object(nostr_mcp, "_policy", return_value=policy), patch.object(nostr_mcp, "_args", return_value=args), patch.object(
            nostr_mcp.message_db, "message_event_ids", return_value=set()
        ), patch.object(nostr_mcp.cli_nostr, "receive_friend_messages", return_value=3):
            with self.assertRaisesRegex(nostr_mcp.NostrMcpError, "could not connect"):
                nostr_mcp._receive(15, sync_history=True)

    def test_outbound_message_rejects_a_name_outside_friends_json(self) -> None:
        policy = {"enabled": True, "allowed_senders": [], "profile": "user1", "max_receive_timeout": 30.0, "max_reply_length": 1000, "max_list_messages": 5}
        with patch.object(nostr_mcp, "_policy", return_value=policy), patch.object(
            nostr_mcp, "_args", return_value=types.SimpleNamespace(friends=Path("friends.json"))
        ), patch.object(nostr_mcp.cli_nostr, "load_friends", return_value={"known": "npub1known"}):
            with self.assertRaisesRegex(nostr_mcp.NostrMcpError, "not configured"):
                nostr_mcp.nostr_send_friend("unknown", "hello")

    def test_friend_list_returns_names_without_public_keys(self) -> None:
        policy = {"enabled": True, "allowed_senders": [], "profile": "user1", "max_receive_timeout": 30.0, "max_reply_length": 1000, "max_list_messages": 5}
        with patch.object(nostr_mcp, "_policy", return_value=policy), patch.object(
            nostr_mcp, "_args", return_value=types.SimpleNamespace(friends=Path("friends.json"))
        ), patch.object(nostr_mcp.cli_nostr, "load_friends", return_value={"bob": "npub1secret", "alice": "npub1secret2"}):
            result = nostr_mcp.nostr_list_friends()

        self.assertEqual(result, {"friends": ["alice", "bob"]})

    def test_status_has_no_secret_value(self) -> None:
        with patch.object(
            nostr_mcp,
            "_policy",
            return_value={"enabled": False, "allowed_senders": [], "profile": "user1", "max_receive_timeout": 30.0, "max_reply_length": 1000, "max_list_messages": 5},
        ), patch.object(
            nostr_mcp,
            "_args",
            return_value=types.SimpleNamespace(user_profile=types.SimpleNamespace(identifier="user1", name="User", pub_key="npub-test"), db=Path("message.db"), key_env="NOSTR_KEY", env=Path(".env")),
        ), patch.object(nostr_mcp.message_db, "message_summary", return_value={"total": 0}), patch.object(
            nostr_mcp.cli_nostr, "get_env_value", return_value="private-value-must-not-appear"
        ):
            result = nostr_mcp.nostr_status()

        self.assertTrue(result["private_key_configured"])
        self.assertNotIn("private-value-must-not-appear", repr(result))

    def test_server_registers_only_first_phase_tools(self) -> None:
        registered_tools: list[str] = []

        class FakeMCP:
            def __init__(self, *_arguments: object, **_keywords: object) -> None:
                pass

            def tool(self):
                def register(function):
                    registered_tools.append(function.__name__)
                    return function
                return register

        fake_mcp_module = types.ModuleType("mcp")
        fake_server_module = types.ModuleType("mcp.server")
        fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fake_fastmcp_module.FastMCP = FakeMCP
        original_sys_path = sys.path.copy()
        try:
            with patch.dict(sys.modules, {"mcp": fake_mcp_module, "mcp.server": fake_server_module, "mcp.server.fastmcp": fake_fastmcp_module}):
                runpy.run_path(str(SERVER_PATH), run_name="nostr_mcp_server_test")
        finally:
            sys.path[:] = original_sys_path

        self.assertEqual(registered_tools, ["nostr_status", "nostr_doctor", "nostr_list_relays", "nostr_list_friends", "nostr_list_messages", "nostr_get_message", "nostr_sync", "nostr_mark_handled", "nostr_reply", "nostr_send_friend"])


if __name__ == "__main__":
    unittest.main()

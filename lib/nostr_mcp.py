"""Structured, policy-guarded Nostr operations for a local MCP server.

The module reuses the local CLI's configuration, NIP-17 transport and SQLite
store, but never formats terminal output or returns a private key.  The
``agent`` section of ``cli_nostr.json`` is the explicit authorization boundary
for every operation that reads decrypted messages, receives, sends or writes.
"""

from __future__ import annotations

import argparse
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import cli_nostr
from lib import nostr_runner
from lib import wrapp_nostr_db as message_db


DEFAULT_LIST_LIMIT = 5
MAX_REQUESTED_LIST_LIMIT = 20
_WRITE_LOCK = threading.Lock()


class NostrMcpError(ValueError):
    """A safe error suitable for a local agent or MCP client."""


def _policy() -> dict[str, object]:
    setup = cli_nostr.load_setup(cli_nostr.DEFAULT_SETUP_PATH)
    value = setup.get("agent", {})
    if not isinstance(value, dict):
        raise NostrMcpError("cli_nostr.json field 'agent' must be an object.")
    enabled = value.get("enabled", False)
    allowed = value.get("allowed_senders", [])
    if not isinstance(enabled, bool) or not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise NostrMcpError("Nostr agent policy requires boolean enabled and a list of text allowed_senders.")
    profile = value.get("profile", cli_nostr.DEFAULT_PROFILE_NAME)
    if not isinstance(profile, str) or not profile.strip():
        raise NostrMcpError("Nostr agent policy field 'profile' must be non-empty text.")
    max_receive = value.get("max_receive_timeout", 30)
    max_reply = value.get("max_reply_length", 1000)
    max_list = value.get("max_list_messages", DEFAULT_LIST_LIMIT)
    if isinstance(max_receive, bool) or not isinstance(max_receive, (int, float)) or not 1 <= float(max_receive) <= 300:
        raise NostrMcpError("Nostr agent max_receive_timeout must be a number from 1 through 300.")
    if isinstance(max_reply, bool) or not isinstance(max_reply, int) or not 1 <= max_reply <= 10_000:
        raise NostrMcpError("Nostr agent max_reply_length must be a whole number from 1 through 10000.")
    if isinstance(max_list, bool) or not isinstance(max_list, int) or not 1 <= max_list <= MAX_REQUESTED_LIST_LIMIT:
        raise NostrMcpError(f"Nostr agent max_list_messages must be a whole number from 1 through {MAX_REQUESTED_LIST_LIMIT}.")
    return {"enabled": enabled, "allowed_senders": allowed, "profile": profile.strip(), "max_receive_timeout": float(max_receive), "max_reply_length": max_reply, "max_list_messages": max_list}


def _require_enabled(policy: Mapping[str, object]) -> None:
    if policy["enabled"] is not True:
        raise NostrMcpError("Nostr agent actions are disabled in cli_nostr.json (agent.enabled).")


def _args(policy: Mapping[str, object] | None = None) -> argparse.Namespace:
    active_policy = _policy() if policy is None else policy
    args = argparse.Namespace(
        env=cli_nostr.DEFAULT_ENV_PATH,
        profiles=cli_nostr.DEFAULT_PROFILES_PATH,
        user=str(active_policy["profile"]),
        force=False,
        verbose=0,
    )
    try:
        cli_nostr.apply_setup(args)
    except (OSError, ValueError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    return args


def _allowed_sender_keys(policy: Mapping[str, object]) -> set[str]:
    keys: set[str] = set()
    for value in policy["allowed_senders"]:
        assert isinstance(value, str)
        candidate = value.strip()
        if len(candidate) == 64 and all(character in "0123456789abcdefABCDEF" for character in candidate):
            keys.add(candidate.lower())
            continue
        try:
            keys.add(str(cli_nostr.friend_public_key(candidate).hex()).lower())
        except cli_nostr.CliNostrError as error:
            # Missing local Nostr dependencies are an environment problem, not
            # evidence that the configured whitelist entry is malformed.
            raise NostrMcpError(str(error)) from error
        except ValueError as error:
            raise NostrMcpError("Nostr agent allowed_senders contains an invalid public key.") from error
    return keys


def _authorized_row(row: Any, policy: Mapping[str, object]) -> bool:
    return row["direction"] == "received" and str(row["sender_pubkey"]).lower() in _allowed_sender_keys(policy)


def _is_after_last_outbound(row: Any, args: argparse.Namespace, sent_cache: dict[str, tuple[int | None, str] | None]) -> bool:
    """Return whether an inbound row is newer than our last outbound turn to it."""
    sender_pubkey = str(row["sender_pubkey"])
    if sender_pubkey not in sent_cache:
        try:
            sent_cache[sender_pubkey] = message_db.latest_sent_message_time(args.db, sender_pubkey)
        except (OSError, ValueError, message_db.NostrMessageDatabaseError) as error:
            raise NostrMcpError(str(error)) from error
    latest = sent_cache[sender_pubkey]
    if latest is None:
        return True
    last_rumor_time, last_saved_at = latest
    incoming_rumor_time = row["rumor_created_at"]
    if isinstance(incoming_rumor_time, int) and not isinstance(incoming_rumor_time, bool) and last_rumor_time is not None:
        return incoming_rumor_time > last_rumor_time
    return str(row["saved_at"]) > last_saved_at


def _current_authorized_row(
    row: Any, policy: Mapping[str, object], args: argparse.Namespace, sent_cache: dict[str, tuple[int | None, str] | None]
) -> bool:
    return _authorized_row(row, policy) and _is_after_last_outbound(row, args, sent_cache)


def _validate_limit(limit: object) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_REQUESTED_LIST_LIMIT:
        raise NostrMcpError(f"limit must be a whole number from 1 through {MAX_REQUESTED_LIST_LIMIT}.")
    return limit


def _friend_nicknames(args: argparse.Namespace) -> dict[str, str]:
    """Map configured public contact keys to their local nicknames."""
    try:
        friends = cli_nostr.load_friends(args.friends)
    except (OSError, ValueError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    names: dict[str, str] = {}
    for name, public_key in friends.items():
        try:
            names[str(cli_nostr.friend_public_key(public_key).hex()).lower()] = name
        except (ValueError, cli_nostr.CliNostrError):
            continue
    return names


def _message_record(row: Any, nicknames: Mapping[str, str]) -> dict[str, object]:
    """Return the small conversational record an agent actually needs."""
    sender_key = str(row["sender_pubkey"]).lower()
    if row["replied_at"]:
        local_status = "replied"
    elif row["handled_at"]:
        local_status = "handled"
    else:
        local_status = "pending"
    return {
        "id": int(row["uid"]),
        "sender": nicknames.get(sender_key, f"unknown-{sender_key[:12]}"),
        "saved_at": row["saved_at"],
        "content": row["content"],
        "local_status": local_status,
        "handled_at": row["handled_at"],
        "replied_at": row["replied_at"],
        "reply_status": row["reply_status"],
    }


def nostr_status() -> dict[str, object]:
    """Return safe local configuration and database state, without contacting relays."""
    policy = _policy()
    args = _args(policy)
    try:
        counts = message_db.message_summary(args.db)
        key_configured = bool(cli_nostr.get_env_value(args.key_env, args.env))
    except (OSError, ValueError, message_db.NostrMessageDatabaseError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    return {"profile": {"id": args.user_profile.identifier, "name": args.user_profile.name, "npub": args.user_profile.pub_key}, "agent_enabled": policy["enabled"], "allowed_sender_count": len(policy["allowed_senders"]), "private_key_configured": key_configured, "message_counts": counts}


def nostr_doctor() -> dict[str, object]:
    """Check local Nostr prerequisites without network access or secret output."""
    policy = _policy()
    checks: list[dict[str, object]] = []
    try:
        args = _args(policy)
        checks.append({"name": "profile", "ok": True, "detail": args.user_profile.identifier})
        key_is_set = bool(cli_nostr.get_env_value(args.key_env, args.env))
        checks.append({"name": "private_key", "ok": key_is_set, "detail": "configured" if key_is_set else "not configured"})
        relays = cli_nostr.configured_relays(args)
        checks.append({"name": "relays", "ok": bool(relays), "detail": f"{len(relays)} configured"})
        _allowed_sender_keys(policy)
        checks.append({"name": "allowed_senders", "ok": bool(policy["allowed_senders"]), "detail": f"{len(policy['allowed_senders'])} configured"})
        checks.append({"name": "agent_policy", "ok": policy["enabled"] is True, "detail": "enabled" if policy["enabled"] else "disabled"})
        message_db.create_message_database(args.db)
        checks.append({"name": "message_database", "ok": True, "detail": "available"})
    except (OSError, ValueError, cli_nostr.CliNostrError, message_db.NostrMessageDatabaseError) as error:
        checks.append({"name": "configuration", "ok": False, "detail": str(error)})
    return {"ok": all(item["ok"] is True for item in checks), "checks": checks}


def nostr_list_relays(probe: bool = False) -> dict[str, object]:
    """List configured relays and optionally run a bounded connection probe."""
    if not isinstance(probe, bool):
        raise NostrMcpError("probe must be true or false.")
    args = _args()
    try:
        general = cli_nostr.configured_relays(args)
    except (OSError, ValueError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    result: dict[str, object] = {"general_relays": general, "dm_inbox_relays": list(args.user_profile.dm_relays)}
    if probe:
        result["probe"] = [
            {"relay": relay, "ok": ok, "detail": detail, "duration_ms": round(duration * 1000)}
            for relay in general for ok, detail, duration in [cli_nostr.probe_relay(relay, args.timeout, 0)]
        ]
    return result


def nostr_list_friends() -> dict[str, object]:
    """List only the local contact names eligible for agent-initiated sending."""
    policy = _policy()
    _require_enabled(policy)
    args = _args(policy)
    try:
        friends = cli_nostr.load_friends(args.friends)
    except (OSError, ValueError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    return {"friends": sorted(friends)}


def nostr_list_messages(limit: int | None = None, pending_only: bool = True) -> dict[str, object]:
    """List only authorized inbound local messages, never arbitrary message history."""
    policy = _policy()
    _require_enabled(policy)
    if not isinstance(pending_only, bool):
        raise NostrMcpError("pending_only must be true or false.")
    args = _args(policy)
    try:
        rows = message_db.list_messages(args.db, MAX_REQUESTED_LIST_LIMIT)
    except (OSError, ValueError, message_db.NostrMessageDatabaseError) as error:
        raise NostrMcpError(str(error)) from error
    sent_cache: dict[str, tuple[int | None, str] | None] = {}
    selected = [
        row for row in rows
        if _current_authorized_row(row, policy, args, sent_cache) and (not pending_only or not row["handled_at"])
    ]
    requested_limit = int(policy["max_list_messages"]) if limit is None else _validate_limit(limit)
    effective_limit = min(requested_limit, int(policy["max_list_messages"]))
    nicknames = _friend_nicknames(args)
    return {
        "messages": [_message_record(row, nicknames) for row in selected[:effective_limit]],
        "limit": effective_limit,
        "has_more": len(selected) > effective_limit,
        "newer_than_last_outbound": True,
    }


def nostr_get_message(message_id: int) -> dict[str, object]:
    """Read one authorized inbound message and its local handling state."""
    policy = _policy()
    _require_enabled(policy)
    args = _args(policy)
    try:
        row = message_db.get_message(args.db, message_id)
    except (OSError, ValueError, message_db.NostrMessageDatabaseError) as error:
        raise NostrMcpError(str(error)) from error
    if row is None or not _current_authorized_row(row, policy, args, {}):
        raise NostrMcpError("Message is not available to the Nostr agent.")
    return {"message": _message_record(row, _friend_nicknames(args))}


def _receive(timeout_seconds: object, *, sync_history: bool) -> dict[str, object]:
    policy = _policy()
    _require_enabled(policy)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 1 <= float(timeout_seconds) <= float(policy["max_receive_timeout"]):
        raise NostrMcpError(f"timeout_seconds must be a number from 1 through {policy['max_receive_timeout']:g}.")
    args = _args(policy)
    args.msg_timeout = float(timeout_seconds)
    args.sync_history = sync_history
    args.suppress_wait_output = True
    args.suppress_received_output = True
    try:
        before = message_db.message_event_ids(args.db)
        exit_code = cli_nostr.receive_friend_messages(args)
        if exit_code != 0:
            raise NostrMcpError("Nostr synchronization could not connect to a configured relay.")
        after = message_db.message_event_ids(args.db)
    except (OSError, ValueError, message_db.NostrMessageDatabaseError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    return {"ok": True, "mode": "sync" if sync_history else "receive", "timeout_seconds": float(timeout_seconds), "messages_added": len(after - before)}


def nostr_receive(timeout_seconds: float = 15.0) -> dict[str, object]:
    """Receive and store new NIP-17 messages for a bounded local interval."""
    return _receive(timeout_seconds, sync_history=False)


def nostr_sync(timeout_seconds: float = 30.0) -> dict[str, object]:
    """Fetch the configured NIP-17 history window and stop after relay history ends."""
    return _receive(timeout_seconds, sync_history=True)


def nostr_mark_handled(message_id: int, report: str) -> dict[str, object]:
    """Record a non-empty handling report before any agent reply is permitted."""
    policy = _policy()
    _require_enabled(policy)
    args = _args(policy)
    try:
        row = message_db.get_message(args.db, message_id)
        if row is None or not _current_authorized_row(row, policy, args, {}):
            raise NostrMcpError("Message is not available to the Nostr agent.")
        message_db.mark_message_handled(args.db, message_id, report)
    except (OSError, ValueError, message_db.NostrMessageDatabaseError) as error:
        raise NostrMcpError(str(error)) from error
    return {"ok": True, "message_id": message_id, "status": "handled"}


def nostr_reply(message_id: int, text: str) -> dict[str, object]:
    """Send one recorded reply to an authorized, already handled inbound message."""
    policy = _policy()
    _require_enabled(policy)
    if not isinstance(text, str) or not text.strip():
        raise NostrMcpError("Reply text must be non-empty.")
    if len(text) > int(policy["max_reply_length"]):
        raise NostrMcpError(f"Reply text exceeds the configured {policy['max_reply_length']} character limit.")
    args = _args(policy)
    with _WRITE_LOCK:
        try:
            row = message_db.get_message(args.db, message_id)
            if row is None or not _current_authorized_row(row, policy, args, {}):
                raise NostrMcpError("Message is not available to the Nostr agent.")
            if not row["handled_at"]:
                raise NostrMcpError("Message must first be marked handled.")
            if row["replied_at"]:
                raise NostrMcpError("Message already has a recorded reply.")
            relay_urls = cli_nostr.select_live_relays(args, cli_nostr.message_relay_limit(args))
            if not relay_urls:
                raise NostrMcpError("No configured relay is available.")
            secret = cli_nostr.get_env_value(args.key_env, args.env)
            if not secret:
                raise NostrMcpError("The selected profile private key is not configured.")
            result = nostr_runner.send_nip17_message(cli_nostr.normalize_private_key(secret), str(row["sender_pubkey"]), text, relay_urls, timeout=args.timeout)
            message_db.record_message_reply(args.db, message_id, event_id=result.recipient_event_id, status=result.delivery_status, content=text)
            message_db.record_message(args.db, direction="sent", relay=", ".join(result.confirmed_relays or relay_urls), event_id=result.recipient_event_id, rumor_id=result.rumor_id, rumor_created_at=result.rumor_created_at, sender_pubkey=result.sender_pubkey, recipient_pubkey=result.recipient_pubkey, friend_name=str(row["friend_name"] or ""), content=text, delivery_status=result.delivery_status)
        except (OSError, ValueError, message_db.NostrMessageDatabaseError, cli_nostr.CliNostrError, nostr_runner.NostrRunnerError) as error:
            raise NostrMcpError(str(error)) from error
    return {"ok": bool(result.confirmed_relays), "message_id": message_id, "delivery_status": result.delivery_status, "recipient_event_id": result.recipient_event_id, "confirmed_relays": list(result.confirmed_relays)}


def nostr_send_friend(friend_name: str, text: str) -> dict[str, object]:
    """Send one user-requested NIP-17 message to a named local friend only."""
    policy = _policy()
    _require_enabled(policy)
    if not isinstance(friend_name, str) or not friend_name.strip():
        raise NostrMcpError("friend_name must be a non-empty configured contact name.")
    if not isinstance(text, str) or not text.strip():
        raise NostrMcpError("Message text must be non-empty.")
    if len(text) > int(policy["max_reply_length"]):
        raise NostrMcpError(f"Message text exceeds the configured {policy['max_reply_length']} character limit.")
    args = _args(policy)
    try:
        friends = cli_nostr.load_friends(args.friends)
        recipient = friends.get(friend_name)
        if recipient is None:
            raise NostrMcpError("friend_name is not configured for Nostr agent sending.")
        relay_urls = cli_nostr.select_live_relays(args, cli_nostr.message_relay_limit(args))
        if not relay_urls:
            raise NostrMcpError("No configured relay is available.")
        secret = cli_nostr.get_env_value(args.key_env, args.env)
        if not secret:
            raise NostrMcpError("The selected profile private key is not configured.")
        with _WRITE_LOCK:
            result = nostr_runner.send_nip17_message(cli_nostr.normalize_private_key(secret), recipient, text, relay_urls, timeout=args.timeout)
            message_db.record_message(args.db, direction="sent", relay=", ".join(result.confirmed_relays or relay_urls), event_id=result.recipient_event_id, rumor_id=result.rumor_id, rumor_created_at=result.rumor_created_at, sender_pubkey=result.sender_pubkey, recipient_pubkey=result.recipient_pubkey, friend_name=friend_name, content=text, delivery_status=result.delivery_status)
    except (OSError, ValueError, message_db.NostrMessageDatabaseError, cli_nostr.CliNostrError, nostr_runner.NostrRunnerError) as error:
        raise NostrMcpError(str(error)) from error
    return {"ok": bool(result.confirmed_relays), "friend": friend_name, "delivery_status": result.delivery_status, "confirmed_relays": list(result.confirmed_relays)}


def nostr_inspect_inbox() -> dict[str, object]:
    """Compare raw NIP-17 envelope IDs with the local database without decrypting."""
    args = _args()
    try:
        own_pubkey = str(cli_nostr.friend_public_key(args.user_profile.pub_key).hex())
        known = message_db.message_event_ids(args.db)
        since = max(0, int(__import__("time").time()) - cli_nostr.message_lookback_seconds(args))
        reports = nostr_runner.inspect_nip17_inbox(own_pubkey, args.user_profile.dm_relays, since=since, timeout=args.timeout)
    except (OSError, ValueError, message_db.NostrMessageDatabaseError, cli_nostr.CliNostrError, nostr_runner.NostrRunnerError) as error:
        raise NostrMcpError(str(error)) from error
    return {"relays": [{"relay": item.relay_url, "event_ids": list(item.event_ids), "stored_count": len(set(item.event_ids) & known), "error": item.error} for item in reports]}


def nostr_publish_dm_relays() -> dict[str, object]:
    """Explicitly publish the active profile's NIP-17 kind-10050 relay list."""
    policy = _policy()
    _require_enabled(policy)
    args = _args(policy)
    try:
        from pynostr.event import Event
        from pynostr.key import PrivateKey
        secret = cli_nostr.get_env_value(args.key_env, args.env)
        if not secret:
            raise NostrMcpError("The selected profile private key is not configured.")
        normalized_secret = cli_nostr.normalize_private_key(secret)
        private_key = PrivateKey.from_hex(normalized_secret)
        if private_key.public_key.bech32() != args.pub_key:
            raise NostrMcpError("Selected profile public key does not match its configured private key.")
        relay_urls = cli_nostr.select_live_relays(args, len(cli_nostr.configured_relays(args)))
        if not relay_urls:
            raise NostrMcpError("No configured relay is available.")
        event = Event(pubkey=private_key.public_key.hex(), kind=10050, tags=[["relay", relay] for relay in args.user_profile.dm_relays], content="")
        event.sign(normalized_secret)
        statuses = {relay: cli_nostr.nostr.publish_events(relay, [event], args.timeout, 0) for relay in relay_urls}
    except (ImportError, OSError, ValueError, cli_nostr.CliNostrError) as error:
        raise NostrMcpError(str(error)) from error
    event_id = str(event.id)
    confirmed = [relay for relay, relay_statuses in statuses.items() if relay_statuses.get(event_id, {}).get("ok") is True]
    return {"ok": bool(confirmed), "event_id": event_id, "dm_inbox_relays": list(args.user_profile.dm_relays), "confirmed_relays": confirmed}

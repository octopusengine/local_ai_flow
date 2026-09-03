# Nostr MCP Preparation

## Status

This repository provides a local stdio MCP server at
[`mcp/nostr_mcp_server.py`](../mcp/nostr_mcp_server.py). Its launch descriptor
is [`mcp/nostr_server.json`](../mcp/nostr_server.json). It is deliberately a
small first-phase capability for the Cowork **Nostr agent**, not a general
Nostr client or an automatic responder.

The existing command-line programs remain fully usable on their own:

- `cli_nostr.py` owns local configuration, profiles, NIP-17 actions, relay
  diagnostics, and SQLite message lifecycle operations.
- `nostr_messenger.py` is a human-operated terminal test client built on those
  same operations.
- `lib/nostr_runner.py` contains presentation-free NIP-17 transport helpers.

`lib/nostr_mcp.py` is the structured adapter used by the server. It imports
the local configuration, runner and database layers directly; it never drives
the terminal or parses terminal output.

## Existing boundaries

### `lib.nostr_runner`

`nostr_runner` is the narrowest reusable transport boundary. It does not read
`.env`, print to a terminal, or write SQLite. The caller supplies explicit,
already-normalized input and owns any persistence and presentation.

Current public operations:

| Function | Input | Result | Side effects |
| --- | --- | --- | --- |
| `send_nip17_message()` | Sender private key, recipient key, text, relay URLs, timeout | `NostrSendResult`, including non-secret event IDs and per-relay confirmation status | Publishes NIP-17 gift wraps. |
| `inspect_nip17_inbox()` | Recipient hexadecimal public key, relay URLs, lookback timestamp, timeout | One `NostrInboxRelayResult` per relay with returned gift-wrap IDs or an error | Read-only relay query; no decryption and no DB writes. |

`NostrSendResult` deliberately exposes only safe operational data: recipient
and sender public keys, Nostr event IDs, rumor timestamp, and relay delivery
statuses. It never includes the private key or encrypted plaintext internals.

### `cli_nostr.py`

The CLI layer resolves the selected profile and `.env` key, applies the fixed
setup from `cli_nostr.json`, and records the local message lifecycle. Its
functions can be imported by a trusted local integration, but an MCP server
should avoid invoking its `main()` function or relying on printed output.

Useful current operations include:

| Operation | CLI equivalent | MCP use |
| --- | --- | --- |
| Select and validate a profile | `--doctor`, `--config`, `--key-info` | Safe setup/status information. |
| Test relay connections | `--connect` | Connectivity diagnostics. |
| Publish the DM relay list | `--dm-relays-publish` | Explicitly publish `kind:10050` after profile relay changes. |
| Inspect raw DM envelopes | `--dm-inbox` | Read-only delivery troubleshooting. |
| Receive and store NIP-17 DMs | `--receive` | Inbound polling or a controlled listener. |
| Synchronize stored NIP-17 history | `--sync` | Bounded catch-up operation that stops at relay end-of-stored-events. |
| List or show messages | `--db-msg`, `--db-msg-show` | Agent work queue and conversation context. |
| Mark a message handled | `--msg-done ID REPORT` | Record an action result before responding. |
| Send a recorded reply | `--msg-reply ID TEXT` | Controlled outbound response after handling. |

The SQLite helpers in `lib.wrapp_nostr_db` expose the same persistence layer:
`list_messages`, `get_message`, `message_summary`, `message_event_ids`,
`mark_message_handled`, `record_message_reply`, and `record_message`.

## Local message state

Incoming messages are stored in `data_nostr/nostr_msg.db` before an agent or
person acts on them. The expected state transition is:

```text
received -> handled (handling report) -> replied
```

The handling report is intentionally a separate step. It records what was
performed, when, and with what result even when the agent should not send a
reply. `cli_nostr.py` refuses to send `--msg-reply` unless the incoming message
is already marked handled. A second recorded reply requires the explicit
`--force` option.

Rows are deduplicated by Nostr gift-wrap `event_id`. The receiver also ignores
an ID already seen during a receive pass or already present in the local DB.
Different Nostr events with identical plaintext remain distinct messages.

## First-phase MCP tools

The first version exposes only the message work queue and the diagnostics
needed to operate it. It deliberately does not expose friend management,
general message sending, public event publication, relay configuration, or
raw inbox-envelope inspection.

The Cowork Nostr profile also includes the local `system_datetime` tool, so it
can interpret requests such as “today's messages” against each row's
`saved_at` timestamp.

| Tool | Suggested purpose |
| --- | --- |
| `nostr_status` | Return non-secret selected-profile and DB counts. |
| `nostr_doctor` | Check local profile, key presence, relay list, whitelist, policy and message DB without contacting relays. |
| `nostr_list_relays` | Return configured and DM-inbox relay URLs; optionally probe connections. |
| `nostr_list_messages` | Return recent or pending locally saved inbound messages only when their sender is allowlisted. |
| `nostr_get_message` | Return one allowlisted local message and its handling/reply state. |
| `nostr_sync` | Silently fetch bounded recent NIP-17 history from relays, save new messages to the DB and return only the number added. |
| `nostr_mark_handled` | Save a required non-empty handling report for one received message. |
| `nostr_reply` | Send one reply to a handled message and store the delivery outcome. |

The first agent workflow can remain deliberately conservative:

```text
sync (count only) -> list up to max_list_messages -> inspect message -> perform authorized work
             -> mark handled with report -> reply only when appropriate
```

## Security and authorization

An MCP server would have access to the selected profile's private key through
the local `.env`. Treat it as a trusted local component and never return or log
that value. Public keys, `npub`, event IDs, and relay URLs are safe to return.

Important policy choices must be made by the embedding application, not by the
Nostr transport:

- Which local profiles the MCP server may select.
- Which Nostr senders are authorized to trigger agent work.
- Which message kinds or content are in scope.
- What local actions an agent may perform before marking a message handled.
- Whether it may send a reply automatically, require approval, or only prepare
  a draft.
- Maximum receive duration, reply length, and relay fan-out.

`cli_nostr.json` contains the local MCP policy: `enabled`, `profile`,
`allowed_senders`, `max_receive_timeout`, `max_reply_length`, and
`max_list_messages`. The MCP
adapter enforces it. It accepts whitelist entries as an `npub` or a 64-digit
hex public key and never reveals decrypted content from a non-whitelisted
sender. `max_list_messages` defaults to 5 and caps each tool response even if
the model requests a larger limit, protecting its context window.

Message tools return a compact work record only: local ID, configured sender
nickname, `saved_at`, content and the local `pending` / `handled` / `replied`
state (plus handling/reply timestamps). They omit relay URLs, event IDs, raw
public keys and handling-report text.

## Configuration and storage

The default local files are:

| File | Purpose |
| --- | --- |
| `.env` | Private keys, referenced by profile environment-variable names. Never expose it through MCP. |
| `data_nostr/profiles.json` | Local profile name, public `npub`, private-key variable name, and DM inbox relays. |
| `data_nostr/relays.json` | General relay list used for publishing and receiving. |
| `data_nostr/friends.json` | Named public-key contacts for manual outgoing messages. |
| `cli_nostr.json` | Shared paths, receive timeout, relay fan-out, lookback, and enforced local agent policy. |
| `data_nostr/nostr_msg.db` | Incoming/outgoing message records and lifecycle state. |

The current `msg_lookback` is 14 days. It is the history window requested by
the client, not a promise of relay retention. Reading a Nostr event does not
delete it from a relay; relay retention is controlled by the relay operator.

## Implementation shape

The local server uses a small adapter that:

1. Resolves and validates the one profile selected in `cli_nostr.json`.
2. Calls `cli_nostr.apply_setup()` or equivalent explicit configuration loading.
3. Converts exceptions (`CliNostrError`, `NostrRunnerError`, and DB errors)
   into structured MCP tool errors without leaking secrets.
4. Returns records and results as JSON-compatible objects, not terminal text.
5. Requires a handling report before calling the reply operation.
6. Serializes writes to a message row so two agent turns cannot reply to the
   same inbound message unexpectedly.

There is no background daemon, automatic reply loop, remote service, or tool
for a second reply. Cowork's Nostr profile also disables automatic
continuation and review so the result of a receive, hardware action, or reply
is never silently retried or reinterpreted.

# Nostr chat flow

This is the first-phase chat contract for the Cowork **Nostr agent**. It is a
small, user-directed message bridge, not an autonomous Nostr bot or a
background listener.

## Terms and fresh state

The Nostr SQLite database is a local archive. It is useful for lifecycle state
and history, but it is not evidence that no new message has arrived. A request
such as “read”, “check what they answered”, “latest messages”, or “what came
back?” therefore always starts with:

```text
nostr_sync -> nostr_list_messages
```

`nostr_sync` fetches from configured relays and returns only the number of
saved messages. `nostr_list_messages` returns a compact, policy-capped view
(normally at most five items): nickname, time, content, and local state. The
agent must not inspect a previous listing first or expand the listing merely
because `has_more` is true.

The adapter exposes only inbound messages newer than the agent's latest
outbound reply to that sender. This prevents a later chat cycle from answering
an older pending test message. The same check is enforced before marking or
replying to an individual message.

## Default single-message cycle

The normal flow handles at most one current message, then returns control to
the human:

```text
user asks to check
  -> sync
  -> list compact current queue
  -> choose the newest current message only
  -> do authorized light/hardware work, if any
  -> mark the actual result handled
  -> send one reply when it is appropriate
  -> stop
```

The handling report must describe the actual outcome, including a failure. A
reply is sent only after `nostr_mark_handled` succeeds. A message containing
only a timestamp or bare number is marked as non-actionable and receives no
reply. The agent does not continue into older pending messages from the same
list.

An inbound message can serve as a work prompt only within the user's enabled
light/hardware permissions. Any unavailable or failing action is reported
truthfully; it is never claimed as completed.

## Waiting and asynchronous replies

Waiting happens only when the user explicitly asks for it. One polling cycle
is strictly:

```text
system_wait(1..60 seconds) -> nostr_sync -> nostr_list_messages -> decide
```

The agent must not examine an old list after waiting, and it must not wait a
second time after the final fresh check. If the fresh queue is empty, it says
so concisely and stops. If the user explicitly requests several checks, the
request must name a bounded count; each iteration follows the same sequence.
The tool deliberately limits a single wait to 60 seconds so the session stays
responsive and predictable.

There is no timeout for a human deciding when to write back: they may answer
minutes or hours later. When the human then asks the agent to check again, it
starts a fresh `sync -> list` cycle. It never assumes that cached conversation
state or an old DB view represents the delayed answer.

This phase intentionally has no background polling, automatic wake-up, or
delayed autonomous reply. Longer-lived monitoring would need its own explicit
user-controlled mechanism and policy.

## Sending a new message

For a user-directed new message, the agent may send to an exact name from
`friends.json` through `nostr_send_friend`. If the name is not already known,
it calls `nostr_list_friends`; public keys stay internal. The explicit request
to send is sufficient authorization. Sending a new message is separate from
the inbound handling cycle and does not require `nostr_mark_handled`.

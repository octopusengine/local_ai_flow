# Jam3$-01

Jam3$-01 is a small cross-platform terminal menu for the local Ollama tools.
It runs on Windows and Linux without a shell-specific launcher.

## Run

```text
python james.py
```

Press a highlighted key directly; Enter is not required.

## Main menu

- `p` — Project settings
- `c` — Camera capture
- `v` — Voice recording
- `f` — Best-flow menu
- `m` — MCP-flow menu
- `t` — Chat flow
- `d` — Database menu
- `s` — Setup; choose the default language
- `w` — Reserved cowork section
- `h` — Help
- `q` — Exit from the main menu

## Configuration

`james.json` contains its JSON-format version (`json_version`), the visual menu
width, the default language (`cz`, `en`, or `es`), and the project configuration
filename.
It also contains the main task database path plus the `best_flows` and
`best_mcp_flows` lists. The active project name is read from the `subdir` field
in `project.json`.
`chat_model` sets the model used only by James chat and explicitly overrides
the model defined in `task_base.json`. `chat_context_turns` sets how many
complete user/assistant exchanges are retained in `chat_context.txt`.

The Project menu can display `project.json` and change its `subdir` value.
Every submenu returns with `b` or the Left arrow; `q` remains reserved for the
main menu.

## Chat

`t` sets the active project's selector to `chat`, then starts a James-mediated
chat using `flow_chat_cz.json`, `flow_chat_en.json`, or `flow_chat_es.json`.
James accepts the current message at `>?`, stores it in `chat_input.txt`, and
then starts the flow. Each completed response is written to `chat_reply.txt`.
James appends the user/assistant exchange to the structured bullet list in
`chat_context.txt`, retaining its six newest exchanges for the next round.
The terminal is cleared once when the chat begins, then each round remains
visible. Type `/bye` at the James prompt to return to the main menu, or
`/clr` to discard the current context and start a new conversation. The
selected Setup language chooses the corresponding chat flow and response
language.

Use any catalog command from `assistant/commands/sc.json` at the beginning of
a chat message to shape its answer. For example, `/eli5 explain gravity` adds
the simple-explanation rule, while `/howto bake bread` uses the how-to action.
Aliases work too; the catalog's canonical command name is passed to the chat
flow. A command must be followed by a message.

## Local James commands

These commands are handled by James locally and are never sent to the model:

- `/bye` — return to the main menu.
- `/clr` — discard the current `chat_context.txt` exchanges and begin a new conversation.
- `/mod NEW` — use model `NEW` for the rest of this chat session.

## Database browser

Choose `list` in the Database menu to browse records. Use the Up and Down
arrows to select a row. Enter or `s` shows the complete record. Speak its
answer with `c` for Czech, `a` for English, or `e` for Spanish; each uses that
language's default configured voice. In the record detail, `p` and `n` move to
the previous or next record in the current list. `r` changes its rating, and
`d` deletes it after confirmation.

The Database menu also has `filter`, which offers project, selector, and model.
Choose a value from its numbered, arrow-key navigable list to open the filtered
database browser.

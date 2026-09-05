# James help

## Navigation

Run `python james.py` from the project root with Ollama running.
The main menu reacts to the highlighted key without Enter; `q` quits.
In selection menus, use Up/Down and Enter. `b` or Space returns from
menus and document pages. In text prompts, follow the displayed controls.

## Chat

Type a message and press Enter. These commands help you get started:

- `/hlp` shows Chat controls; `/cmd` shows the localized prompt-command catalog.
- `/bye` returns to the main menu; `/clr` starts a fresh conversation context.
- `/mod MODEL` changes the model; `/lng cz` changes the Chat language for this session.
- `/add FILE` adds a project text file; `/url URL` adds readable web-page text.
- `/ctx` shows context size; `/src` lists attached sources.
- `/voice` records and submits a voice prompt; `/say` reads the latest reply aloud.
- `/cam` captures an image; `/ocr` extracts its text; `/img` adds an image description and enables follow-up vision chat.
- `/rag NAME` selects a knowledge base; `/ask FILTER :: QUESTION` retrieves relevant chunks and asks the question.

Prompt shortcuts can begin a message, for example `/eli5 Explain gravity`.
See `/hlp` for the full command list and file arguments. Project files are
resolved within the active project; `/proj` shows its settings.

## Cowork

Choose an agent profile for general work, coding, hardware, or Nostr.
The profile determines its model and available tools. Follow the displayed
session controls and review tool requests when confirmation is required.
Plans manages project plans; Activity is currently a placeholder.

## Flow

Choose a category and flow with Up/Down, then Enter to run it.
Press `i` in a flow list to inspect the selected flow before running it.
Categories include Test, Single, Code, Batch, Media, MCP, and rag_wiki.
Flows may change the active project or write outputs; check their steps.

## Database and RAG

Database lists saved tasks and answers, opens records by ID, filters them,
and supports ratings and deletion. Use Up/Down and Enter to select an action.
Monthly filters by calendar month; Last week covers today and the previous six days.

RAG manages local knowledge-base profiles and ingestion. After building a
base, select it in Chat with `/rag NAME`; `/rag off` disconnects it.

## MCP

Choose Base, Hardware, or Nostr to inspect services and their configuration.
Optional modules need their own dependencies and settings. If a module is
incomplete, James reports the missing files. Hardware and Nostr actions
follow their configured tool policies.

## Setup and more information

Select the active project and language in Setup. `cz` selects Czech Help
and About; other languages use their English versions. Chat `/lng` only
changes the current Chat session. Ollama shows the shared model settings.

- `james/james.json`: menu settings.
- `james/chat_cmd.json`: Chat defaults, accessible via Setup → james_chat.
- `james/james_flows.json`: flow lists.
- `agent/agents.json`: Cowork profiles, viewable via Setup → agents.
- `lib/wrapp_md.json`: Markdown colours.

About gives a short project overview and library versions.
For more detail, see `james/README.md` and `james/chat_cmd.md`.

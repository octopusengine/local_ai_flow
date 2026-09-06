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
Categories include Test, Models, Single, Code, Batch, Media, MCP, and rag_wiki.
Flows may change the active project or write outputs; check their steps.

## Database and RAG

Database lists saved tasks and answers, opens records by ID, filters them,
and supports ratings and deletion. Use Up/Down and Enter to select an action.
Monthly filters by calendar month; Last week covers today and the previous six days.

RAG manages local knowledge-base profiles and ingestion. After building a
base, select it in Chat with `/rag NAME`; `/rag off` disconnects it.

## Websites in Coding session

Each profile in `agent/agents.json` defaults to `"log": true`. Agent events
are appended immediately to the active session project's `log.txt` as readable
plain text without terminal colours: timestamps, run IDs, steps, models and
parameters, streamed responses, tool arguments/results, durations and errors,
including vision and review. Image bytes are excluded. Set `"log": false`
in a profile and start a new session to disable it. CLI agents use `log` in
`cli_agent.json`.

Development, checks, screenshots and subsequent fixes run headless by default.
The agent opens a visible browser only at the user's explicit request, after
finishing edits and checks. Asking to build or improve a website alone does not
request a visible browser.

Example: “Build a website, check it, save browser.png and leave the finished
site open in my browser.” The coding profile provides `serve_project`,
`browser_test`, `browser_screenshot`, and `browser_open`. Screenshots are
saved in the active project; `inspect_image` can process them with the vision
model. Capture requires installed Edge, Chrome, or Chromium and saves one
viewport (default window 1280 × 720, configurable width/height).

The visible tab remains open when returning to the menu. The local server
ends when James exits. Browser tools accept only the active project's server
URLs returned by `serve_project`, which serves static files and does not start
Vite/Next.js. Existing run-confirmation rules apply; observe policy disallows
opening the browser and saving screenshots.

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

# James

James is a small cross-platform terminal workspace for the local Ollama tools in this repository. It provides a compact menu for chat, flows, databases, RAG, MCP, configuration, and future Cowork work.

![James main menu](img/james1_22.png)

## Run it

From the repository root:

```text
python james.py
```

The active project is selected in `project.json`. General James settings—language, terminal width, and database location—are in [james.json](james.json), which points to the Chat setup through `chat_setup: "chat_cmd.json"`. Chat defaults are in [chat_cmd.json](chat_cmd.json), flow lists are in [james_flows.json](james_flows.json), and Markdown renderer colours are in [james_md.json](james_md.json).

## Current capabilities

- **Chat:** Maintains a project-local conversation context and supports URL, file, camera, OCR, image-description, clipboard, search, export, import, and local-tool actions.
- **Chat commands:** Local commands control the Chat session, its context, files, camera, OCR, RAG, model, and export/import actions. See [chat_cmd.md](chat_cmd.md).
- **Prompt shortcut commands:** Commands from [`assistant/commands/sc.json`](../assistant/commands/sc.json) can be used in chat or flows. One primary command may be chained with compatible modifiers, for example `/tldr /list /md`. `/tldr` and `/wtf` work on the latest saved reply, or on an optional UTF-8 project file, without conversational context; other bare catalog commands apply to the current chat context. See the generated [English catalog](../assistant/commands/README.md) and [Czech catalog](../assistant/commands/sc_cz.md).
- **Flows:** Runs validated local Python CLI workflows from the repository `flows/` directory.
- **Database:** Browses and filters completed local tasks and answers.
- **RAG:** Configures and uses local knowledge bases from project sources.
- **MCP:** Starts the local Model Context Protocol server and lists its available services.
- **Cowork:** Present in the menu as a future agent-coordination workspace; its current concept is documented below.

![Slash-command reference in James](img/james2.png)

## Documents and configuration

| Resource | Purpose |
| --- | --- |
| [james_help.md](james_help.md) | Main-menu help and implementation/library notes. |
| [james_md.py](james_md.py) | Reusable compact Markdown terminal renderer used by James text pages and Chat replies. |
| [james_md.json](james_md.json) | Renderer-specific Markdown colours. |
| [james_flows.json](james_flows.json) | Flow lists grouped by the James Flow menu categories; every entry names an existing `flows/*.txt` file. |
| [chat_cmd.md](chat_cmd.md) | Chat commands: the local command reference for a Chat session. |
| [chat_cmd.json](chat_cmd.json) | Chat defaults for a new session (task, retained context turns, and debug), plus camera/export settings; OCR/image-description task, slash-command, and language settings; localized context-command fallback text; and the internal `flows/chat/` template for `/tldr` and `/wtf`. |
| [../assistant/commands/README.md](../assistant/commands/README.md) | Prompt shortcut command catalog in English, generated from [`sc.json`](../assistant/commands/sc.json). |
| [../assistant/commands/sc_cz.md](../assistant/commands/sc_cz.md) | Prompt shortcut command catalog in Czech, generated from [`sc.json`](../assistant/commands/sc.json). |
| [about.md](about.md) | English About page shown for English and Spanish UI settings. |
| [about_cz.md](about_cz.md) | Czech About page shown for the Czech UI setting. |
| [todo_cowork_cz.md](todo_cowork_cz.md) | Czech proposal and future checklist for the Cowork workspace. |

## Chat commands and context workflow

Chat state lives in the active project directory. The most useful commands are:

```text
/hlp                Show the local Chat-command help.
/clr                Clear the context buffer and start a new conversation.
/task [TASK.json]   List available task JSON files, or change the Chat flow task for this session; the default is task_base.json.
/add FILE          Attach a UTF-8 project file.
/cat FILE          Show a UTF-8 project file without adding it to context; render `.md` as Markdown.
/cam [FILE]        Capture a camera image.
/ocr [FILE]        Extract image text and attach it as [OCR].
/img [FILE]        Describe an image, attach it as [IMAGE], and retain it for follow-up vision questions.
/mod               List local Ollama models and highlight the active Chat model.
/lng [LANGUAGE]    List Chat languages, or switch this Chat session to cz, en, or es.
/rag DATA          Select `rag_wiki/data/wiki_DATA.db` for this Chat session; `/rag off` disconnects it.
/chunk N FILTER[, FILTER ...]
                  Retrieve and attach up to N local chunks, then show them. Comma-separated phrases use AND; `(phrase) and/or (phrase)` and `#(phrase)` let you choose the operator. Enter the chat question on the next line.
/cmd               Show the localized slash-command catalog with James Markdown colors.
/ctx               Show context size and counts.
/src               List attached sources.
/save [FILE]       Export the current context.
/load FILE         Replace the current context.
/debug [on|off]    Show or set chat diagnostics; on preserves live runner output, timings, and executed commands.
/tldr [FILE]       Summarize the latest reply, or an optional project file.
/wtf [FILE]        Explain the latest reply, or an optional project file, in everyday language.
/tldr /list /md    Condense the latest reply as a Markdown list.
```

At the start of a Chat session, the active model is read from the selected task. `/task` switches to that task's model, while a later `/mod MODEL` overrides only the model; the task and model are both passed to the Chat flow.

Use `/hlp` inside Chat for the local Chat-command list and `/cmd` for the localized, rendered Prompt shortcut command catalog. Setup → Slash Commands provides the same catalog outside Chat.
On Linux, Chat explicitly keeps the current session's prompt history through GNU readline, so ↑ and ↓ recall earlier prompts.

## Database

Database is James's browser for the local history of completed tasks and answers. It is useful when you want to find a previous result, inspect its prompt and answer, narrow the history to a subset, or prepare a smaller copy for further work. The active database is configured by `main_db` in [james.json](james.json); the default is `data/tasks.db`.

From the main menu, open **Database** and use the arrows and Enter to choose:

- **List** to browse saved records. Open a record to inspect it and use its available actions, such as rating or deleting the selected record.
- **Filter** to limit the browser by a stored field or date range.
- **Clone** to create a separate database containing selected records or starred records, leaving the active database unchanged.

The underlying command-line tool is [cli_db.py](../cli_db.py); its task schema is [data/tasks_db.md](../data/tasks_db.md). Database browsing changes data only when you explicitly use a record action or create a clone.

## RAG

RAG (retrieval-augmented generation) lets Chat use selected passages from a local document collection as temporary source context. Use it for questions whose answer should be grounded in project documents rather than only in the model's general knowledge.

To create a collection, place source files in `rag_wiki/src/NAME`, then open **RAG** → **ingest** in James. James builds `rag_wiki/data/wiki_NAME.db`, registers the profile in [rag_wiki/databases.json](../rag_wiki/databases.json), and selects it as the active wiki. Re-running ingest lets you update changed sources or overwrite and rebuild the collection.

In Chat, select a prepared wiki and retrieve the passages you need before asking the question:

```text
/rag NAME
/chunk 3 search phrase
Ask the question that should use those chunks.
/rag off
```

`/chunk` attaches only the retrieved chunks to the current Chat context; `/rag off` removes this transient RAG context. **RAG** → **test** is a read-only vector-retrieval demonstration: it asks for a wiki name, preview length, result count, and a search phrase; it then renders the matching short chunks and their vector distances. It accepts the Chat-style `(A) and/or (B)` notation, but uses its phrases as one semantic vector query; exact Boolean filtering remains the FTS5 behavior of Chat `/chunk`. The menu also exposes the vector configuration, registered databases, and source/data directory tree. For the standalone workflow and data design, see [cli_vector.md](../rag_wiki/cli_vector.md), [vector_db_cz.md](../rag_wiki/vector_db_cz.md), and [rag_schema.md](../rag_wiki/rag_schema.md).

## MCP

MCP (Model Context Protocol) is the interface through which an AI client can discover and call tools exposed by a server. In this project, James manages the local MCP server and helps verify which services it currently exposes; it is useful for integrating controlled local capabilities such as date/time, calculation, or configured filesystem and external servers.

Open **MCP** from the main menu and choose:

- **run MCP server** to start the configured local Streamable HTTP server in the background. James reports its endpoint and does nothing if it is already running.
- **list MCP services** to discover the tools currently exposed by that server.
- **show MCP setup** to review the local endpoint configuration before using it.

The local endpoint is defined in [mcp/mcp_config.json](../mcp/mcp_config.json). For direct tests or model tool-calling integration, use [cli_mcp.py](../cli_mcp.py); the protocol and project notes are in [mcp/mcp.md](../mcp/mcp.md) and [mcp/mcp2_cz.md](../mcp/mcp2_cz.md). Review the relevant server configuration before enabling tools that can access files or external services.

## Scope and boundaries

James orchestrates existing local CLIs; it does not replace their task configuration. The general `--context` behaviour of `cli_ollama.py` remains a reference-input mechanism for standalone CLI calls and flows. The convenience behaviour for a bare Prompt shortcut command (`/COMMAND`) is deliberately implemented only in the James Chat layer.

# James

James is a local terminal menu for Ollama workflows.

- `Chat` runs a multi-turn conversation with a local model.
- `Flow` runs prepared automations from the `flows/` directory.
- `Database` browses stored tasks and answers.
- `RAG` builds and queries local knowledge bases from project sources.
- `MCP` runs and configures the local Model Context Protocol server and its services.
- `Setup` configures the project, language, and Ollama settings.

The menu configuration is stored in `james/james.json`.

```text
James
├── cli_ollama.py
├── cli_db.py
├── cli_vector.py
├── cli_mcp.py
├── rag_wiki/
├── mcp/
├── runner.py
└── james.py
    ├── Setup
    ├── Chat
    ├── Flow
    ├── Database
    ├── RAG
    ├── MCP
    └── Help / About
```

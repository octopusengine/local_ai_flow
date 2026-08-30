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

## Related library versions

```text
wrapp_ollama:   0.25.11
wrapp_log:      0.26.06
wrapp_terminal: 0.25.01
wrapp_md:       0.26.07
wrapp_system:   0.26.01
wrapp_db:       0.23.12
wrapp_mcp:      0.26.01
wrapp_img:      0.26.02
wrapp_piper:    0.25.11
wrapp_whisper:  0.26.02
wrapp_ffmpeg:   0.26.01
```

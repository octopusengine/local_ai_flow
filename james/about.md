# James

James is a local terminal menu for Ollama workflows.

- `Chat` runs a multi-turn conversation with a local model.
- `Flow` runs prepared automations from the `flows/` directory.
- `Database` browses stored tasks and answers.
- `Setup` configures the project, language, and Ollama settings.

The menu configuration is stored in `james/james.json`.

```text
James
├── cli_ollama.py
├── cli_db.py
├── cli_vector.py
├── cli_mcp.py
├── runner.py
└── james.py
    ├── Setup
    ├── Chat
    ├── Flow
    ├── Database
    └── Help / About
```

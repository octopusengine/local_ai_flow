# James

James is a local terminal menu for Ollama workflows.

- `Chat` runs a multi-turn conversation with a local model, project context, images, and voice input and output.
- `Cowork` provides local agent sessions for working with files, code, and tools according to the selected profile.
- `Flow` runs prepared automations from the `flows/` directory.
- `Database` browses stored tasks and answers.
- `RAG` builds and queries local knowledge bases from project sources.
- `MCP` provides access to base Model Context Protocol services and optional modules for BLE hardware and Nostr.
- `Setup` configures the project, language, and Ollama settings.

James uses the shared client in `lib/wrapp_ollama.py`: directly in agent sessions, and through `runner.py` and `cli_ollama.py` in regular flows. Speech is handled by `cli_speech.py`, which calls the Piper library; recording transcription uses Whisper.

## Related library versions

```text
wrapp_ollama:   0.25.11
wrapp_log:      0.26.06
wrapp_terminal: 0.25.01
wrapp_md:       0.26.07
wrapp_system:   0.26.01
wrapp_db:       0.23.12
wrapp_mcp_server: 0.26.01
wrapp_vector:   0.1
wrapp_img:      0.26.02
wrapp_whisper:  0.26.02
wrapp_ffmpeg:   0.26.01
```

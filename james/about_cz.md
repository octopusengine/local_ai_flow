# James

James je lokální terminálové menu pro pracovní postupy s Ollamou.

- `Chat` vede vícekolovou konverzaci s lokálním modelem.
- `Flow` spouští připravené automatizace z adresáře `flows/`.
- `Database` prochází uložené úlohy a odpovědi.
- `RAG` vytváří a dotazuje lokální znalostní databáze z projektových zdrojů.
- `MCP` spouští a nastavuje lokální server Model Context Protocol a jeho služby.
- `Setup` nastavuje projekt, jazyk a Ollama volby.

Konfigurace menu je uložena v `james/james.json`.

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

## Verze souvisejících knihoven

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

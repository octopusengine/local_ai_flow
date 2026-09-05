# James

James je lokální terminálové menu pro pracovní postupy s Ollamou.

- `Chat` vede vícekolovou konverzaci s lokálním modelem, projektovým kontextem, obrázky a hlasovým vstupem i výstupem.
- `Cowork` nabízí lokální agentní relace pro práci se soubory, kódem a nástroji podle zvoleného profilu.
- `Flow` spouští připravené automatizace z adresáře `flows/`.
- `Database` prochází uložené úlohy a odpovědi.
- `RAG` vytváří a dotazuje lokální znalostní databáze z projektových zdrojů.
- `MCP` zpřístupňuje základní služby Model Context Protocol a volitelné moduly pro BLE hardware a Nostr.
- `Setup` nastavuje projekt, jazyk a Ollama volby.

James používá sdíleného klienta `lib/wrapp_ollama.py`: v agentních relacích přímo, v běžných flows přes `runner.py` a `cli_ollama.py`. Řeč zajišťuje `cli_speech.py`, který volá knihovnu Piper; přepis nahrávek používá Whisper.

## Verze souvisejících knihoven

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

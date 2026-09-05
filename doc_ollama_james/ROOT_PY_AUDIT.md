# Audit samostatných Python skriptů v kořeni

Stav k 2026-09-05; rozsah: všech 25 souborů `./*.py`.

Označení níže vychází ze statického hledání importů, názvů skriptů,
subprocess volání a příkazů v textových/JSON flows a launcherech.
Zálohy `_bak`, kopie `_nagit`, virtuální prostředí, testy, dokumentace
a historické logy nejsou důkazem současného produkčního volání.
Externí ruční spouštění ani dynamicky sestavené příkazy nelze tímto auditem
vyloučit. „Bez volajícího“ samo o sobě neznamená nefunkční nebo zbytečný.
Skripty nebyly spouštěny, přesouvány ani mazány.

## Kandidáti na archivaci / starší samostatné nástroje

| Soubor | Označení | Důvod a dnešní alternativa |
| --- | --- | --- |
| `cli_ai_project.py` | **LEGACY_ORCHESTRATOR** | Nenalezen volající v aktuálním kódu ani flows. Pevná pipeline record/audio/image → text → volitelný překlad → řeč. Složitelné pomocí `runner.py`, `cli_record_mp3.py`, `cli_whisper_mp3.py`, `cli_ollama.py`, `cli_speech.py`; podrobnosti níže. |
| `ollama_piper_en.py` | **LEGACY_DEMO** | Bez nalezeného volajícího. Ollama + anglické čtení; běžný scénář dnes pokrývá Ollama → speech flow / James. Importuje `PiperSpeaker` z `ollama_piper.py`. |
| `ollama_piper.py` | **LEGACY_DEMO_DEPENDENCY** | James ani flows jej nevolají, ale **importuje ho `ollama_piper_en.py:8`**. Archivovat případně jako dvojici. Vlastní fronta/vlákno pro přehrávání není důkazem přesné shody chování s novým řešením. |
| `piper_compare.py` | **STANDALONE_TEST** | Bez nalezeného volajícího. Porovnání českých hlasů; používá `speak` z `piper_mp3_test.py`. Běžné TTS pokrývá `cli_speech.py --voice`, srovnávací test má vlastní účel. |
| `piper_mp3_test.py` | **STANDALONE_TEST_DEPENDENCY** | **Importuje ho `piper_compare.py:5`**. Není zcela nevolaný; archivovat případně s porovnávacím testem. |
| `piper_standalone_test.py` | **STANDALONE_TEST** | Bez nalezeného volajícího. Minimální přímý test PiperVoice a zápisu WAV. |
| `piper_voice_test.py` | **STANDALONE_TEST** | Bez nalezeného volajícího. Test pěti anglických hlasů; má diagnostický účel mimo James. |
| `piper_dialog.py` | **STANDALONE_SPECIALIZED** | Bez nalezeného volajícího. Vícehlasý český dialog, pauzy a skládání MP3; nelze označit za plně nahrazený jedním voláním `cli_speech.py`. |
| `piper_dialog_en.py` | **STANDALONE_SPECIALIZED** | Bez nalezeného volajícího. Vícehlasý dialog s vlastním parserem a exportem MP3; stejná výhrada jako u české verze. |

## Samostatné vstupní body, které neoznačovat jako mrtvý kód

| Soubor | Označení | Důvod |
| --- | --- | --- |
| `cli_agent.py` | **KEEP_OPTIONAL_CLI** | James tento skript nespouští; oba přímo používají `lib/wrapp_agent.py`. CLI má vlastní `--prompt`, `--policy`, `--show-config` a další přepínače. Jde o kompatibilní CLI adaptér ke sdílenému enginu, nikoli opuštěnou kopii agentní logiky. `cli_agent.json` nadále čte i James (`james.py:104`). |
| `nostr_messenger.py` | **KEEP_OPTIONAL_CLIENT** | Bez nalezeného volajícího, ale dokumentovaný člověkem ovládaný klient pro Nostr DM. Importuje `cli_nostr` (`nostr_messenger.py:18`). James/Nostr agent není automaticky úplnou náhradou tohoto ručního klienta. |
| `james.py` | **KEEP_MAIN_ENTRYPOINT** | Hlavní ručně spouštěné menu; absence volajícího je očekávaná. |

## Aktivní součásti James / flows — ponechat

| Soubor | Konkrétní vazba |
| --- | --- |
| `runner.py` | James sestavuje a spouští příkaz pro flow (`james.py:3879` a násl.). Runner validuje kořenové `.py` a spouští je; nenahrazuje jejich implementaci. |
| `cli_ollama.py` | James (`james.py:4659` a násl.), četné flows; také import v `runner.py:1062`. |
| `cli_tool.py` | James (`james.py:4646` a násl.), např. `flows/flow_tools.txt`. |
| `cli_db.py` | James vytváří CLI příkaz (`james.py:2914` a násl.); také `flows/flow_base.txt`. Přímé DB funkce v James neodstranily všechna CLI volání. |
| `cli_vector.py` | James spouští ingest (`james.py:2639`); také RAG/vector flows. |
| `cli_speech.py` | James (`james.py:4550`), hlasové flows a `cli_ai_project.py`. |
| `cli_camera.py` | James (`james.py:4633`), `flows/flow_cam_ocr.txt` a další kamerové flows. |
| `cli_record_mp3.py` | James (`james.py:4446` a násl.), `flows/flow_record_text.txt`. |
| `cli_whisper_mp3.py` | James (`james.py:4472` a násl.), `flows/flow_record_text.txt`. |
| `cli_mcp.py` | James MCP příkazy (`james.py:3585` a násl.) a MCP flows. |
| `cli_mcp_tx.py` | **Stále volán** z `flows/flow_mcp_tx.txt:7`. Není v aktuálním seznamu `james/james_flows.json`, ale existující flow jej potřebuje. |
| `cli_ble.py` | `flows/flow_test_ble.txt`, kontrola dostupnosti v James a vazba v `lib/hw_mcp.py`. |
| `cli_nostr.py` | Nostr flows, import v `nostr_messenger.py` a vazba v `lib/nostr_mcp.py`. |

## Nahrazuje James / flows `cli_ai_project.py`?

**Ano pro jeho hlavní účel orchestrace; ne jako automatická náhrada 1:1
stejného příkazu a výstupních názvů.** James jej nepoužívá. Už dokumentace
`cli_ai_project.md:279` jej popisuje jako volitelný orchestrátor.

- Nahrávání a přepis: `flows/flow_record_text.txt` volá record → whisper →
  úpravu textu → speech. Je také uveden v `james/james_flows.json`.
- Obrázek/OCR: `flows/flow_cam_ocr.txt` volá kameru a OCR, je v menu James.
  Překlad a speech jsou v tomto konkrétním flow jen zakomentované příklady.
  Vstup z existujícího obrázku vyžaduje příslušné argumenty OCR, nikoli kameru.
- Překlad a čtení: `flows/flow_voice_free.txt` ukazuje překlad `c2a` a české
  i anglické TTS.
- Přepis existujícího MP3 a libovolnou kombinaci volitelných etap lze složit
  ze stejných CLI, která volá `cli_ai_project.py:83–143`.

Při migraci zachovat požadovaný projekt, názvy výstupů, směr překladu a export
MP3. Ukázkové flows někdy mění aktivní projekt a nejsou přesnou kopií původní
pipeline. `cli_ai_project.py` navíc mapuje uživatelské `c2e` na CLI `c2a`.

První kandidát k úklidu je tedy `cli_ai_project.py`. Dalších osm Piper
skriptů tvoří oddělené demo/test/specializované nástroje; u dialogů ponechat
jejich unikátní funkce a u dvojic respektovat importy. Zbývajících 16 souborů
má aktivní vazbu nebo smysluplnou roli samostatného vstupního bodu.

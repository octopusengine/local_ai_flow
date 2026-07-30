# Naše MCP integrace

Tento dokument popisuje konkrétní MCP řešení v tomto projektu. Je určený jako praktická mapa: co je protokol, které soubory hrají jakou roli, co přesně dělá `cli_mcp.py` a kdy se do běhu zapojuje Ollama s modelem Qwen.

## MCP stručně

**MCP (Model Context Protocol)** je komunikační protokol pro zpřístupnění nástrojů aplikacím s jazykovým modelem. Sám MCP není model, nástroj ani server. Určuje, jak spolu klient a server komunikují například při:

- zjištění dostupných nástrojů (`list_tools`),
- získání popisu parametrů nástroje,
- volání nástroje a předání jeho výsledku.

Model není povinnou součástí MCP. MCP klient může nástroj zavolat přímo, bez jakéhokoli LLM. Teprve při tool-callingu se model rozhoduje, který z nabídnutých nástrojů chce použít.

## Co máme napsáno

| Část | Soubor | Role |
| --- | --- | --- |
| MCP server | [`mcp/wrapp_mcp.py`](wrapp_mcp.py) | Lokální server, který registruje a publikuje naše tooly přes HTTP na `/mcp`. |
| Tool | [`mcp/rot13.py`](rot13.py) | Čistá funkce `rot13(word)`. |
| Tool | [`mcp/calculate.py`](calculate.py) | Čistá funkce `calculate(a, b, operation)`. |
| Tool | [`mcp/current_datetime.py`](current_datetime.py) | Čistá funkce `datetime()`. |
| MCP klient / runner | [`cli_mcp.py`](cli_mcp.py) | Spustí server, připojí se k němu, najde a volá tooly. S `--ollama` je také prostředníkem mezi MCP a Ollamou. |
| Konfigurace Memory | [`mcp/memory_server.json`](memory_server.json) | Lokální stdio konfigurace pro referenční MCP Memory server. |
| Konfigurace Filesystem | [`mcp/filesystem_server.json`](filesystem_server.json) | Lokální stdio konfigurace pro Filesystem server omezený na `data_mcp`. |
| Testovací data | [`data_mcp/`](../data_mcp/) | Vyhrazený prázdný adresář pro Filesystem MCP testy. |
| Konfigurace serveru | [`mcp/mcp_config.json`](mcp_config.json) | Host, port, cesta `/mcp` a výchozí název modelu. |
| Konfigurace projektu | [`project.json`](project.json) | Aktivní projektový adresář, logování, selektor a přepínač ukládání do DB. |

Samotné soubory `rot13.py`, `calculate.py` a `current_datetime.py` nejsou MCP servery. Jsou to běžné Python funkce. MCP server z nich vytvoří veřejně volatelné MCP tooly až registrací v `wrapp_mcp.py`:

```python
mcp.tool()(rot13)
mcp.tool()(datetime)
mcp.tool()(calculate)
```

## Role Python balíčku `mcp`

Instalovaný Python balíček `mcp` je SDK pro MCP; není to automaticky spuštěný server.

- V serveru používáme `mcp.server.fastmcp.FastMCP`.
- V klientovi používáme `mcp.ClientSession` a `streamable_http_client`.

Jedna knihovna tedy pomáhá implementovat obě strany protokolu. Vlastní server je až proces spuštěný z `mcp/wrapp_mcp.py`.

## Architektura běžného testu

```mermaid
flowchart LR
    CLI["cli_mcp.py\nMCP klient / runner"] -->|"spustí jako podproces"| SERVER["mcp/wrapp_mcp.py\nMCP server"]
    CLI -->|"MCP Streamable HTTP\nlist_tools + call_tool"| SERVER
    SERVER --> TOOLS["rot13 · datetime · calculate"]
```

`cli_mcp.py` nejdřív spustí náš server, počká na port, naváže MCP relaci, zavolá `list_tools()` a podle `--function` vybere nástroj. Potom nástroj volá přímo přes MCP. Po skončení server vždy ukončí.

Například pro kalkulačku proběhne zjednodušeně toto:

```text
cli_mcp.py
  → spustí wrapp_mcp.py
  → MCP initialize
  → MCP list_tools
  → MCP call_tool("calculate", {"a": 3, "b": 7, "operation": "*"})
  ← "21.0"
```

V tomto režimu není potřeba Ollama ani jazykový model.

## Role Qwen a Ollamy

`qwen3.5:latest` je jazykový model uložený a provozovaný v Ollamě. Není to MCP server, MCP klient ani Python modul `mcp`.

Model nepotřebuje mít nainstalovaný Python balíček `mcp`. Naše CLI mu při režimu `--ollama` pošle JSON schema toolu. Model pak vrátí strukturovanou žádost o jeho volání. `cli_mcp.py` tuto žádost přečte, provede skutečné volání přes MCP server a výsledek doručí modelu zpět.

```mermaid
sequenceDiagram
    participant C as cli_mcp.py
    participant S as MCP server
    participant O as Ollama / Qwen

    C->>S: list_tools + přímý call_tool
    S-->>C: ověřený výsledek toolu
    C->>O: schema toolu a instrukce
    O-->>C: požadavek na tool call
    C->>S: call_tool s argumenty od modelu
    S-->>C: výsledek toolu
    C->>O: výsledek jako zpráva role tool
    O-->>C: finální text modelu
```

Ne každý model v Ollamě umí tool-calling spolehlivě. Pro režim `--ollama` je potřeba model, který vrací `tool_calls` ve formátu API `/api/chat`. Přímý MCP test bez `--ollama` na schopnostech modelu nezávisí.

## Příkazy a jejich rozdíl

### Vypsání toolů

```powershell
python3 cli_mcp.py --list
python3 cli_mcp.py -l --out tools.txt
```

Spustí MCP server, vypíše jeho nástroje a jejich popisy a skončí. Ollama se nevolá a záznam do DB se nevytváří. S `--out` se seznam uloží do aktivního projektového adresáře.

### Rychlý přímý MCP test — výchozí režim

```powershell
python3 cli_mcp.py --function calculate --a 3 --b 7 --operation "*"
python3 cli_mcp.py --function rot13 --word apple --out mcp_out.txt
python3 cli_mcp.py --function datetime
```

To je výchozí a rychlý režim. CLI zavolá nástroj přímo přes MCP a po úspěchu:

- vytiskne diagnostický řádek s výsledkem,
- vytiskne samotný výsledek na samostatný zelený řádek,
- uloží samotný výsledek do `--out FILE`, je-li zadané,
- při `"db": true` v `project.json` uloží samotný výsledek do `data/tasks.db` do sloupce `answer`.

Příklad očekávaného výsledku:

```text
[čas] MCP calculation test result: 3.0 * 7.0 = 21.0
21.0
[čas] Task recorded in data/tasks.db: 123
[čas] MCP tool test: PASSED
```

Barevné zvýraznění závisí na tom, zda terminál podporuje ANSI barvy. Text v logu a souboru zůstává čistý, bez řídicích sekvencí.

V tomto režimu parametr `--model` Ollamu nevolá. Hodnota modelu se jen používá jako metadata případného DB záznamu; pro samotný výsledek `calculate` nebo `rot13` není podstatná.

### Úplné ověření přes Ollamu — volitelné

```powershell
python3 cli_mcp.py --ollama --model qwen3.5:latest --function calculate --a 3 --b 7 --operation "*"
python3 cli_mcp.py --ollama --model qwen3.5:latest --function rot13 --word apple
```

Přepínač `--ollama` je výchozně vypnutý. Teprve s ním CLI po přímém MCP testu ještě ověřuje, zda model:

1. dostal schema zvoleného toolu,
2. skutečně požádal o jeho zavolání,
3. předal použitelné argumenty,
4. dostal výsledek toolu zpět,
5. dokázal vrátit finální textovou odpověď.

Tento režim může trvat podstatně déle, protože čeká na jednu nebo dvě odpovědi modelu přes Ollama API. `--out` se přesto zapíše hned po přímém MCP výsledku, tedy před případným dlouhým čekáním na finální odpověď modelu.

`--ollama` nelze kombinovat s `--list`.

### Obecný stdio MCP server

Přepínač `--server-config FILE` připojí `cli_mcp.py` k jinému lokálnímu stdio MCP serveru. Konfigurační soubor musí být uvnitř tohoto projektu a v první verzi podporuje pouze transport `stdio`:

```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-memory"],
  "cwd": "."
}
```

Konfigurace používají pouze `npx` a relativní pracovní adresář, proto fungují ve Windows i Linuxu. Python MCP SDK na Windows vyřeší spustitelný příkaz `npx` bez nutnosti zapisovat do JSONu `cmd /c`. Je potřeba mít nainstalovaný Node.js a `npx`; při prvním běhu `npx` stáhne balíček daného serveru.

`--args JSON` předá zvolenému toolu libovolný JSON objekt. Je určený pro obecné servery, jejichž parametry neodpovídají našim zkratkám `--word`, `--a`, `--b` a `--operation`.

#### Memory

```powershell
python3 cli_mcp.py --server-config mcp/memory_server.json --list
```

Nejdřív je vhodné vypsat aktuální tooly. Pak lze volat jejich jméno a přesné argumenty ze schema, například:

```powershell
python3 cli_mcp.py --server-config mcp/memory_server.json --function create_entities --args '{"entities":[{"name":"test","entityType":"note","observations":["hello MCP"]}]}'
```

#### Filesystem

```powershell
python3 cli_mcp.py --server-config mcp/filesystem_server.json --list
python3 cli_mcp.py --server-config mcp/filesystem_server.json --function list_allowed_directories
```

Filesystém server dostává jako jediný povolený adresář `data_mcp` v kořeni projektu. Je to vyhrazený testovací prostor — server v něm může podle zvoleného toolu soubory číst, vytvářet, přepisovat, přesouvat i mazat. Nedávejme mu cestu k celému projektu ani k domovskému adresáři.

Kompletní připravená ukázka je [`tasks_flows/flow_mcp_filesystem.txt`](../tasks_flows/flow_mcp_filesystem.txt). Flow vytvoří `data_mcp/mcp_flow_example.txt` přes `write_file`, načte jej přes samostatné `read_text_file` volání a uloží přečtený obsah do `filesystem_mcp_read.txt` v aktivním projektovém adresáři. Takový výstupní soubor je jednoduché, průhledné rozhraní pro další CLI modul.

`--server-config` se zatím nedá kombinovat s `--ollama`: tento krok ověřuje obecné přímé MCP volání. Tool-calling přes Ollamu pro cizí servery bude samostatné rozšíření.

## Výstupní soubor a databáze

Přepínač `--out FILE` vyžaduje název souboru:

```powershell
python3 cli_mcp.py --function rot13 --word apple --out mcp_out.txt
```

Samotné `--out` bez hodnoty je chyba parseru. Soubor musí být přímo v aktivním projektovém adresáři určeném položkou `subdir` v `project.json`; cesty mimo něj ani další vnořená podsložka nejsou povolené. Výstup používá UTF-8 s BOM, stejně jako `cli_ollama.py`.

Při zapnutém `"db": true` se po úspěšném testu vytvoří záznam v `data/tasks.db`. Důležité hodnoty jsou:

| Sloupec | Hodnota |
| --- | --- |
| `project` | Aktivní `subdir` z `project.json`. |
| `selector` | `selector` z `project.json`. |
| `task` | Například `mcp/calculate`. |
| `model` | Hodnota z `--model` nebo výchozí z `mcp_config.json`. |
| `parameters` | Endpoint, jméno toolu, argumenty a případně název výstupního souboru. |
| `answer` | Přímý a ověřený výsledek MCP toolu, například `21.0` nebo `NCCYR`. |

## Konfigurace

[`mcp/mcp_config.json`](mcp_config.json) definuje lokální endpoint a výchozí model:

```json
{
  "host": "127.0.0.1",
  "port": 8000,
  "path": "/mcp",
  "transport": "streamable-http",
  "ollama_model": "qwen3.5:latest"
}
```

[`project.json`](project.json) určuje například, kde bude soubor z `--out`, zda se má psát log a zda se mají zaznamenávat výsledky do DB:

```json
{
  "subdir": "project_test",
  "selector": "mcp",
  "log": true,
  "debug": false,
  "db": true
}
```

## Praktické poznámky

- V PowerShellu i jiných shellech je bezpečné psát násobení jako `--operation "*"`, aby hvězdička nebyla rozbalena jako zástupný znak pro soubory.
- Přímý režim testuje MCP server a nástroj. Netestuje schopnost modelu používat nástroje.
- Režim `--ollama` testuje navíc model a lokální Ollama API. Je proto vhodný při změně modelu, aktualizaci Ollamy nebo při úpravě schema toolu.
- Pokud je port z `mcp_config.json` obsazený, CLI se zastaví, aby omylem nepoužilo cizí už spuštěný server.

## TODO / nice to have

Následující věci nejsou nutné pro současný provoz, ale mohou integraci zpřehlednit nebo rozšířit:

- [ ] Přidat `--no-db` pro jednorázový běh bez zápisu, i když má projekt v `project.json` `"db": true`.
- [ ] Přidat `--json` pro strojově čitelný výsledek (tool, argumenty, výsledek, doba trvání, stav).
- [ ] Přidat `--timeout` pro samostatné omezení čekání na MCP server a na jednotlivé odpovědi Ollamy.
- [ ] Přidat `--all` pro rychlé přímé otestování všech toolů s předdefinovanými bezpečnými argumenty.
- [ ] Přidat automatické testy `cli_mcp.py` s testovacím MCP serverem a mockovanou Ollama odpovědí.
- [ ] V režimu `--ollama` porovnat finální text modelu s výsledkem toolu a jasně nahlásit, když model výsledek změní nebo doplní komentář.
- [ ] Přidat vzdálený HTTP MCP endpoint jako další typ `--server-config`.
- [ ] Přidat `--ollama` také pro obecný `--server-config` režim.
- [ ] Zobrazit při `--list` i schema parametrů (`inputSchema`), nejen název a popis toolu.

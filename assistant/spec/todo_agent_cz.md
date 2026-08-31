# Lokální agent a Cowork · Code – návrh postupné integrace

## Účel

V repozitáři nyní existuje funkční prototyp lokálního coding agenta:
`cli_agent.py`. Je určený pro práci v aktivním projektu z `project.json` a
využívá lokální Ollamu. Cílem je ověřitelně rozšířit James o samostatný režim
**Cowork → Code**, ve kterém může model iterativně pracovat se soubory a po
potvrzení spouštět příkazy.

Tento režim nemá nahrazovat běžný James Chat. Chat zůstane předvídatelný
pro otázky, RAG a explicitní slash příkazy. Cowork · Code bude záměrný pracovní
prostor pro tvorbu a ověřování malých programů, úprav projektu a dalších
artefaktů.

## Aktuální stav

### `cli_agent.py`

Agent má klasickou nástrojovou smyčku:

```text
uživatelův požadavek
        ↓
Ollama /api/chat
        ↓
modelový text nebo tool call
        ↓
spuštění nástroje a návrat výsledku modelu
        ↓
Ollama /api/chat
        ↓
finální odpověď
```

Používá nativní Ollama `/api/chat`, nikoli OpenAI kompatibilní endpoint. Ve
verbose režimu se odpověď streamuje, takže terminál průběžně ukazuje oddělené
bloky `[thinking]`, `[answer]`, požadované nástroje a jejich výsledky.

Aktivní pracovní adresář je načtený z root `project.json` přes stejné helpery
jako ostatní CLI. Při současné konfiguraci jde o `proj_snake`.

### Dostupné nástroje

Schema je v `assistant/tools/tool_schema.json`; adresář `assistant/tools` proto
obsahuje pouze deklarativní data. Jeden soubor obsahuje dva profily: `light`
pro základní file/shell nástroje včetně Python venv a `extended` pro základ
plus rozšířené nástroje.
`cli_agent.json: tool_schema_light: true` zvolí `light`; hodnota `false` zvolí
`extended` (nejde o slučování dvou JSON souborů). Implementace a agentní smyčka
jsou v `lib/wrapp_agent.py`.

`cli_agent.json: options` drží Code-specifické Ollama overrides, například
`num_ctx` a `num_predict`. Agent je skládá nad obecné výchozí hodnoty z
`lib/ollama.json`; běžné James Chat tasky tím nemění.
Výchozí Code profil používá `temperature: 0.1` pro stabilnější implementace a
`repeat_penalty: 1.05`, aby netlumil běžná opakování v kódu příliš agresivně.

`cli_agent.json: auto_continue: true` dovolí jednu automatickou návaznou
výzvu, pokud model předčasně ukončí běh popisem práce v budoucím čase místo
provedení nástrojů. Je omezená na jeden pokus, aby nevznikla nekonečná smyčka.

| Nástroj | Účel | Současné chování |
|---|---|---|
| `session_info()` | živé údaje o Code seanci | model, nastavení, čas a počet tool calls; automatické čtení |
| `list_files(path)` | výpis obsahu adresáře | automatické čtení |
| `read_file(path, start_line?, end_line?)` | čtení celého souboru nebo řádkového výřezu | automatické čtení |
| `find_text(query, path?, glob?)` | hledání textu v projektových zdrojích | automatické čtení |
| `file_info(path)` | typ, velikost, přípona a změna souboru | automatické čtení |
| `write_file(path, content)` | vytvoření nebo přepsání souboru | automatický zápis |
| `apply_patch(path, patch)` | ověřená malá změna přes unified diff | dle policy pro zápis |
| `toolchain_info()` | nalezení překladačů C, C++ a Rust v `PATH` | automatické čtení |
| `python_runtime_info()` | nalezení `.venv`/`venv` a pygame | automatické čtení |
| `run_python(path, args?, stdin?, timeout_seconds?)` | spuštění projektového Pythonu přes existující venv | 30 s default, max. 120 s, strukturovaný report; potvrzení dle `cli_agent.json: run_confirm` |
| `web_runtime_info()` | nalezení Node.js a prohlížečů v `PATH` | automatické čtení |
| `serve_project(path?, port?)` | dočasný HTTP server pouze na localhost | potvrzení dle `cli_agent.json: run_confirm` |
| `browser_test(url, expected_text?)` | read-only kontrola DOMu lokálního serveru | automatické čtení |
| `run_command(command, stdin?)` | spuštění shellového příkazu; volitelně testovací vstup | potvrzení dle `cli_agent.json: run_confirm` |

Ověřený scénář s `qwen3.5:latest`:

1. model vytvořil `primes.py` přes `write_file`,
2. dostal zpět výsledek zápisu,
3. v dalším kroku vyžádal `run_command("python3 primes.py")`,
4. po potvrzení vyhodnotil skutečný výstup programu,
5. teprve poté uzavřel odpověď.

To potvrzuje, že funguje agentní loop i předávání výsledků nástrojů zpět do
modelu.

### Limity současného prototypu

- `ProjectToolScope` nyní odmítá absolutní cesty i cesty, které by opustily
  aktivní projekt; platí to i pro čtení a zápis přes symbolické odkazy.
- Zápis se řídí policy: Observe jej zakáže, Draft vyžádá potvrzení a Code jej
  povolí uvnitř aktivního projektu.
- `AgentRun` drží v paměti prompt, tool volání, artefakty, výsledek i dobu
  běhu. Dokončené běhy se při `db: true` ukládají do `data/tasks.db`.
- `cli_agent.py` je samostatné CLI. James ho zatím neumí spustit ani zobrazit
  jeho historii.
- Běžný James Chat ukládá konverzační kontext do souborů a posílá jednotlivé
  požadavky přes `runner.py`; nepoužívá nativní nástrojovou konverzaci Ollamy.

## Produktové rozdělení: Chat versus Cowork

| Oblast | James Chat | Cowork · Code |
|---|---|---|
| Primární účel | otázky, RAG, práce s kontextem | tvorba a ověřování artefaktů |
| Akce nad soubory | explicitní `/files`, `/cat`, `/add` | model si vybírá dostupný tool |
| Průběh | jedna modelová odpověď na tah | více kroků: model → tool → model |
| Shell | explicitně přes `/tool` | potvrzení dle viditelné session policy a `run_confirm` |
| Kontext | `chat_context.txt`, RAG, historie chatu | samostatná agentní konverzace a run report |
| Riziko | nízké, uživatel volí každou akci | vyšší, proto scope a policy |

Rozdělení je důležité. Pokud by se agentní tools zapnuly automaticky v běžném
Chatu, model by mohl reagovat na obyčejný dotaz nečekaným zápisem do projektu.
Cowork · Code jasně komunikuje, že uživatel zahajuje pracovní, autonomnější
režim.

## Navržené menu James

```text
MAIN MENU
  cowork

COWORK
  > code
    plans             (později)
    activity          (později)

COWORK · CODE
  > start coding session
    one-shot task
    select model
    project
    tool policy
    recent runs
    setup-info
    help
```

### Položky Cowork · Code

- **start coding session**: otevře interaktivní agentní terminál. Uživatel
  zadává více požadavků, dokud neukončí relaci `exit` nebo `quit`.
- **one-shot task**: zadá jeden cíl, například „vytvoř testovací program“,
  agent jej provede a Cowork se následně vrátí do menu.
- **select model**: ukáže tool-capable lokální modely a uloží volbu pro
  aktuální Cowork session. Výchozí volba může být `qwen3.5:latest`.
- **project**: zobrazí a případně pro Cowork session přepne pracovní projekt;
  nemění root `project.json`, pokud k tomu uživatel nedá explicitní pokyn.
- **tool policy**: nastaví způsob potvrzování nástrojů.
- **recent runs**: zobrazí poslední reporty daného projektu.
- **setup-info**: rozparsovaně ukáže `cli_agent.json`, aktivní Code model,
  schema profil a cestu k task definicím běžného James Chatu.
- **help**: krátce vysvětlí režimy, bezpečnostní pravidla a ukázkový prompt.

### Výsledek po ukončení relace

Cowork zobrazí stručný, ověřitelný report místo spoléhání pouze na modelové
shrnutí:

```text
COWORK · CODE · REPORT

Model: qwen3.5:latest
Project: proj_snake
Tools: 4 calls

Created:
  primes.py

Commands:
  python3 primes.py  → exit code 0

Result:
  Program vypsal prvních deset prvočísel.
```

## Tool policy

Nastavení musí být viditelné před prvním agentním požadavkem. Doporučené jsou
tři režimy:

| Režim | `list_files` / `read_file` | `write_file` | `run_command` |
|---|---|---|---|
| **Observe** | automaticky | zakázán | zakázán |
| **Draft** | automaticky | potvrdit každý zápis | potvrdit každý příkaz |
| **Code** | automaticky | automaticky v aktivním projektu | potvrdit každý příkaz |

Pro Cowork · Code je vhodný výchozí **Code**. Při programování by potvrzování
každého přepsání souboru brzdilo běžnou práci, ale příkazy mohou instalovat
balíčky, spouštět programy nebo měnit prostředí, proto musí zůstat potvrzované.
Pro prohlídku cizího projektu se používá **Observe**; pro citlivé úpravy
**Draft**.

V každém režimu se musí vynutit scope aktivního projektu. Žádný nástroj nesmí
číst ani zapisovat mimo něj, ani když model předá absolutní cestu nebo `..`.

## Cílová architektura

Z dlouhodobého hlediska nemá být `cli_agent.py` zdroj samostatné logiky.
Společná implementace by měla být v knihovně:

```text
                     ┌──────────────────────┐
                     │ lib/wrapp_agent.py   │
                     │                      │
                     │ AgentEngine          │
                     │ Ollama chat/stream   │
                     │ tool loop            │
                     │ policy + scope       │
                     │ run report           │
                     └───────┬────────┬─────┘
                             │        │
                 ┌───────────┘        └───────────┐
                 ▼                                ▼
        cli_agent.py                         james.py
        interaktivní CLI                 Cowork · Code UI
```

### Navržené komponenty

#### `lib/wrapp_agent.py`

- `AgentEngine`: vlastní agentní loop a práce s Ollama `/api/chat`.
- `AgentTool`: název, schema, implementace, bezpečnostní úroveň a popis.
- `ProjectToolScope`: bezpečně resolveuje cestu pod aktivním projektem.
- `ToolPolicy`: pravidla Observe, Draft a Code.
- `AgentRun`: stav jednoho běhu, prompty, tool volání, výsledky, chyby a
  změněné soubory.
- callbacky pro UI: `on_thinking`, `on_content`, `on_tool_call`,
  `on_tool_result`, `on_status`.

CLI i James budou callbacky renderovat odlišně, ale nesmějí mít dvě různé
implementace agentní smyčky.

#### `assistant/tools/`

- `tool_schema.json` zůstane zdrojem definic pro Ollamu a profilů `light` /
  `extended`.
- `assistant/tools` obsahuje pouze tento jeden JSON soubor; implementace file tools je ve
  `lib/wrapp_agent.py` a přijímá `ProjectToolScope`.
- Bezpečnostní metadata toolů (`read`, `write`, `command`) drží `AgentTool`,
  protože samotné JSON schema je neobsahuje.

#### `cli_agent.py`

Po extrakci bude jen tenký obal:

1. načte `project.json`, model, timeout a CLI parametry,
2. vytvoří `ProjectToolScope` a `AgentEngine`,
3. barevně renderuje callbacky přes `wrapp_terminal.Terminal`,
4. obslouží stdin a po ukončení vytiskne report.

#### `james.py`

James bude obsahovat pouze Cowork menu a adaptér terminálu. Pro první verzi
nemusí sdílet Chat historii s agentem. Každý Cowork Code run je samostatná
pracovní relace nad zvoleným projektem.

## Postupný přechod

### Fáze 0 – prototyp a manuální ověření (hotovo)

- [x] vytvořen `tool_schema.json` s lehkým profilem pro základní file/shell
      práci včetně Python venv,
- [x] implementovány souborové tools ve `lib/wrapp_agent.py`,
- [x] vytvořen `cli_agent.py` s nativním Ollama tool loopem,
- [x] přidán `--verbose` se streamovaným thinking a barevným výstupem,
- [x] ověřen zápis Python souboru a jeho spuštění po uživatelském potvrzení.

### Fáze 1 – bezpečný agentní základ

Cíl: agent bude technicky bezpečný pro aktivní projekt ještě před napojením
na James.

- [x] Implementovat `ProjectToolScope(root: Path)`.
- [x] Odmítnout absolutní cesty a cesty, které po resolve opustí root projektu.
- [x] Přidat policy wrapper nad každým toolem.
- [x] Přidat zápis `AgentRun` do paměti a výpis finálního reportu.
- [x] Přidat testy pro `..`, absolutní cesty, neznámé argumenty a odmítnutý
      příkaz.
- [x] Přidat testy pro tool loop s mocknutou Ollama odpovědí, včetně více tool
      volání v jedné odpovědi a více agentních kroků.

Výsledek: `cli_agent.py` zůstane plně použitelný, ale bude skutečně omezený na
zvolený projekt.

### Fáze 2 – rozdělení na knihovnu a CLI

Cíl: zamezit duplikaci, až Cowork začne agent používat.

- [x] Přesunout agentní engine do `lib/wrapp_agent.py`.
- [x] Nechat `cli_agent.py` jako kompatibilní CLI adaptér.
- [x] Zachovat existující argumenty: `--model`, `--prompt`, `--timeout`,
      `--max-steps`, `--verbose`.
- [x] Doplnit `--policy observe|draft|code` a volitelný dočasný projektový
      override validovaný uvnitř rootu.
- [x] Přidat jednotkové testy knihovny bez závislosti na běžící Ollamě.

Výsledek: stejný engine budou moci volat dvě různá rozhraní.

### Fáze 3 – Cowork menu v James (MVP)

Cíl: z `cowork`, které je nyní placeholder, vznikne použitelný vstupní bod
pro Code.

- [x] Nahradit `show_mock(config, "cowork")` funkcí `cowork_menu(config)`.
- [x] Vytvořit `cowork_code_menu(config)` s položkami z návrhu menu.
- [x] Přidat volbu modelu, projektu a policy pro aktuální Cowork session.
- [x] Spustit shared `AgentEngine` a renderovat události přes `Terminal`.
- [x] Po ukončení relace vykreslit `AgentRun` report a nabídnout návrat do
      Cowork menu.
- [x] Zajistit, že přepnutí projektu v Coworku je pouze session-local, stejně
      jako `/proj` v Chat, pokud uživatel výslovně nezmění `project.json`.

Výsledek: James nabízí kontrolovaný coding agent bez změny chování standardního
Chatu.

### Fáze 4 – perzistence a obnova

Cíl: pracovní činnost je dohledatelná i po ukončení James.

- [ ] Ukládat strukturovaný report do `.cowork/code-runs/RUN_ID.json` uvnitř
      aktivního projektu.
- [ ] Ukládat stručné lidsky čitelné shrnutí vedle JSON reportu jako Markdown.
- [ ] Položka `recent runs` zobrazí datum, model, výsledek, chybu a změněné
      soubory.
- [ ] Umožnit zobrazit detail staršího běhu, ne však automaticky pokračovat
      bez nového uživatelského rozhodnutí.

Možná struktura:

```text
proj_snake/
  .cowork/
    code-runs/
      2026-08-30_2215_primes.json
      2026-08-30_2215_primes.md
```

### Fáze 5 – rozšířené tools a pracovní plány

Cíl: navázat na obecnější Cowork návrh, aniž by se Code příliš rychle změnil
v nekontrolovanou orchestrace.

- [x] Přidat projektově omezený `find_text` a bezpečný `file_info`.
- [x] Přidat řádkové výřezy `read_file` a ověřený `apply_patch` pro malé
      změny existujících UTF-8 souborů.
- [x] Přidat read-only `toolchain_info` pro bezpečné zjištění dostupných C,
      C++ a Rust překladačů před kompilací.
- [x] Přidat `python_runtime_info` a `run_python`; první verze pouze používá
      existující `.venv`/`venv`, nevytváří je ani nespouští pip.
- [x] Přidat lokální webový základ: `web_runtime_info`, localhost-only
      `serve_project` a read-only `browser_test` nad renderovaným DOMem.
- [x] Přidat `run_python` s omezeným timeoutem a reportem, jako specializovaný
      tool místo obecných shell příkazů pro běžné Python testy.
- [ ] Přidat read-only RAG tool, který vrátí zdroje společně s výsledky.
- [ ] Přidat MCP tools až po zobrazení služby, parametrů a dopadu.
- [ ] Přidat `cowork_plan.json` pro více kroků, závislosti, stav a ruční
      schvalování pracovního plánu.
- [x] Přidat read-only roli revizora, která kontroluje artefakt a test output,
      ale nedostává zapisovací ani příkazové tools.

## Doporučený formát `AgentRun`

```json
{
  "id": "2026-08-30_2215_primes",
  "started_at": "2026-08-30T22:15:00+02:00",
  "project": "proj_snake",
  "model": "qwen3.5:latest",
  "policy": "code",
  "prompt": "Napiš program pro výpočet prvních deseti prvočísel.",
  "status": "completed",
  "tools": [
    {
      "step": 1,
      "name": "write_file",
      "arguments": {"path": "primes.py"},
      "status": "completed",
      "result_summary": "Saved primes.py (797 characters)"
    },
    {
      "step": 2,
      "name": "run_command",
      "arguments": {"command": "python3 primes.py"},
      "approved": true,
      "status": "completed",
      "exit_code": 0
    }
  ],
  "artifacts": ["primes.py"],
  "final_answer": "Program funguje správně."
}
```

Do reportu se nemají ukládat celá tajemství, proměnné prostředí ani nezkrácené
velké výsledky příkazů. Pro obsah souborů a dlouhé výstupy je vhodný odkaz na
projektový artefakt nebo omezený preview.

## Kritéria hotové první verze Cowork · Code

- Uživatel se z hlavního menu dostane na `Cowork → Code`.
- Zobrazí se aktivní projekt, model a tool policy ještě před prvním promptem.
- Model umí v jednom běhu použít více tool kroků.
- Streamovaný thinking, odpověď, tool call a výsledek mají konzistentní
  barevné rozlišení přes `wrapp_terminal`.
- Každý příkaz vyžaduje explicitní potvrzení.
- Každá souborová operace je vynuceně omezena na aktivní projekt.
- Po dokončení nebo chybě vznikne stručný run report.
- Běžný James Chat, jeho slash příkazy a ukládání `chat_context.txt` zůstanou
  beze změny.

## Otevřená rozhodnutí

1. Má policy **Draft** potvrzovat každý zápis, nebo nejdříve ukázat diff a
   potvrdit sadu změn najednou?
2. Má se model pro Cowork pamatovat jen v jedné James session, nebo také v
   perzistentní konfiguraci?
3. Mají být reporty pouze v `.cowork/`, nebo mají vznikat i záznamy v
   `data/tasks.db`?
4. Má Cowork Code zpočátku podporovat pouze Python, nebo obecné soubory a
   příkazy s bezpečnostní policy?
5. Kdy má být Code propojen s RAG a MCP? Doporučení: až po scope, reportech a
   testech základních file tools.

## Doporučené další rozhodnutí

Začít Fází 1: vynutit scope aktivního projektu a zavést strukturovaný run
report. Teprve potom má smysl stavět Cowork menu; tím se vyhne přenesení
prototypových bezpečnostních limitů přímo do hlavního James rozhraní.

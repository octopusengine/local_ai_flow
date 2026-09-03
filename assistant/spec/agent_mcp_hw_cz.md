# Externí hardware jako MCP služba pro agenta

## Účel a rozhodnutí

Cílem je, aby agent (James, Cowork nebo lokální model) uměl bezpečně pracovat
s externím hardwarem: provést předem definovanou akci, přečíst senzor a vrátit
strojově čitelný výsledek. Prvním ověřeným případem je ESP32-C3 přes BLE Nordic
UART Service (NUS): LED se po příkazech `led-on` a `led-off` rozsvítí a zhasne.

Rozhodnutí pro architekturu:

- `cli_ble.py` zůstává samostatné lidské CLI pro scan, GATT diagnostiku,
  ruční ověření zařízení a správu `devices.json`.
- `cli_tool.py` se o BLE nerozšiřuje. Jeho použití by jen zdvojilo rozhraní,
  které už `cli_ble.py` poskytuje lépe.
- Vznikne samostatný MCP server `mcp/hw_mcp_server.py`; server nebude vnořen
  ani do `cli_ble.py`, ani do `cli_mcp.py`.
- `cli_mcp.py` zůstane univerzální MCP klient/tester. Přes existující
  `--server-config` bude umět spustit a otestovat HW server stejně jako MCP
  službu pro práci se soubory.
- Komunikace s BLE, později UARTem či jinými transporty, patří do společné
  knihovní vrstvy. MCP server má být pouze bezpečné agentní API, ne další
  implementace Bluetooth protokolu.

Navržené uspořádání:

```text
James / Cowork / Ollama agent
            │ MCP
            ▼
mcp/hw_mcp_server.py          samostatná, lokální HW služba
            │
            ▼
lib/device_runner.py          vykonání konfigurací povolené akce
            │
            ├── BLE / lib/wrapp_ble.py
            ├── později UART, HTTP, GPIO, ...
            ▼
devices.json + .env           allowlist konfigurace a neveřejná tajemství
            ▼
ESP32-C3 a další zařízení

cli_ble.py                    ruční diagnostika a správa; používá stejnou vrstvu
cli_mcp.py                    testuje MCP server, není HW serverem
```

## Zjištěný výchozí stav

### BLE a ESP32

- `cli_ble.py` funguje jako multiplatformní BLE klient nad knihovnou Bleak.
  Umí scan, GATT průzkum, bezpečné čtení, zápis, notifikace, párování, retry,
  logování a správu pojmenovaných zařízení.
- ESP32-C3 inzeruje BLE NUS. Z pohledu počítače se příkaz zapisuje do
  `nus-rx`; odpovědi přicházejí notifikací z `nus-tx`.
- `devices.json` má profil `nordic-uart` a zařízení `test-led`. Obsahuje
  pojmenované akce `led-on`, `led-off`, `led-toggle` a `esp-hi`.
- `led-on` používá rámec Bluefruit `!B516`; `led-off` `!B615`. Aktuální flow
  `flows/flow_test_ble.txt` ověřil fyzické rozsvícení a následné zhasnutí LED.
- Identita BLE zařízení se nejprve hledá podle prefixu reklamního jména a
  uložená MAC slouží jako záloha. To je správné pro zařízení s měnící se
  privátní adresou.

### Konfigurace a tajemství

- `devices.json` odděluje technické UUID a rámce protokolu od pojmenovaných
  akcí, které může člověk nebo agent použít.
- U `test-led` je autentizace propojená na název proměnné prostředí `KEY1`.
  `lib/device_runner.py` načte hodnotu z `.env`, po spojení ji odešle před
  vlastním příkazem a nikdy ji nezařadí do výsledku ani logu.
- Jde pouze o jednoduchý sdílený klíč. Bez párování a šifrování může být
  přenášen čitelně; není vhodný jako ochrana pro citlivé či nebezpečné zařízení.
- Současný runner klíč odešle, ale zatím explicitně nečeká na potvrzení `ok`
  před vlastním příkazem. To je vhodné opravit před rozšířením na významnější
  výstupy.

### Připravená společná vrstva

`lib/device_runner.py` již obsahuje správné jádro pro agentní rozhraní:

- `run_device_tool(...)` přijímá jen `device_id` a `tool_id` definované v
  konfiguraci;
- vrací `DeviceToolResult` s informací o spojení, necitlivém odeslaném
  příkazu, notifikacích, diagnostice, době běhu a strukturované chybě;
- chyby rozlišuje na konfiguraci, autentizaci, nenalezené zařízení, spojení,
  timeout, GATT a neočekávanou chybu;
- nezávisí na terminálovém výstupu, takže jej mohou shodně použít CLI, MCP
  server i budoucí webové rozhraní.

## Proč samostatný MCP server

`cli_mcp.py` je klient, který spouští nebo připojuje MCP server a testuje jeho
tools. Není vhodným místem pro obchodní logiku externího HW. Samostatný
`mcp/hw_mcp_server.py` přináší jasnou hranici schopností: James/Cowork si jej
přidá jako další lokální službu vedle filesystem MCP, lze jej samostatně
verzovat, testovat i omezit.

První transport má být `stdio`, protože je lokální, bez otevřeného portu a
odpovídá běžnému spouštění MCP služeb agentem. Volitelný Streamable HTTP lze
přidat později pouze na `127.0.0.1`, pokud jej vyžaduje konkrétní hostitel nebo
je praktický pro vývoj. Je vhodné vytvořit konfiguraci například
`mcp/hw_server.json`, kterou přečte `cli_mcp.py --server-config ...`.

Stávající `mcp/wrapp_mcp_server.py` je obecný lokální server. HW tools do něj
zatím nezačleňujeme: soubory, výpočty a fyzické akce mají odlišná oprávnění,
životní cyklus i bezpečnostní politiku. Pozdější společný katalog může obě
služby sjednotit, ale není důvod ztratit nyní samostatnou hranici.

## MCP rozhraní první verze

Názvy jsou záměrně obecné (`hardware_`), aby později zahrnuly BLE, UART i další
transporty. Vstupem jsou pouze ID z konfigurace, nikdy UUID, raw payload nebo
příkaz shellu.

| Tool | Vstup | Výstup | Poznámka |
| --- | --- | --- | --- |
| `hardware_list_devices` | bez vstupu | zařízení, popis a dostupné akce | Zjistí povolené možnosti bez připojení k HW. |
| `hardware_device_info` | `device_id` | veřejná konfigurace zařízení a akce | Nevrací MAC, klíč ani raw autentizační údaje, pokud to není nutné. |
| `hardware_run_action` | `device_id`, `action_id`, volitelně bezpečný timeout | strukturovaný `DeviceToolResult` | Jediný tool, který fyzicky něco provádí. |

Pro první vertikální řez stačí implementovat `hardware_list_devices` a
`hardware_run_action("test-led", "esp-hi")`, potom `led-on` a `led-off`.
`hardware_device_info` může následovat ihned poté, protože je čistě
konfigurační.

Příklad odpovědi pro agenta:

```json
{
  "ok": true,
  "device_id": "test-led",
  "action_id": "esp-hi",
  "description": "Send a greeting and wait for hello",
  "connected": true,
  "authentication_sent": true,
  "sent": [{"characteristic": "...", "text": "hi"}],
  "notifications": [{"text": "hello"}],
  "duration_ms": 1200,
  "diagnostics": []
}
```

V produkčním MCP výsledku je vhodné prezentovat odpovědi i bezpečně jako UTF-8
text, pokud je dekódovatelný, a vždy jako hex. Hodnota klíče se nesmí vrátit
ani při chybě.

## Budoucí senzory a potvrzení stavu

Teplota nemá dostat vlastní ad-hoc větev v MCP serveru. ESP firmware nejprve
definuje pojmenovaný příkaz a odpověď; konfigurace pak získá akci například
`temperature-read` s notifikací. Po stabilizaci protokolu se přidá deklarativní
dekodér a až pak tool `hardware_read_value`.

Preferovaný přechodový protokol z ESP je JSON v notifikaci, například:

```json
{"ok":true,"led":true,"firmware":"0.1"}
{"ok":true,"temperature_c":23.7}
```

Agent pak dostane hodnoty jako skutečná pole, nikoli nutnost vykládat volný text.
Pro senzory se doplní čas měření, jednotka a validace rozsahu. Pro výstupy je
vhodnější `led-on`/`led-off` než `led-toggle`, protože idempotentní operace se
po timeoutu nebo opakování chová předvídatelně.

## Bezpečnostní pravidla

- MCP server může vykonat pouze zařízení a akce uložené v `devices.json`.
- Nevystavovat obecný BLE scan, GATT read/write, UUID ani binární payload jako
  běžné agentní tools. Ty zůstávají dostupné jen přes ruční `cli_ble.py`.
- `.env` je lokální zdroj tajemství; tajemství nikdy nevypisovat, neukládat do
  auditního logu a nevracet přes MCP.
- Každá konfigurace akce má mít bezpečnostní klasifikaci, minimálně
  `read_only`, `actuator_safe` a `actuator_confirm`.
- `actuator_confirm` nesmí server spustit bez potvrzení, které zprostředkuje
  hostitel agenta. První verze může takovou akci odmítnout se strukturovaným
  stavem `confirmation_required`.
- Pro relé, motory, topení a podobné výstupy vyžadovat bezpečný výchozí stav,
  maximální dobu běhu a hardwarovou ochranu nezávislou na agentovi.
- Přidat auditní záznam: čas, device/action ID, výsledek, chybový typ a doba
  běhu. Nesmí obsahovat klíč, raw autentizační data ani zbytečně citlivý obsah
  senzorů.
- Agent nesmí po chybě bez omezení opakovat fyzickou akci. Server má vracet
  jasné typy chyb; policy později doplní cooldown a limit pokusů.

## Postup implementace a testování

### 0. Zmrazení výchozího stavu

- [x] Ověřit ruční flow `flows/flow_test_ble.txt`: LED se zapne a vypne.
- [x] Uložit zařízení `test-led`, profil NUS a akce do `devices.json`.
- [x] Oddělit vykonání akce do `lib/device_runner.py`.
- [x] Přidat/ověřit automatický test, že `devices.json` pro `test-led` projde
  validací a obsahuje `led-on`, `led-off` a `esp-hi`.
- [ ] Zaznamenat běžnou dobu scanu, spojení a `esp-hi`, aby MCP timeouty měly
  reálný základ.

#### Referenční měření 2026-09-02

Měření proběhlo ve stejném prostředí jako tento projekt, příkazy neměnily
konfiguraci ani firmware. Nejde ještě o běžnou dobu: ESP se v tomto okamžiku
nepodařilo spolehlivě připojit, proto zůstává příslušný checkbox otevřený.

| Operace | Příkaz | Naměřený čas | Výsledek |
| --- | --- | ---: | --- |
| Scan | `python cli_ble.py -s --name octopus-led --timeout 5` | 5 550 ms | Žádný odpovídající výpis zařízení. |
| Připojení a GATT inspekce | `python cli_ble.py -d test-led --timeout 5` | 10 450 ms | `device_not_found`; proběhl úvodní scan i čerstvý scan po selhání připojení. |
| Pozdrav | `python cli_ble.py -d test-led esp-hi --timeout 5` | 5 370 ms | `device_not_found`, bez odeslání akce. |

Po ověření zapnutého ESP a stabilního BLE spojení zopakovat každý scénář alespoň
třikrát. Zapsat medián a rozptyl pro scan, úspěšné připojení/GATT inspekci a
úspěšné `esp-hi`; až z těchto hodnot odvodit výchozí MCP timeout.

### 1. Zpevnění BLE kontraktu před MCP

- [ ] Zachovat zcela lokální tok autentizace: `devices.json` pouze odkáže na
  proměnnou z `.env`, firmware ověří klíč pro dané BLE spojení a běžné
  testovací LED akce nevyžadují další zásah uživatele. Potvrzení `ok` zatím
  pouze vracet a logovat, nikoli na něm blokovat další akci.
- [x] Implementovat ve zdrojovém firmware `status` s JSON odpovědí o stavu
  červené a zelené LED a verzi firmware; přidat `red-on`, `red-off`,
  `green-on`, `green-off` a `temperature-read` s hodnotou `dummy_temp`.
- [x] Nahrát `esp_upy/test_ble_key.py` ve verzi `test_ble_key-0.2` do ESP a
  ověřit přes BLE zpětnou kompatibilitu `led-on` a `led-off`. Obě akce vrátily
  `ok` a JSON stav s očekávanou hodnotou `led.red`.
- [x] Ověřit přes BLE explicitní ovládání červené i zelené LED. Barevné akce
  vracejí JSON stav LED; původní `led-on` a `led-off` zůstávají kompatibilní.
- [x] Ověřit přes BLE `temperature-read`: vrací JSON
  `{"ok":true,"temperature_c":21.3,"unit":"degC"}` z `dummy_temp`.
- [x] Ověřit samostatný příkaz `status`: vrací JSON stavu obou LED a verzi
  firmware. Rozšíření firmware je tím potvrzeno i na HW.
- [x] Ověřit ručně pozitivní scénář: `esp-hi` vrací `ok` a `hello`.
- [x] Ověřit ručně negativní scénář: chybný/nepřítomný klíč nezmění LED a
  vrací bezpečnou odpověď `unauthorized` bez vyzrazení hodnoty klíče.
- [x] Ověřit odpojené ESP, slabý signál a timeout: fyzická akce se neprovede
  a běh skončí strukturovanou chybou. Texty diagnostiky se doladí později.

### 2. MCP server – minimální vertikální řez

- [x] Vytvořit `mcp/hw_mcp_server.py` přes FastMCP se stdio transportem.
- [x] Vytvořit `mcp/hw_server.json` pro spuštění serveru z `cli_mcp.py` a
  z James/Cowork; pracovní adresář je kořen projektu a příkaz `python` tedy
  používá stejný aktivní interpreter jako hostitel.
- [x] Implementovat `hardware_list_devices` výhradně z veřejné části
  `devices.json`; odpověď neobsahuje adresu, BLE profil, raw payload ani
  nastavení autentizace.
- [x] Implementovat `hardware_run_action` s validací ID a voláním
  `device_runner.run_device_tool(...)`.
- [x] Převést `DeviceToolResult` na stabilní JSON-safe slovník; data notifikací
  vracet jako text, pokud je dekódovatelný, a vždy jako hex.
- [x] Zaručit v implementované MCP vrstvě, že veřejný katalog a serializovaný
  výsledek neobsahují `.env` klíč; server sám nezapisuje debug výstup na stdout.
  Pokrývají to regresní testy bez připojeného HW.
- [x] Otestovat přes `cli_mcp.py --server-config mcp/hw_server.json --list`.
  Ve VS Code `venv` byly nalezeny právě `hardware_list_devices` a
  `hardware_run_action`.
- [x] Otestovat přímé MCP volání `hardware_list_devices` bez připojeného ESP.
  Vrátilo pouze povolené názvy zařízení a akcí; MAC, UUID, raw payloady ani
  `KEY1` nebyly ve výstupu přítomné.
- [x] Otestovat přímé MCP volání `hardware_run_action(test-led, esp-hi)` s
  fyzickým ESP a porovnat výsledek s `cli_ble.py`: spojení, lokální
  autentizace, odeslání `hi` a notifikace `ok`/`hello` uspěly. Runner naměřil
  34 873 ms, celý MCP test 35,7 s; hodnota klíče nebyla ve výstupu přítomná.
- [x] Rozdělit v James `MCP` na katalog modulů `MCP base`, `MCP hardware` a
  `MCP nostr`. Base zachovává původní run/list/setup; hardware má samostatný
  výpis allowlistovaných tools, setup a BLE requirements. Chybějící volitelné
  soubory (`cli_ble.py`, `requirements_ble.txt` aj.) zobrazí instalační
  nápovědu bez pádu Jamesu; Nostr je zatím vstup „připravujeme“.

Poznámka k testovacímu prostředí: tento běh Codexu používá systémový Python
3.10 bez MCP SDK, proto zde `cli_mcp.py --server-config mcp/hw_server.json
--list` skončil před spuštěním serveru. Závěrečné MCP integrační testy je třeba
spustit ve funkčním VS Code `venv`, ve kterém je MCP SDK nainstalované.

### 3. Ovládání LED a agentní integrace

- [x] Přidat do veřejného popisu akcí klasifikaci side effectu; `led-on` a
  `led-off` jsou `actuator_safe`, zatímco `led-toggle` je `actuator_toggle`,
  zůstává pro ruční CLI a hardware agent/MCP jej odmítne.
- [x] Otestovat `led-on` a `led-off` přes MCP s vizuálním ověřením LED.
- [x] Otestovat opakované `led-on` a `led-off`; stav zůstává předvídatelný.
- [x] Zpřístupnit HW v James/Cowork jako samostatnou lokální schopnost profilu
  `hardware`. James/Cowork není MCP klient: oba agentní tools přímo volají
  stejný allowlist `lib/hw_mcp.py` jako samostatný MCP server, takže nevzniká
  druhá neřízená BLE cesta.
  Profil neobsahuje `run_command` ani `run_python`, protože by jimi šlo obejít
  jmenný allowlist přes ruční BLE CLI. Cowork vybírá `light`, `code` a
  `hardware` z deklarativního `james/agents.json`; každý profil má vlastní
  model a sadu tools. Čtení či vyhledávání hodnot z `.env` je pro agentní
  file tools odmítnuto.
  Hardwarová relace nemá automatické pokračování ani následný coding review:
  obojí by mohlo bez nového pokynu uživatele opakovat nebo chybně posuzovat
  fyzickou akci. Její instrukce doporučují katalog HW při nejasném požadavku a
  zakazují tvrdit úspěch bez výsledku `hardware_run_action` s `ok: true`.
- [x] Ověřit, že agent umí podle potřeby načíst `hardware_list_devices` a
  dokončit požadavek „rozsviť LED“ pouze přes `hardware_run_action`. V Cowork
  sezení agent vypsal katalog, zvolil `test-led` / `red-on` a výsledný JSON
  potvrdil stav `red: true`; vizuální ověření LED uspělo. Katalog není povinný
  před každou akcí ani před každým dalším vstupem v téže konverzaci; allowlist
  validuje samotný `hardware_run_action`.
- [x] Ověřit, že prompt požadující raw UUID/payload ani neznámou akci nezíská
  schopnost provést BLE zápis. Hardware profil nevystavuje shell, Python
  runner ani raw BLE tool; `hardware_run_action` přijímá jen explicitně
  agent-enabled ID a test neznámé akce potvrzuje odmítnutí před runnerem.
  Ruční `cli_ble.py` s lokálním klíčem zůstává záměrně samostatná privilegovaná
  diagnostická cesta, nikoli schopnost agenta/MCP.

### 4. Observabilita a policy

- [ ] Přidat auditní log s redakcí tajemství a rotační strategií souboru.
- [ ] Přidat volitelný režim opakování pro zařízení či akci: výchozí je jeden
  pokus; měřicí seance mohou mít explicitní timeout, počet opakování a prodlevu.
- [ ] Přidat `hardware_health` pouze jako neinvazivní kontrolu dostupnosti,
  RSSI a odezvy.
- [ ] Rozšířit `devices.json` o `risk_level` a `requires_confirmation`.
- [ ] Integrovat potvrzení rizikové akce s mechanismem konkrétního hostitele;
  bez integrovaného potvrzení server akci odmítne.

### 5. Senzory a další transporty

- [ ] Definovat a zdokumentovat firmware protokol pro `temperature-read`.
- [ ] Přidat parser/validaci odpovědi `temperature_c`, jednotku a čas měření.
- [ ] Implementovat `hardware_read_value` až nad tímto stabilním kontraktem.
- [ ] Přidat testy hraničních hodnot, neplatného JSONu a timeoutu notifikace.
- [ ] Navrhnout transportní adaptér pro UART, aniž by se měnilo MCP API:
  `hardware_run_action(device_id, action_id)` zůstává stejné.
- [ ] Pro výkonné akční členy doplnit fyzický fail-safe a nezávislý časový
  limit ještě před jejich zpřístupněním agentovi.

## Kritéria první hotové verze

První verze je hotová, až když James/Cowork lokálně objeví samostatný HW MCP
server, dokáže vypsat `test-led`, provést `esp-hi`, `led-on` a `led-off` a
obdrží strukturované výsledky. Současně platí, že žádný MCP tool neumí odeslat
libovolný BLE příkaz, tajný klíč se nikde neobjeví a chyba spojení nespustí
neomezené opakování fyzické akce.

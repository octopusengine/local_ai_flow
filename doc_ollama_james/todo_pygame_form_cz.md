# TODO: agentní testování pygame a HTML/JS formulářů

Cílem je umožnit agentům James / Cowork nejen napsat aplikaci a spustit ji, ale také provést konkrétní interakce a ověřit jejich výsledek. Dokument je návrh postupného rozšíření, nikoli popis již dostupných funkcí.

Priorita: **nejprve formuláře přes Playwright, následně testovací rozhraní pygame**. Ovládání celé plochy přes screenshoty a klávesnici je samostatná pozdější etapa.

## 1. Výchozí stav

- [x] Agent má nástroje pro čtení, úpravy a spuštění kódu v projektu.
- [x] `serve_project` poskytuje lokální server pro projekt.
- [x] `browser_test` spouští headless Chromium, načte DOM a může vyhledat očekávaný text.
- [x] Schéma označuje `browser_test` jako čtecí kontrolu; neodesílá formuláře a je dostupný také reviewerovi.
- [ ] Doplnit interakce s formuláři a ověřování výsledků akcí.
- [ ] Doplnit řízené testování a hraní pygame.

Aktuální implementace a místa napojení:

- [lib/wrapp_agent.py](../lib/wrapp_agent.py) – implementace nástrojů, agentní smyčka a review.
- [assistant/tools/tool_schema.json](../assistant/tools/tool_schema.json) – parametry nástrojů a profily dostupnosti.
- [agent/agents.json](../agent/agents.json) – modely, generovací parametry a výběr nástrojů.
- [agent/cowork_coding.txt](../agent/cowork_coding.txt) – společné instrukce Coding agenta.
- [agent/README.md](../agent/README.md) – dokumentace agentních relací.
- [tests/test_wrapp_agent.py](../tests/test_wrapp_agent.py) – testy wrapperu.

Dosavadní běh Tetrisu ukázal rozdíl mezi spuštěním a ověřením: agent spustil pygame, ale hru ovládal uživatel. První běh odhalil pád při rotaci, další skončil limitem běhu. Timeout interaktivní aplikace sám neznamená chybu hry ani úspěšné ověření její funkčnosti.

## 2. Společné zásady

- [ ] Oddělit úspěšné spuštění aplikace od úspěšného testu jejího chování.
- [ ] Každý test musí mít konkrétní očekávání: co se po akci změní a co se změnit nesmí.
- [ ] Vrátit výsledek `passed`, `failed`, `error` nebo `timeout`; chybějící prostředí vykázat jako `unavailable`.
- [ ] Uvádět provedené kroky, první problém, dobu běhu a odkazy na artefakty.
- [ ] Oddělit čas modelu, start prostředí a samotné provádění testu.
- [ ] Omezit počet akcí, dobu jednoho kroku i celého scénáře.
- [ ] Zajistit ukončení procesů a uvolnění prostředků při chybě i přerušení.
- [ ] V instrukcích vyžadovat, aby agent po opravě zopakoval dotčený scénář a nepovažoval samotné uložení souboru za dokončení práce.

Lokální modely mohou rozhodovat desítky sekund. Proto má první verze provádět více akcí v jednom nástrojovém volání. Pro hru je vhodné krokování simulace; agent nemá závodit s padající figurkou v reálném čase.

## 3. HTML/JS formuláře – první použitelná verze

### 3.1 Prostředí a rozsah

- [ ] Ověřit způsob správy Python závislostí a přidat Playwright do odpovídajícího instalačního postupu.
- [ ] Vyřešit dostupnost podporovaného prohlížeče na Windows i Linuxu; jasně odlišit chybějící balíček od chybějícího browseru.
- [ ] Rozšířit `web_runtime_info` o dostupnost interaktivního testování a návod k doplnění prostředí.
- [ ] Spouštět pro každý scénář izolovaný browser context, aby cookies a local storage neovlivňovaly další test.
- [ ] Zachovat headless režim jako výchozí; viditelné okno přidat jako explicitní volbu pro ladění.
- [ ] Pro první etapu používat statickou HTML/JS stránku z `serve_project`; backendové aplikace řešit navazující etapou.

### 3.2 Nový nástroj `browser_interact`

Název i rozhraní níže jsou návrh. Stávající `browser_test` ponechat kompatibilní. Interakce nemají být automaticky přidány do čtecího review: tlačítko může změnit data i při přístupu na localhost.

- [ ] Přidat nový nástroj do schématu a runtime registru.
- [ ] Zařadit jej do vhodných Coding profilů; stanovit jeho kategorii v existující politice nástrojů.
- [ ] Povolit pouze lokální aplikace spuštěné či výslovně registrované pro danou relaci.
- [ ] Validovat scénář před spuštěním: známé akce, požadované argumenty, délky hodnot a maximální počet kroků.
- [ ] Podporovat `fill`, `click`, `check`, `uncheck`, `select` a `press`.
- [ ] Podporovat kontroly `expect_text`, `expect_value`, `expect_visible`, `expect_checked` a stav povoleného/zakázaného prvku.
- [ ] Preferovat lokátory podle labelu, role a přístupného názvu; umožnit CSS selector jako doplněk.
- [ ] Nejednoznačný lokátor vykázat jako problém, nikoli automaticky kliknout na první shodu.
- [ ] Používat čekání na dosažení podmínky a vestavěné čekání Playwrightu místo pevných dlouhých pauz.
- [ ] Po první chybě standardně scénář zastavit; pokračování zavést pouze jako výslovnou volbu.

Příklad navrhovaného volání:

```json
{
  "url": "http://localhost:8000/form.html",
  "steps": [
    {"action": "fill", "selector": "#email", "value": "test@example.cz"},
    {"action": "check", "selector": "#souhlas"},
    {"action": "click", "selector": "button[type=submit]"},
    {"action": "expect_text", "selector": "#vysledek", "value": "Odesláno"}
  ]
}
```

Adresa je ilustrativní: v implementaci musí odpovídat serveru registrovanému v relaci. V rámci tohoto dokumentu nástroj ještě není implementován.

### 3.3 Výstup a diagnostika

- [ ] Vrátit strukturované výsledky kroků a stručný souhrn pro model.
- [ ] Při selhání uvést očekávaný a skutečný stav, lokátor a typ chyby.
- [ ] Zachytit neošetřené JavaScript chyby a relevantní chyby konzole.
- [ ] Pořídit screenshot při selhání; umožnit závěrečný screenshot na vyžádání.
- [ ] Uložit artefakty pod samostatné ID běhu do projektové složky, například `test_artifacts/`.
- [ ] Omezit délku DOM výpisu a logů; nevracet celý rozsáhlý dokument do kontextu modelu.
- [ ] Výstupy obsahující hesla a citlivé formulářové hodnoty vhodně maskovat.
- [ ] Rozlišit existenci screenshotu od jeho skutečného zhlédnutí modelem; textový model nemá tvrdit vizuální kontrolu.

Příklad navrhovaného výsledku:

```json
{
  "status": "failed",
  "completed_steps": 3,
  "failed_step": 4,
  "expected": "Text Odesláno v #vysledek",
  "actual": "Prvek je prázdný",
  "javascript_errors": ["TypeError: Cannot read properties of null"],
  "screenshot": "test_artifacts/run_001/failure.png"
}
```

### 3.4 Scénáře pro demonstrační formulář

- [ ] Prázdný formulář: povinná pole zabrání odeslání.
- [ ] Neplatný e-mail: ověřit skutečnou validační vlastnost nebo aplikací vykreslenou chybu, ne pouze přítomnost inputu.
- [ ] Nezaškrtnutý souhlas: ověřit požadované chování.
- [ ] Platné hodnoty: ověřit potvrzení a správnost zpracovaných dat.
- [ ] Oprava chyby: po doplnění platné hodnoty chyba zmizí a odeslání funguje.
- [ ] Ovládání klávesnicí: Tab, Enter a pořadí focusu.
- [ ] Dvojité odeslání: podle zadání ověřit zabránění duplicitě.
- [ ] Reset: hodnoty a validační hlášení se vrátí do očekávaného stavu.

**Hotovo, když:** agent dokáže spustit scénář nad lokálním formulářem, dostane konkrétní chybu, opraví kód a opakovaný scénář projde. Test musí opravdu vyplnit a odeslat formulář.

## 4. Formuláře – backend a další rozšíření

- [ ] Navrhnout registraci lokálního backendu s ověřením připravenosti a řízeným ukončením procesu.
- [ ] Kontrolovat odeslaný request: metodu, cestu a hodnoty payloadu.
- [ ] Přidat simulované odpovědi serveru pro úspěch, validační chybu, HTTP 500 a pomalou odezvu.
- [ ] Rozlišovat test se simulovaným backendem od integračního testu se skutečným uložením.
- [ ] Pro integrační test používat samostatná testovací data a ověřit možnost opakovatelného úklidu.
- [ ] Hlásit neočekávané síťové požadavky a přesměrování; omezení lokálního cíle musí platit i pro navigace, popupy a síťové požadavky stránky.
- [ ] Udržet reviewerovo ověřování čtecí, případně interaktivní review později spouštět jen v izolované testovací instanci.
- [ ] Později doplnit upload souborů, dialogy a responzivní viewporty podle skutečných potřeb.
- [ ] Volitelně přidat Playwright trace pro obtížně reprodukovatelné chyby.

## 5. Pygame – nejprve ověření logiky

Nejlevnější cesta k nalezení chyb nevyžaduje obraz ani řízení celé pracovní plochy. Herní stav musí být testovatelný odděleně od vykreslování a časování okna.

- [ ] Oddělit model hry od hlavní pygame smyčky a vykreslování.
- [ ] Umožnit import modulu bez automatického otevření okna.
- [ ] Umožnit pevný seed nebo přímo připravenou sekvenci figurek.
- [ ] Nahradit ve scénářích reálný čas explicitním krokem simulace.
- [ ] Otestovat směry rotace na nesymetrické figurce: vlevo a vpravo se nesmějí zaměnit.
- [ ] Otestovat čtyři stejné rotace a dvojici protisměrných rotací.
- [ ] Otestovat kolize se stěnou, podlahou a již usazenými bloky.
- [ ] Otestovat vrácení neplatné rotace do původního stavu.
- [ ] Otestovat hard drop: správné místo dopadu, zamknutí a vznik další figurky.
- [ ] Otestovat odstranění jednoho i více řádků a odpovídající změnu skóre.
- [ ] Otestovat konec hry při zablokovaném místě vzniku nové figurky.

**Hotovo, když:** chyby typu prohozených rotací nebo odstraněného atributu figurky zachytí automatický test bez nutnosti ručního hraní.

## 6. Pygame – řízené hraní agentem

### 6.1 Testovací rozhraní aplikace

Následující operace jsou návrh rozhraní, nikoli existující nástroje Jamese:

| Operace | Význam |
|---|---|
| `game_start` | Spustí konkrétní hru v testovacím režimu a vrátí ID relace. |
| `game_state` | Vrátí desku, figurku, pozici, skóre a stav game over. |
| `game_action` | Provede pojmenovanou akci, například posun, rotaci nebo hard drop. |
| `game_step` | Posune simulaci o stanovený počet kroků. |
| `game_stop` | Ukončí pouze příslušnou testovací relaci a uloží výsledek. |

- [ ] Zvolit jednoduchý přenos příkazů a odpovědí, například JSON přes stdin/stdout podprocesu.
- [ ] Oddělit protokol od běžných diagnostických výpisů pygame a aplikace.
- [ ] Navrhnout adaptér pro konkrétní hru; generická hra bez tohoto rozhraní nebude automaticky podporovaná.
- [ ] V testovacím režimu pozastavit gravitaci mezi příkazy agenta.
- [ ] Vrátit kompaktní strukturovaný stav; pro Tetris postačí pole buněk a popis aktuální figurky.
- [ ] Umožnit dávku akcí a omezený počet kroků simulace na jedno volání.
- [ ] Přidat screenshot jako doplněk k ověření vykreslování.
- [ ] Po pádu aplikace vrátit traceback a poslední dostupný stav.
- [ ] Při timeoutu označit, která operace překročila limit; neoznačovat běžící hru automaticky za úspěšnou ani chybnou.

### 6.2 Ověření skutečného ovládání

Přímé zavolání `rotate_left()` neověří, že na ni vede správná klávesa. Pro test kláves je potřeba druhá vrstva přes skutečný handler událostí.

- [ ] Uvnitř procesu hry umožnit vložit pygame události KEYDOWN/KEYUP.
- [ ] Ověřit mapování všech deklarovaných kláves proti zadání a nápovědě.
- [ ] Otestovat posloupnost stisknutí/uvolnění a případné držení klávesy.
- [ ] Ověřit, že mezerník opravdu provede rychlé usazení.
- [ ] Ověřit ukončení okna bez tracebacku a uvolnění pygame prostředků.

`pygame.event.post` vkládá události do fronty daného pygame procesu. Samostatný Python proces tím bez dalšího propojení neovládne již běžící cizí okno; tuto možnost musí obsloužit testovací adaptér hry.

### 6.3 Agentní scénář

- [ ] Agent načte stav hry a vybere z povolených akcí.
- [ ] Provede tah a ověří očekávanou změnu pozice či rotace.
- [ ] Zahraje omezenou sekvenci figurek s pevným seedem.
- [ ] Ověří konkrétní cíl, například odstranění řádku, nikoli jen přežití několik sekund.
- [ ] Uloží akce, stavy, seed a výsledek pro reprodukci.
- [ ] Po opravě hry zopakuje stejný scénář.

**Hotovo, když:** agent bez zásahu uživatele provede herní scénář, ověří očekávané výsledky a ukončí relaci. Jde o testovací hraní; schopnost dobře hrát Tetris je další samostatný cíl.

## 7. Později: ovládání hry pouze obrazem a klávesnicí

Tato varianta je obecnější, ale přidává rozpoznávání obrazu, zaměření okna, platformní rozdíly a prodlevu modelu. Pro první verzi není nutná.

- [ ] Ověřit podporu obrazového vstupu u vybraného lokálního modelu i v agentním runtime.
- [ ] Přidat snímání konkrétního herního okna a předání obrazu modelu.
- [ ] Přidat adresné posílání kláves do vybraného okna; zabránit zásahu do jiné aplikace při ztrátě focusu.
- [ ] Vyřešit samostatně Windows a Linux včetně rozdílů X11/Wayland.
- [ ] Umožnit pozastavení/zpomalení vlastní hry během rozhodování modelu.
- [ ] Porovnat rozpoznaný stav se skutečným stavem testovacího adaptéru.
- [ ] Vyhodnotit latenci, chybovost rozpoznávání a přínos proti strukturovanému rozhraní.

**Hotovo, když:** agent prokazatelně přečte stav ze screenshotu a provede akci v určeném okně. Samotné uložení obrázku nebo spuštění procesu tento bod nesplňuje.

## 8. Testy infrastruktury a integrace do Jamese

- [ ] Jednotkové testy validace scénářů, neznámých akcí a limitů.
- [ ] Test, že chybějící Playwright/browser vrátí srozumitelný stav `unavailable`.
- [ ] Integrační test skutečného formuláře v prohlížeči; nenahradit jej pouze mockem Playwright API.
- [ ] Negativní scénář: test musí selhat při úmyslně rozbité validaci nebo handleru tlačítka.
- [ ] Test úklidu procesů, serverů a browser contextů po selhání.
- [ ] Test politiky: nový interaktivní nástroj nesmí být automaticky dostupný čtecímu reviewerovi.
- [ ] Test pygame adaptéru s reprodukovatelnou sekvencí akcí a detekcí pádu.
- [ ] Aktualizovat instrukce Coding agenta: kdy použít DOM kontrolu, interakční test, test logiky a ruční ověření.
- [ ] Aktualizovat dokumentaci profilů, závislostí a příkladů použití.
- [ ] Uložit alespoň jeden vzorový report formuláře a jeden pygame report.

## 9. Doporučené pořadí realizace

1. **Formuláře MVP:** Playwright, izolovaný kontext, `browser_interact`, základní akce a assertions, demonstrace opravy vadného formuláře.
2. **Diagnostika a backend:** screenshoty, JS chyby, kontrola requestů, simulované odpovědi a izolovaná integrační data.
3. **Pygame logika:** oddělení stavu a testy rotací, kolizí, usazení a řádků.
4. **Pygame adaptér:** start/stav/akce/krok/stop a reprodukovatelné automatické hraní.
5. **Obrazové ovládání:** až podle potřeby a dostupného modelu.

Hrubý orientační rozsah pro formuláře: jednoduchý prototyp přibližně 2–4 hodiny, odladěná první verze pro Windows/Linux přibližně 1–2 pracovní dny. Skutečný rozsah závisí na prostředí a integraci politik. U pygame závisí náročnost především na oddělení herní logiky od okna; časový odhad upřesnit po výběru konkrétní hry. Tyto odhady nejsou závazný harmonogram.

## Reference

- [Playwright: interakce s formuláři a klávesnicí](https://playwright.dev/python/docs/input)
- [Pygame: fronta událostí a event.post](https://www.pygame.org/docs/ref/event.html)

---

kredit: "zpracovala GPT-6 Astra Střední"

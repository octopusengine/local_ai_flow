# Nápověda James

## Ovládání

Spusťte `python james.py` z kořene projektu se spuštěnou Ollamou.
Hlavní menu reaguje na zvýrazněnou klávesu bez Enter; `q` ukončí James.
Ve výběrových menu používejte šipky nahoru/dolů a Enter. `b` nebo mezerník
vrací z menu a stránek dokumentů zpět. V textových výzvách se řiďte
zobrazenými pokyny.

## Chat

Napište zprávu a stiskněte Enter. Pro začátek se hodí:

- `/hlp` zobrazí ovládání Chatu; `/cmd` lokalizovaný katalog příkazů pro prompty.
- `/bye` vrátí do hlavního menu; `/clr` vyčistí kontext konverzace.
- `/mod MODEL` změní model; `/lng cz` změní jazyk Chatu pro tuto relaci.
- `/bot holly` načte `bot/holly.json` a nahradí aktivní nastavení bota; zachová historii, zdroje a velikost kontextového okna. Samotné `/bot` vypíše dostupné boty. `/task TASK.json` přepne zpět na úlohu.
- Při `/bot NAME` se do kontextu přidá také úvod z `bot/NAME.md`, pokud soubor existuje a není prázdný. Chybějící Markdown se přeskočí.
- V JSON bota lze uvést `"sc": ["brief", "md"]` pro automatické short commands a `"short_commands": {"vlastni": "Instrukce"}` pro vlastní `/vlastni`. Holly obsahuje `/hlasku TÉMA`. Výstup chatu řídí Chat (`chat_reply.txt`), bot nepotřebuje `default_output_file`.
- `/add FILE` přidá projektový textový soubor; `/url URL` čitelný text webové stránky.
- `/ctx` ukáže velikost kontextu; `/src` vypíše připojené zdroje.
- `/voice` nahraje a odešle hlasový dotaz; `/say` přečte poslední odpověď.
- `/cam` pořídí snímek; `/ocr` získá jeho text; `/img` přidá popis obrázku a umožní navazující obrazový chat.
- `/rag NAME` vybere znalostní databázi; `/ask FILTER :: QUESTION` vyhledá relevantní úryvky a odešle otázku.

Zprávu lze začít zkratkou pro prompt, například `/eli5 Vysvětli gravitaci`.
Úplný seznam příkazů a argumentů pro soubory najdete pod `/hlp`.
Projektové soubory se hledají v aktivním projektu; `/proj` ukáže jeho nastavení.

## Cowork

Vyberte agentní profil pro obecnou práci, programování, hardware nebo Nostr.
Profil určuje model a dostupné nástroje. Řiďte se zobrazeným ovládáním relace
a posuzujte požadavky nástrojů, které vyžadují potvrzení.
Plans spravuje projektové plány; Activity je zatím pouze připravená položka.

V nabídce agenta `set project` vyberete šipkami a Enterem adresář `proj*`
z kořenového adresáře aplikace. První položka `new/other` umožní zadat
libovolný adresář uvnitř kořene aplikace, i bez prefixu `proj`: existující
použije, neexistující vytvoří a nastaví. `select model` stejným způsobem vybírá
z nainstalovaných modelů Ollamy. `b` nebo mezerník se vrací beze změny.
Volby platí pouze pro danou Cowork relaci.
U modelů se ověřují schopnosti z Ollamy. Pouze modely s ověřenou podporou
nástrojů mají označení `[ tools ]`; ostatní jsou bez štítku.

Každý profil v `agent/agents.json` má výchozí `"log": true`. Agent průběžně
připojuje čitelný text bez terminálových barev do `log.txt` v pracovním adresáři
aktivní relace. Zachovává se průběžný přepis terminálu. Navíc se stručně zapisuje
zadání, nastavení modelu na začátku běhu nebo při změně, časy kroků, chyby
a závěrečný souhrn. U odpovědí včetně vision jsou počty vstupních a výstupních
tokenů a rychlost generování tokenů/s podle metrik Ollamy; chybějící údaje jsou
označené unavailable. Rychlost nezahrnuje načítání modelu ani zpracování vstupu.
Jednotlivé fragmenty nemají vlastní diagnostické bloky. Obrázková data se nelogují.
Pro vypnutí nastavte u příslušného profilu `"log": false` a spusťte novou relaci.
CLI agent používá přepínač `log` v `cli_agent.json`.

## Flow

Šipkami vyberte kategorii a flow, Enter jej spustí.
Klávesa `i` v seznamu zobrazí obsah vybraného flow před spuštěním.
Kategorie zahrnují Test, Models, Single, Code, Batch, Media, MCP a rag_wiki.
Flows mohou měnit aktivní projekt nebo zapisovat výstupy; zkontrolujte jejich kroky.

## Database a RAG

Database vypisuje uložené úlohy a odpovědi, otevírá záznamy podle ID,
filtruje je a umožňuje hodnocení i mazání. Akci vyberte šipkami a Enter.
Monthly filtruje kalendářní měsíc; Last week zahrnuje dnešek a šest předchozích dní.

RAG spravuje profily lokálních znalostních databází a načítání zdrojů.
Vytvořenou databázi připojte v Chatu pomocí `/rag NAME`; `/rag off` ji odpojí.

## Web v Coding session

Vývoj, kontroly, screenshoty i následné úpravy probíhají standardně skrytě.
Viditelný prohlížeč agent otevře pouze na výslovnou žádost uživatele,
po dokončení úprav a kontrol. Samotné zadání vytvořit nebo vylepšit web
viditelný prohlížeč nevyžaduje.

Například: „Vytvoř web, zkontroluj ho, ulož browser.png a hotový web nech
otevřený v prohlížeči.“ Coding profil má nástroje `serve_project`,
`browser_test`, `browser_screenshot` a `browser_open`. Screenshot se ukládá
do aktivního projektu; `inspect_image` ho může zpracovat pomocí vision modelu.
Snímání potřebuje nainstalovaný Edge, Chrome nebo Chromium a zachycuje jeden
výřez stránky (výchozí okno 1280 × 720, nastavitelné width/height).

Viditelná karta zůstane otevřená i po návratu z Coding session do menu.
Lokální server běží jen do ukončení Jamese. Nástroje přijímají pouze URL
serveru aktivního projektu spuštěného přes `serve_project`; ten obsluhuje
statické soubory, nespouští Vite/Next.js. Platí nastavená pravidla potvrzování
spouštění; režim observe otevření prohlížeče ani zápis screenshotu nepovoluje.

## MCP

Vyberte Base, Hardware nebo Nostr pro přehled služeb a jejich konfigurace.
Volitelné moduly potřebují vlastní závislosti a nastavení. U neúplného modulu
James vypíše chybějící soubory. Akce hardwaru a Nostr se řídí nastavenými
pravidly nástrojů.

## Setup a další informace

V Setup vyberte aktivní projekt a jazyk. `cz` zvolí českou nápovědu a About;
ostatní jazyky používají anglické verze. Chatový `/lng` mění jen aktuální
relaci Chatu. Ollama zobrazí společná nastavení modelů.

- `james/james.json`: nastavení menu.
- `james/chat_cmd.json`: výchozí nastavení Chatu, dostupné přes Setup → james_chat.
- `james/james_flows.json`: seznamy flows.
- `agent/agents.json`: profily Cowork, dostupné přes Setup → agents.
- `lib/wrapp_md.json`: barvy Markdownu.

About obsahuje stručné představení projektu a verze knihoven.
Podrobnosti najdete v `james/README.md` a `james/chat_cmd.md`.

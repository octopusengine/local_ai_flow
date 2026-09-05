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

# Cowork – návrh budoucí spolupráce agentů

Cowork může být pracovní vrstva nad Chatem: uživatel zadá cíl, James jej rozloží na menší kroky, u každého ukáže stav a podle potřeby zapojí lokální nástroje, RAG nebo MCP služby. Nejde o další chatové okno, ale o dohledatelný pracovní plán, který umí sbírat podklady a vracet jeden ověřitelný výsledek.

## Co by Cowork mohl dělat

- **Plánovat práci:** z volného zadání vytvoří checklist kroků, jejich vstupy, očekávané výstupy a závislosti.
- **Rozdělovat role:** například výzkumník najde podklady, analytik je zkontroluje, autor připraví výstup a revizor jej ověří.
- **Udržovat pracovní kontext:** společný kontext bude krátký a strukturovaný; rozsáhlé podklady zůstanou v souborech projektu nebo v RAG databázi.
- **Ukazovat průběh:** pro každý krok stav `čeká`, `běží`, `hotovo`, `potřebuje rozhodnutí` nebo `chyba`.
- **Vytvářet artefakty:** výsledkem může být Markdown zpráva, tabulka, kód, soubor v projektu nebo záznam v databázi úloh.

## Napojení na Tools, RAG a MCP

- **Tools:** Cowork použije `cli_tool.py` pro malé lokální úkony, například datum, síťový test, práci se soubory nebo předpřipravené kontexty. Každé volání se zaznamená u kroku, který jej vyvolal.
- **RAG:** před řešením věcného dotazu může Cowork vyhledat relevantní lokální zdroje v aktivní znalostní databázi. Do výsledku přidá seznam použitých dokumentů a otevřeně označí, když podklady chybí.
- **MCP:** MCP služby se hodí pro řízený přístup k externím nebo lokálním schopnostem. Cowork by měl před spuštěním zobrazit službu, parametry a očekávaný dopad; akce měnící data vyžadují potvrzení uživatele.

## Jednoduchý pracovní tok

1. Uživatel zadá cíl, například „Připrav přehled problémů z OCR účtenek a navrhni další kroky.“
2. Cowork vytvoří plán a nabídne jej k potvrzení nebo úpravě.
3. Vybrané kroky si načtou soubory, OCR výsledky nebo RAG kontext.
4. Nástrojové a MCP kroky se provedou s viditelným logem a návratovým stavem.
5. Revizní krok zkontroluje výsledek proti zadání a uloží závěrečný souhrn do projektu.

## Bezpečné hranice

- Cowork nespouští síťové, MCP ani souborově měnící akce bez jasného kroku v plánu.
- Každý krok uvádí použité vstupy, vytvořené soubory a případné chyby.
- Při nejistotě se zastaví ve stavu `potřebuje rozhodnutí`; nenahrazuje chybějící požadavek domněnkou.
- Citlivé hodnoty z konfigurací a logů se neukládají do sdíleného kontextu.

## Budoucí checklist

- [ ] Navrhnout formát `cowork_plan.json` pro cíl, kroky, závislosti, stav a výsledné artefakty.
- [ ] Přidat Cowork menu s přehledem plánů aktivního projektu.
- [ ] Implementovat vytvoření plánu z chatu a ruční potvrzení před spuštěním.
- [ ] Přidat vykonávač bezpečných lokálních kroků přes `cli_tool.py` a `runner.py`.
- [ ] Doplnit RAG krok, který uloží použité zdroje a jejich krátké výňatky.
- [ ] Doplnit MCP krok s náhledem parametrů, potvrzením změnových operací a logem odpovědi.
- [ ] Ukládat stav kroků a závěrečné shrnutí do databáze úloh nebo do souboru projektu.
- [ ] Přidat obnovu přerušeného plánu a přehled chybových kroků.
- [ ] Připravit testovací plán pro oprávnění, selhání nástrojů a opakované spuštění.

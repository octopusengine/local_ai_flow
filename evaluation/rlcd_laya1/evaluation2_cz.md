# Vyhodnocení laya, běh 2: anglický checkpoint na devíti anglických ticketech

Srovnání dvou běhů nad stejnými devíti anglickými tickety (`ticket1.md` až `ticket9.md`):

- **Běh A:** checkpoint `multilingual`, původní znění otázek.
- **Běh B:** checkpoint `english`, `question.json` se zněním v2.

Původní samostatné vyhodnocení běhu A (anglicky) je v souboru `evaluation2_multilingual_en.md`.

## Shrnutí

Běh B vychází výrazně lépe, hlavně u naléhavosti a oddělení. **Zlepšení ale nejde jednoznačně připsat modelu**, protože se změnily dvě věci najednou (checkpoint i znění otázek) a nové znění otázek jsem psal se znalostí testovacích ticketů (viz „Co srovnání zkresluje"). Berte výsledky jako slibné, ne jako potvrzené.

| | A: multilingual + původní otázky | **B: english + otázky v2** |
|---|---|---|
| oddělení, správně | 6 / 9 (67 %) | **8 / 9 (89 %)** |
| naléhavost, Spearman | 0,63 | **0,90** |
| naléhavost, správně seřazené dvojice | 22 / 27 (81 %) | **26 / 27 (96 %)** |
| naléhavost, střední absolutní chyba (škála 0–2) | 0,69 (konstanta 1: 0,67) | **0,41** (konstanta 1: 0,67) |
| naléhavost, rozsah předpovědí | 1,08–1,51 | **0,52–1,78** |
| riziko odchodu, správně při 0,5 | 7 / 9 (78 %) | 7 / 9 (78 %) |
| riziko odchodu, AUROC | 0,94 | 0,94 |
| medián času na ticket | 0,61 s | 1,86 s |

## Nastavení a předpoklady

- **Vstup:** devět anglických ticketů, stejných v obou během. Výsledky běhu B jsou z JSONů, které program uložil vedle ticketů (`ticket1.json` až `ticket9.json`), výsledky běhu A z konzolového výpisu.
- **Správné odpovědi:** moje vlastní hodnocení z doby, kdy jsem tickety psal, ne nezávislý benchmark. Naléhavost: 0 = není naléhavé, 1 = brzy, 2 = kritické.
- **Vzorek:** devět ticketů. Všechna procenta jsou ilustrativní, jediný přehozený ticket posune přesnost o 11 bodů.
- **Práh** pro riziko odchodu je 0,5, oddělení se hodnotí podle nejvyšší volby.
- **Routing** v JSONech potvrzuje vynucení checkpointu (`explicit model='english'`).

## Výsledky běhu B po ticketech

`oček.` je moje hodnocení, `předp.` výstup modelu. U oddělení je v závorce pravděpodobnost zvolené volby.

| # | Ticket | Oddělení oček. / předp. (p) | Naléhavost oček. / předp. | Odchod oček. / předp. | Čas |
|---|---|---|---|---|---|
| 1 | Dvojitá platba, hrozí zrušením | billing / billing (0,976) ✅ | 2 / 1,25 | ano / 0,858 ✅ | 1,33 s |
| 2 | Nefunguje přihlášení (HTTP 500) | technical / technical (0,788) ✅ | 2 / 1,78 | ne / 0,000 ✅ | 1,67 s |
| 3 | Ceník pro osm poboček | sales / **billing** (0,380; sales 0,368) ❌ | 0 / 0,78 | ne / **0,560** ❌ | 2,95 s |
| 4 | Kopie loňských faktur | billing / billing (0,978) ✅ | 0 / 0,83 | ne / 0,018 ✅ | 1,77 s |
| 5 | Špatný formát dat v CSV exportu | technical / technical (0,656) ✅ | 1 / 0,79 | ne / 0,000 ✅ | 1,88 s |
| 6 | Poděkování a nápad na funkci | other / other (0,456) ✅ | 0 / 0,52 | ne / 0,000 ✅ | 1,73 s |
| 7 | Zdražení o 25 %, zvažují jiné dodavatele | billing / billing (0,744) ✅ | 1 / 0,96 | ano / **0,023** ❌ | 2,06 s |
| 8 | Třetí výpadek, hrozí ukončením smlouvy | technical / technical (0,841) ✅ | 2 / 1,77 | ano / 0,988 ✅ | 2,12 s |
| 9 | Přechod na vyšší tarif | sales / sales (0,444) ✅ | 1 / 0,89 | ne / 0,023 ✅ | 1,86 s |

## Oddělení

- **8 z 9 správně.** Jediná chyba je ticket 3, kde vyšlo billing 0,380 proti sales 0,368, tedy téměř remíza.
- **Oproti běhu A:** ticket 6 (poděkování) je teď správně `other` (dřív `technical`) a ticket 9 správně `sales` (dřív `other`). Oddělení `sales` se poprvé objevilo mezi předpověďmi.
- **Pravděpodobnosti jsou informativní.** Správné odpovědi mají nejvyšší pravděpodobnost 0,66 až 0,98, kromě ticketů 6 (0,456) a 9 (0,444). Pravidlo „nejvyšší pravděpodobnost ≥ 0,6" by zpracovalo automaticky šest ticketů (všechny správně) a tři poslalo člověku (ticket 3 špatně, 6 a 9 správně). Práh jsem zvolil po pohledu na data, takže je to jen ilustrace.

## Naléhavost

- **Největší zlepšení.** Rozsah předpovědí se zvětšil z 0,43 na 1,26 a střední absolutní chyba (0,41) je konečně lepší než konstantní odpověď 1 (0,67). V běhu A byla stejná jako konstanta.
- **Pořadí je téměř dokonalé.** Průměr podle mého označení: není naléhavé 0,71, brzy 0,88, kritické 1,60. V 26 z 27 dvojic s různým označením dostal naléhavější ticket vyšší skóre.
- **Co nefunguje:**
  - Ticket 1 dostal 1,25 místo kritického (2), i když požaduje vrácení peněz „dnes".
  - Model nerozlišuje „není naléhavé" od „brzy": tickety 3, 4 a 6 (označeny 0) mají 0,52 až 0,83, tickety 5, 7 a 9 (označeny 1) mají 0,79 až 0,96. Zaokrouhlení na nejbližší úroveň sedí jen u 5 z 9 ticketů.

## Riziko odchodu

- **Beze změny proti běhu A** (7 z 9, AUROC 0,94).
- **Zásahy:** ticket 1 (0,858) a ticket 8 (0,988, dříve 0,770). Pět ze šesti ticketů bez hrozby (2, 4, 5, 6, 9) je pod 0,03.
- **Falešný poplach, ticket 3 (0,560).** Zákazník se zajímá o přechod *k nám* („considering switching to your service"), model ale reaguje na slovo přechod bez ohledu na směr. Je to zčásti chyba mého ticketu. Oproti běhu A (0,644) je to o něco méně, ale pořád nad prahem.
- **Chybějící odchod, ticket 7 (0,023).** Hrozba je jemná („looking at other providers"). Ranking je správně jen o vlásek: ticket 7 (0,0233) je jen o 0,0007 nad nejvyšším čistým negativem (ticket 9, 0,0226). Pořadí je tedy křehké.

## Co srovnání zkresluje

1. **Změnily se dvě věci najednou.** Mezi běhy A a B se změnil checkpoint (`multilingual` → `english`) i znění otázek (původní → v2). Z těchto dvou běhů nelze říct, kolik zlepšení dělá model a kolik lepší formulace.
2. **Znění v2 jsem psal se znalostí testovacích ticketů.** Popisy oddělení a úrovní naléhavosti obsahují formulace, které téměř doslova odpovídají konkrétním ticketům:

   | formulace ve v2 | ticket |
   |---|---|
   | technical: „login problems" | 2 |
   | technical: „data export problems" | 5 |
   | billing: „price or subscription cost questions" | 7 |
   | sales: „plan upgrades and extra users" | 9 |
   | other: „compliments, feedback, feature ideas" | 6 |
   | naléhavost 0: „weeks of time" | 4 |

   Jde o únik testovacích dat do zadání. Osmička z devíti oddělení je proto pravděpodobně optimistická a je to chyba v mém návrhu testu.
3. **Malý vzorek** a moje vlastní označení. Tickety 3 a 7 jsou navíc záměrně či nechtěně nejednoznačné.

## Poznámka k poli `confidence`

Pole `confidence` v JSONu (a dříve `jistota` ve výpisu) **není** pravděpodobnost zvolené odpovědi. Ověřil jsem to na několika hodnotách: u `choice` a `score` je to 1 − normalizovaná entropie rozdělení, u `noul` je to max(p, 1 − p). Proto má ticket 6 „confidence" jen 0,08, přestože `other` je správně (0,456 proti 0,231 druhé volby). Pro filtrování na lidskou kontrolu je proto praktičtější pole `probabilities`. Dřívější úvaha o prahu 0,6 v `evaluation2_multilingual_en.md` se týkala právě tohoto entropického pole a platí jen pro něj.

## Rychlost

- Anglický model (421M parametrů, kontext 512) je asi **třikrát pomalejší** než multilingual (322M): medián 1,86 s proti 0,61 s, poměr na jednotlivých ticketech 2,6 až 3,3.
- Čas roste s délkou textu: nejdelší ticket 3 (154 slov) trval 2,95 s, ostatní 1,33 až 2,12 s.
- **První ticket nebyl pomalejší** (1,33 s je nejrychlejší), takže zahřívací penalizaci nevidíme.
- Načtení modelu v JSONech není. Údaj by bylo potřeba zjistit z konzolového výpisu nebo z `-v`.

## Závěr

- Kombinace `english` + otázky v2 dává nejlepší dosavadní výsledky: oddělení 8 z 9, naléhavost s dobrým pořadím a rozsahem, riziko odchodu na úrovni AUROC 0,94.
- Za cenu asi třikrát delší doby odpovědi (stále do 3 s na CPU).
- Absolutní čísla u naléhavosti a riziko odchodu u jemných hrozeb (ticket 7) ale zůstávají slabá.
- **Nelze zatím říct, jestli za lepším výsledkem stojí checkpoint, nebo znění otázek**, a část zlepšení může být jen přizpůsobení zadání testovacím ticketům.

## Doporučené další kroky

1. **Rozložit vliv obou změn:** spustit tabulku 2×2 (oba checkpointy × obě znění otázek). Pro pohodlné přepínání navrhuji přidat do `cli_laya.py` přepínač `--checkpoint`, teď se checkpoint mění jen v `cli_laya.json`.
2. **Napsat nových devět ticketů**, které znění v2 nezná, a nechat v2 beze změny (slepá testovací sada).
3. **Použít pravděpodobnosti místo `confidence`** pro rozhodnutí, co jde k člověku.
4. Pokud zůstane riziko odchodu u jemných hrozeb slabé, zvážit dotrénování modelu na vlastních datech (laya dodává notebook pro fine-tuning).

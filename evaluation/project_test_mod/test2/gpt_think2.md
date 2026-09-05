# GPT-OSS: porovnání požadavků false, low a high

Vyhodnocení `gpt-oss:latest` z 5. 9. 2026. Zdroje: [nový log](../../project_test_mod/log.txt), [předchozí Windows report](test1_win/README.md) a [archivovaný Windows log](../../project_test_mod/bak1/log_win.txt). Hlavní reference je Windows; linuxové výsledky nemíchám do časových průměrů.

**Explicitní `low` u GPT-OSS v tomto logu funguje: anglická sada dokončila všech šest otázek. `high` u prvních pěti anglických otázek přineslo mnohem delší čekání bez celkového zlepšení správnosti. Poslední anglické Q6 během zpracování doběhlo po 828,1 s; většinu čekání zabralo opakované počítání slov. Nově zahájené české high zatím v tomto snímku finální odpověď nemá.** Předchozí neúspěch Qwenů s `low` se tedy na GPT-OSS obecně nepřenesl.

Snímek načtený pro tento report: **2026-09-05T14:31:09+02:00**, 124655 bajtů, SHA-256 `90a4223982402b6affbfe7273e58985ea91fecdea5d865d3b730ab057e575fb8`. Report nečeká na dokončení posledního požadavku.

## Co lze skutečně srovnávat

`false` níže označuje hodnotu v požadavku, **nikoli prokázané vypnutí přemýšlení**. GPT-OSS podle dokumentace Ollamy boolean ignoruje a používá úrovně `low`, `medium`, `high`. Navíc lokální wrapper při nepravdivém `think` nevypisuje pole `thinking`; chybějící úvahy ve starém logu nejsou důkazem, že model nepřemýšlel. [Ollama – thinking](https://docs.ollama.com/capabilities/thinking)

| Sada / úlohy | Jazyk zadání | think | temperature | repeat_penalty | num_predict / num_ctx | Stav |
|---|---|---|---:|---:|---|---|
| Původní Windows Q1–Q6, ID 520–525 | CZ | false | 0.5 | 1.1 | 2048 / 4096 | 6 odpovědí, Q5 obsahově nedokončená |
| Nové Q1–Q6, ID 538–543 | EN | low | 0.2 | 1.05 | 2048 / 4096 | 6 odpovědí |
| Nové Q1–Q3, ID 544–546 | CZ | low | 0.2 | 1.05 | 2048 / 4096 | 3 odpovědi |
| Nové Q4–Q6, ID 547–549 | CZ | false | 0.5 | 1.1 | 2048 / 4096 | 3 odpovědi; změna konfigurace uprostřed flow |
| Nové Q1–Q2, ID 550–551 | EN | high | 0.1 | 1.05 | 2048 / 4096 | 2 odpovědi |
| Nové Q3–Q5, ID 552–554 | EN | high | 0.1 | 1.05 | 8192 / 16384 | 3 odpovědi; zvýšení limitů uprostřed flow |
| Nové Q6, ID 555, od 14:11:26 | EN | high | 0.1 | 1.05 | 8192 / 16384 | Dokončeno v 14:25:14 |
| Nové Q1 od 14:26:58 | CZ | high | 0.1 | 1.05 | 8192 / 16384 | Ve snímku pouze Thinking; šablona task_base_gptossh.json |

**České flow není kompletní test low. Dokončený český high ani dokončený anglický false zde nemáme.** Anglická Q4 vyžaduje překlad do češtiny a používá `--sc-cz`: hodnotím český překlad, nikoli chybné nedodržení anglického jazyka.

Mění se současně teplota, penalizace, seed a u high také kontext a výstupní limit. Výsledky proto srovnávají konkrétní konfigurace; neizolují kauzální účinek samotného `think`. Dřívější Windows sada a nová sada mohou mít odlišný stav načtení modelu. Přesná verze vah, hardware ani metadata o načítání v těchto podkladech nejsou.

Samostatné soubory v pracovní složce jsou přepisovány dalšími běhy. Aktuální anglické `.md` už obsahují high; nelze je vydávat za odpovědi low. Proto nové výsledky identifikuji především ID v logu. `entropy_gpt_6_en.md` bylo při zahájení analýzy prázdné, nyní obsahuje dokončené high. Úspěšný starší text low zůstal v logu pod ID 543.

## Metodika kvality a rychlosti

Ruční škála odpovídá předchozímu reportu: **R** = relevantnost, pokrytí zadání a forma (0–5); **S** = správnost, u překladu i gramatika a významová věrnost (0–5). Pět znamená bez nalezené podstatné vady, tři správné jádro s významnými vadami, jedna převážně nespolehlivý obsah. Skóruji finální odpovědi, nikoli pracovní návrhy uvnitř Thinking. Rozpracované české high Q1 nemá známku 0, ale „nehodnoceno“; dokončené anglické high Q6 je již zahrnuto.

Čekání = čítač `Ollama response complete` minus čítač `Sending request`. Sloupec „Do začátku Response“ zahrnuje načítání, zpracování vstupu a přemýšlení až k přechodu na finální text. **Není to čistá délka přemýšlení.** Q1 může obsahovat desítky sekund zavádění do RAM/VRAM; souhrny bez Q1 uvádím zvlášť.

Odhad tokenů finálního textu: **CZ znaky / 3, EN znaky / 4**; u anglické sady Q4 používám CZ přepočet. Počítám znaky včetně mezer, kódu a Markdownu, s LF a bez krajních mezer. Protokol a Thinking do délky finální odpovědi nepatří. Tok/s = součet odhadnutých tokenů / součet celého čekání. Jde o hrubý pracovní přepočet, nikoli tokenizaci skutečným tokenizerem. Při shodných 3 znacích/token by anglické texty mimo Q4 vyšly o třetinu výše; mezi jazyky proto nedělám přesný výkonnostní žebříček.

Vedle užitečného výstupu uvádím i orientační tok všech **viditelných** tokenů: finální text plus anglické Thinking přepočtené /4. To lépe ukazuje práci navíc u high, ale opět to nejsou skutečné eval tokeny. U false tyto úvahy nejsou v logu, takže takový součet nelze srovnat. Přesné tok/s vyžadují `eval_count / eval_duration × 10^9`, načítání pak `load_duration`; tato metadata chybí. [Ollama – usage](https://docs.ollama.com/api/usage)

## Předchozí false – česká Windows reference

Přejímám známky a měření ze staršího reportu; odhad tok/s je stále CZ /3. Referenční sada začala v 11:24:01; při porovnání nejde o shodné seedy s novými běhy.

| Úloha / původní odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Hlavní zjištění |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](test1_win/explain_gpt_1.md) | 4 | 3 | 55,0 s | ≈ 3,0 | Správné jádro, nesrozumitelná závěrečná analogie. |
| [Q2 – TCP/UDP](test1_win/compare_gpt_2.md) | 5 | 3 | 106,3 s | ≈ 5,8 | Přehledná tabulka, chybná formulace o vyhýbání se retransmisím. |
| [Q3 – HTTP 404](test1_win/diagnose_gpt_3.md) | 3 | 2 | 139,3 s | ≈ 5,9 | Správné dílčí kroky, ale chybné endpointy a záměna 404 za neotevřený port. |
| [Q4 – překlad](test1_win/translate_gpt_4.md) | 5 | 3 | 155,3 s | ≈ 0,4 | „Ne zohlednili“, vypuštěná chyba kalibrace. |
| [Q5 – králové](test1_win/kings_gpt_5.md) | 2 | 1 | 293,7 s | ≈ 1,0 | Neúplná tabulka, „Václav II (Charles V)“ v 16. století. |
| [Q6 – entropie](test1_win/entropy_gpt_6.md) | 4 | 4 | 169,0 s | ≈ 1,3 | Správný vzorec a základní rozlišení výsledku od hypotézy. |

**R 3,8/5, S 2,7/5; celkem 918,6 s, průměr 153,1 s; ≈ 2,4 tok/s finálního výstupu.**

## Low – anglická sada Q1–Q6

Všech šest požadavků dokončeno. Celé flow trvalo **365,4 s** včetně režie. Thinking jsou krátké poznámky; výjimkou je překlad, kde se v úvaze objeví návrh české věty.

| Úloha / ID | R / 5 | S / 5 | Čekání celkem | Do začátku Response | Odhad tok/s finálního textu | Posouzení |
|---|---:|---:|---:|---:|---:|---|
| Q1 / 538 | 5 | 3 | 65,2 s | 49,7 s | ≈ 2,3 | Správné jádro Rayleighova rozptylu, ale mlha osvětlená baterkou není obecně modrá; směšuje molekulární rozptyl s kapkami a prachem. |
| Q2 / 539 | 5 | 4 | 74,5 s | 6,0 s | ≈ 8,0 | Přehledné porovnání, správný závěr, že UDP není vždy rychlejší. Absolutní garance doručení TCP a pevně uvedených 20 bajtů bez zmínky o options jsou zjednodušení. |
| Q3 / 540 | 3 | 1 | 92,0 s | 7,2 s | ≈ 6,6 | Chybné testy HEAD na `/api`, `/api/embeddings` a `/api/pull?name=…`, vymyšlené `/api/models`. Postup často diagnostikuje vlastní nesprávnou metodu či trasu. |
| Q4 / 541 | 5 | 3 | 27,4 s | 17,6 s | ≈ 2,6 | Zachovává chybu kalibrace a podmínku, ale „ne zohlednili“ je pravopisná chyba a závěrečné „podpoří“ oslabuje časový pohled originálu. |
| Q5 / 542 | 4 | 2 | 63,2 s | 9,6 s | ≈ 6,9 | Svatý Václav z 10. století byl kníže, ne český král. Chybná římská data Karla IV.; některé údaje o Zikmundovi a kulturním významu Karla jsou použitelné. |
| Q6 / 543 | 5 | 4 | 26,4 s | 6,8 s | ≈ 6,7 | Správný úplný vzorec a rozlišení plošného výsledku od širší holografické hypotézy. Formulace o univerzálním kódování na hranici je zjednodušená. |

Low zde přináší rychlé použitelné odpovědi na TCP/UDP a entropii. Diagnostika HTTP 404 a historická fakta však zůstávají nespolehlivé. Oproti high je angličtina většinou stejně čitelná bez rozsáhlého přepracovávání návrhů.

## Česká sada – Q1–Q3 low, Q4–Q6 false

Celé flow má **809,2 s**, ale jeho společný průměr nelze označit za výkon low. Od Q4 log výslovně uvádí zpět false, teplotu 0.5 a penalizaci 1.1.

### Q1–Q3: low

| Úloha / ID | R / 5 | S / 5 | Čekání celkem | Do začátku Response | Odhad tok/s finálního textu | Posouzení |
|---|---:|---:|---:|---:|---:|---|
| Q1 / 544 | 4 | 3 | 30,9 s | 7,9 s | ≈ 5,5 | Rozptyl a vlnové délky jsou vysvětlené, ale příklad s přeléváním barevného světla přes kapky vody je fyzikálně i jazykově vadný. |
| Q2 / 545 | 4 | 3 | 110,8 s | 7,0 s | ≈ 7,2 | Základní srovnání funguje. Přidaná bezpečnostní část zaměňuje spolehlivost s odolností proti útokům; rychlost je formulována příliš obecně. |
| Q3 / 546 | 3 | 1 | 174,0 s | 10,4 s | ≈ 6,8 | Vymýšlí seznam endpointů na GET `/api` a informace o chat API na GET `/api/chat`. Zaměňuje 404 za nedostupnost serveru; správné `/api/tags` a Python POST chyby nevyvažují. |

Pro stejné Q1–Q3 měla stará false reference R 4,0 a S 2,7; nové low má R 3,7 a S 2,3. Čekání je téměř stejné (300,6 s proti 315,7 s). Český low tedy v této trojici neprokázal zlepšení: zrychlení Q1 vyvažuje delší a horší diagnostika Q3.

### Q4–Q6: opět false

| Úloha / ID | R / 5 | S / 5 | Čekání celkem | Do začátku Response | Odhad tok/s finálního textu | Posouzení |
|---|---:|---:|---:|---:|---:|---|
| Q4 / 547 | 5 | 3 | 104,3 s | nezaznamenáno | ≈ 0,7 | „Neohodnotili možnost“ je nepřirozená náhrada nezohlednění; chyba kalibrace zůstala zachována. Význam je čitelný, časová návaznost méně přesná. |
| Q5 / 548 | 4 | 2 | 234,1 s | nezaznamenáno | ≈ 1,6 | Tři reální králové a většina českých dat jsou lepší než v původním běhu. Zůstávají chybná sloučená římská data a nepodložené založení Knihovny a Akademie Rudolfem; „Středočeské království“ je nesmysl. |
| Q6 / 549 | 4 | 3 | 138,6 s | nezaznamenáno | ≈ 1,6 | Správný vztah a vzorec, ale „entropie se zmenšuje na dvě rozměry“ je zavádějící. Výsledek a hypotézu rozlišuje, formulace jsou neobratné. |

Tuto trojici nelze použít jako doklad úspěšného českého low. Q5 se proti starší false odpovědi zlepšila z 1 na 2 body, ale stále obsahuje věcné chyby. Jde o další ukázku variability mezi jednotlivými generováními.

## High – dokončená anglická sada Q1–Q6

Od Q3 se zvýšil výstupní limit z 2048 na 8192 a kontext z 4096 na 16384. Tím se mění nejen prostor pro uvažování, ale potenciálně i nároky na paměť a načítání. Ani větší limit sám nezaručuje kvalitnější odpověď.

| Úloha / ID | R / 5 | S / 5 | Čekání celkem | Do začátku Response | Odhad tok/s finálního textu | Posouzení |
|---|---:|---:|---:|---:|---:|---|
| Q1 / 550 | 5 | 3 | 190,0 s | 172,8 s | ≈ 0,7 | Správné jádro rozptylu; pokus s baterkou a čistou sklenicí vody a modrým prošlým světlem je chybný. Delší přemýšlení tento problém neodstranilo. |
| Q2 / 551 | 5 | 4 | 175,1 s | 79,0 s | ≈ 4,7 | Dobré porovnání a vysvětlení závislosti rychlosti na scénáři; stále příliš absolutní garance doručení a účinku řízení zahlcení. Obsahově podobná úroveň jako low. |
| Q3 / 552 | 3 | 2 | 195,5 s | 96,1 s | ≈ 3,2 | Lepší výběr tras než low a skutečný POST, ale HEAD `/api/generate` není validní test generování. Z 404 bez těla nelze automaticky určit host, endpoint ani model. |
| Q4 / 553 | 5 | 3 | 226,7 s | 216,1 s | ≈ 0,3 | Správně píše „nezohlednili“, ale vypouští chybu z „přehlédnutou kalibrací“; finální „podpoří“ opět posouvá časový vztah. Přes delší čekání není překlad zřetelně lepší. |
| Q5 / 554 | 4 | 1 | 343,3 s | 302,7 s | ≈ 0,8 | Rudolf II. zemřel před začátkem třicetileté války, přesto mu připisuje účast; nesprávný konec české vlády. Ferdinand I. má chybně začátek české vlády 1521, římské tituly jsou sloučeny. Karel IV. nezaložil celý Pražský hrad. |
| Q6 / 555 | 5 | 4 | 828,1 s | 802,2 s | ≈ 0,2 | Správný úplný vzorec a rozlišení plošného zákona od hypotézy. Angličtina místy postrádá členy, ale finální fyzikální smysl je přijatelný. Přes 13 minut čekání nepřineslo vyšší známku než low. |

**Pro stejné anglické Q1–Q5** má low R 4,4 / S 2,6 a high R 4,4 / S 2,6. Shodný průměr skrývá malý posun diagnostiky nahoru a historie dolů. High tedy zde nepřineslo lepší průměrnou správnost, přestože čekání výrazně vzrostlo. Nejde o statistický závěr z opakovaných měření.

Nejvýmluvnější je Q4: low čekání **27,4 s**, high **226,7 s** (asi 8,3×). High se k finálnímu textu dostalo až po **216,1 s** a samotné závěrečné vypisování trvalo přibližně 10,6 s. Překlad přesto zůstal na 3/5. Obdobně high Q5 strávilo **302,7 s před Response** a pak odevzdalo zásadně chybnou historii.

### Poslední anglické Q6: přes 13 minut kvůli krátkému odstavci

Požadavek začal v **14:11:26**, Thinking se objevilo v **14:11:31**, Response až v **14:24:48** a dokončení v **14:25:14** (ID 555). Čítače dávají **828,1 s celkem**, **802,2 s před Response** a **25,9 s pro následný výpis finální odpovědi**. Jde tedy přibližně o 97 % čekání před finálním textem; tato fáze zahrnuje i zpracování vstupu a případné načítání.

Log potvrzuje uživatelovo pozorování: model opakovaně přepisuje téměř hotový odstavec a přepočítává slova, přestože zadání požaduje **přibližně** 100. V pracovním návrhu dokonce odstraní slovo tak, že vznikne „an result“. Finální verze už má „an established result“, zůstávají však jiné chybějící členy. Návrhy v Thinking nehodnotím jako finální odpověď.

Low tuto otázku dokončilo za **26,4 s**, high za **828,1 s**, tedy asi **31,4× pomaleji**. Obě finální odpovědi mají S **4/5**. Zde delší přemýšlení nepřineslo měřitelné zlepšení podle použité rubriky. Celé anglické high flow skončilo úspěšně za **1 975,7 s** včetně režie.

Od **14:26:58** běží ještě české high Q1 s novou šablonou. V načteném snímku jsou pouze úvahy, opět s počítáním slov; neobsahuje finální Response ani konečný čas. Tuto otázku ponechávám mimo skóre a rychlostní průměry. Report na dokončení navazujících běhů nečeká.

## Přehled rychlosti a tokenů

Souhrny zahrnují pouze dokončené odpovědi ve jmenovaném rozsahu. Přepočet EN /4 a CZ /3 je orientační. „Včetně Thinking“ používá pouze úvahy viditelné v logu; není to srovnatelný údaj pro false. Není také důvodem hodnotit dlouhé přemýšlení jako užitečný výstup.

| Konfigurace a rozsah | Znaky finálních odpovědí | Odhad finálních tokenů | Čekání celkem | Průměr / otázka | Finální tok/s | Tok/s včetně viditelného Thinking |
|---|---:|---:|---:|---:|---:|---:|
| Původní false CZ Q1–Q6 | 6 569 | ≈ 2 190 | 918,6 s | 153,1 s | ≈ 2,4 | nezjištěno |
| low EN Q1–Q6 | 8077 | ≈ 2037 | 348,7 s | 58,1 s | ≈ 5,8 | ≈ 6,3 |
| low CZ Q1–Q3 | 6425 | ≈ 2142 | 315,7 s | 105,2 s | ≈ 6,8 | ≈ 7,0 |
| nové false CZ Q4–Q6 | 1983 | ≈ 661 | 477,0 s | 159,0 s | ≈ 1,4 | nezjištěno |
| high EN Q1–Q6 | 8326 | ≈ 2099 | 1958,7 s | 326,4 s | ≈ 1,1 | ≈ 6,9 |

Po připočtení viditelného Thinking vycházejí oba anglické režimy podobně (**low ≈ 6,3, high ≈ 6,9 tok/s**), zatímco rychlost doručeného finálního textu klesá z **≈ 5,8 na ≈ 1,1 tok/s**. To podporuje vysvětlení, že high tráví podstatně více práce úvahami, nikoli že by stroj nutně generoval každý token pomaleji. Jde stále o odhad z textu a celkového času.

### Porovnání stejných otázek

| Srovnání | Low | Druhá konfigurace | Interpretace |
|---|---:|---:|---|
| EN Q1–Q6: celá dokončená sada | 348,7 s | high 1 958,7 s | High asi 5,6× pomalejší; obě sady S 2,8/5. |
| EN Q2–Q6: celá sada bez Q1 | 283,5 s | high 1 768,7 s | High asi 6,2× pomalejší; rozdíl přetrvává bez první otázky. |
| EN Q1–Q5: celkové čekání | 322,3 s | high 1130,6 s | High je přibližně 3,5× pomalejší při stejné průměrné správnosti. |
| EN Q2–Q5: bez první otázky | 257,1 s | high 940,6 s | Také bez Q1 zůstává high výrazně pomalejší; první načítání rozdíl nevysvětluje. |
| CZ Q1–Q3: celkové čekání | 315,7 s | původní false 300,6 s | Low zde nezrychlilo celek ani nezlepšilo průměrnou správnost. |
| CZ Q2–Q3: bez první otázky | 284,8 s | původní false 245,6 s | Rozdíl není pouze otázkou možného načítání v Q1. |

## Praktický závěr a kontrolní opora

Pro GPT-OSS bych z těchto výsledků preferoval **explicitní low pro běžné odpovědi**, nikoli high jako univerzální zlepšení. Nejlépe zde dopadly anglické TCP/UDP a entropie. Česká kvalita stále vyžaduje kontrolu a samotná změna režimu neopravila API znalosti ani historii. Původní false lze ponechat jako historickou referenci, nikoli jako doložený režim bez přemýšlení.

U dalšího experimentu změnit jen jednu věc, ponechat stejné limity a předem určené seedy. U Q1/Q6 nahradit počet slov formulací „stručně v jednom odstavci“; nechávat běžet stále vyšší rozpočet pro dosažení přesně 100 slov v této sadě nedává praktický smysl. Logovat `done_reason`, `eval_count`, `eval_duration`, `load_duration` a oddělené délky Thinking/Response by umožnilo přesnější závěr.

Kontrolní opora: HTTP metoda je součástí správného API volání, HEAD na generovací trase nenahrazuje POST a model může vracet 404. [Ollama generate](https://docs.ollama.com/api/generate), [chyby](https://docs.ollama.com/api/errors). TCP poskytuje uspořádaný proud s retransmisemi, ne absolutní záruku doručení za jakékoli situace. [RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html). Základní fyzikální a historické reference jsou uvedeny také v [předchozím reportu](test1_win/README.md).

## Souhrn hodnocení

Řádky s různými otázkami nejsou přímý žebříček. Low a high EN nyní pokrývají stejné Q1–Q6; celé high má stejné R 4,5 a S 2,8, ale přibližně 5,6× delší čekání. Nedokončené české high Q1 zůstává mimo průměry.

| Konfigurace | Rozsah finálních odpovědí | Relevantnost / 5 | Správnost / 5 | Čekání celkem | Odhad finálních tok/s | Verdikt |
|---|---|---:|---:|---:|---:|---|
| Původní false CZ | Q1–Q6 | 3,8 | 2,7 | 918,6 s | ≈ 2,4 | Historická reference; false neprokazuje vypnuté přemýšlení. |
| low EN Q1–Q6 | 6 odpovědí | 4,5 | 2,8 | 348,7 s | ≈ 5,8 | Nejpraktičtější dokončená nová sada; slabé API a historie. |
| low CZ Q1–Q3 | 3 odpovědi | 3,7 | 2,3 | 315,7 s | ≈ 6,8 | Pouze tři otázky; proti stejným otázkám false bez zlepšení. |
| nové false CZ Q4–Q6 | 3 odpovědi | 4,3 | 2,7 | 477,0 s | ≈ 1,4 | Není součást českého low; další samostatný vzorek. |
| high EN Q1–Q6 | 6 odpovědí | 4,5 | 2,8 | 1958,7 s | ≈ 1,1 | Stejná správnost jako low na celé sadě, přibližně 5,6× delší čekání. |
| high CZ Q1 | Zatím žádná | — | — | neukončeno | — | Nový běh od 14:26:58; v načteném snímku pouze Thinking. |
| high CZ / false EN | Chybí dokončené testy | — | — | — | — | Nelze vyhodnotit. |

---

kredit: "zpracovala GPT-6 Astra Střední"

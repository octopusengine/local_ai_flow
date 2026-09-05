# Test modelů na Windows – test1_win

Vyhodnocení [logu](log.txt) z **5. 9. 2026, 10:22–12:07**. Hodnoceno je šest dokončených českých sad po šesti otázkách, celkem **36 odpovědí**. Stejnou metodiku používá [linuxový report](../test1_lx/README.md).

**Qwen 3.8 dosáhl nejvyšší správnosti, zejména u překladu a diagnostiky HTTP 404, ale byl také nejpomalejší. Qwen 3.5 4B dokončil sadu nejrychleji, s nejnižší správností. Gemma je druhá nejrychlejší, ale její překlad i historie jsou výrazně chybné. Historie českých králů selhala u všech šesti modelů.** Ani vyšší čas nebo rozsáhlejší odpověď zde nezaručovaly kvalitu. Výsledky popisují konkrétní běhy, nikoli obecné schopnosti modelů.

## Podklady a průběh

| Model podle logu | Začátek flow | ID úloh | Podklad |
|---|---|---|---|
| `qwen3.5:4b` (`q34`) | 10:22:32 | 502–507 | Všech šest odpovědí v logu; samostatné výsledky ve složce nejsou. |
| `qwen3.5:latest` (`q35`) | 10:29:46 | 508–513 | Všech šest odpovědí v logu; samostatné výsledky ve složce nejsou. |
| `qwen3.8:latest` (`q38`) | 10:50:18 | 514–519 | Log a šest `.md`. |
| `gpt-oss:latest` (`gpt`) | 11:24:01 | 520–525 | Log a šest `.md`, české flow. |
| `ornith:9b` (`orn9`) | 11:40:14 | 526–531 | Log a šest `.md`, české flow. |
| `gemma4:latest` (`g4`) | 11:59:18 | 532–537 | Log a šest `.md`, české flow. |

Původní odpovědi ve všech **24 přiložených `.md` odpovídají textu v logu**. Mají dvouřádkové záhlaví s modelem, parametry, časem a odhadem tokenů/s; text pod oddělovačem zůstává beze změny. Záhlaví není započítáno do délky ani odhadu tokenů. Chybějící soubory pro Qwen 4B a Qwen latest neznamenají chybějící odpovědi; jsou vyhodnoceny přímo z logu. Nové kopie odpovědí nevytvářím.

Pokus s anglickým GPT flow od 11:22:33 obsahuje odeslané Q1, ale žádnou dokončenou odpověď ani vysvětlení ukončení. Do srovnání nepatří.

U Q5 modelů Qwen latest a GPT končí odpověď uprostřed textu, přestože log hlásí `Ollama response complete`. Hodnotím skutečně dodaný neúplný obsah. Záznam neobsahuje důvod zastavení generování; dosažení limitu tokenů je možná příčina, nikoli prokázaná skutečnost.

## Nastavení a měření rychlosti

| Parametr | Hodnota |
|---|---|
| Šablona / úloha | `task_base.json` / `prompt` |
| Jazyk hodnocených sad | Čeština, `--sc-cz` |
| `temperature` / `repeat_penalty` | `0.5` / `1.1` |
| `num_predict` / `num_ctx` | `2048` / `4096` |
| `think` | `false` v požadavku |
| Seed | V souhrnu `0`; následně každý požadavek vypisuje jiné konkrétní `Seed:`. |

Windows log má u `Sending request` již **+2,0 až +2,1 s**. Proto v hodnocení používám rozdíl **čas u `Ollama response complete` minus čas u `Sending request`**. Například první odpověď 4B: 30,0 − 2,0 = **28,0 s**. Odečítám tak přípravu před požadavkem, nikoli případné načítání modelu na serveru.

| Model | Součet čítačů při dokončení | Příprava před odesláním | Čekání na odpovědi použité v hodnocení | Celé flow včetně režie |
|---|---:|---:|---:|---:|
| Qwen 4B | 352,0 s | 12,2 s | **339,8 s** | 356,3 s |
| Qwen latest | 871,0 s | 12,4 s | **858,6 s** | 875,3 s |
| Qwen 3.8 | 1 899,1 s | 12,4 s | **1 886,7 s** | 1 904,0 s |
| GPT-OSS | 931,0 s | 12,4 s | **918,6 s** | 935,5 s |
| Ornith | 613,0 s | 12,5 s | **600,5 s** | 617,5 s |
| Gemma | 494,7 s | 12,4 s | **482,3 s** | 499,1 s |

Jde o dobu čekání do dokončení, **nikoli tokeny/s ani čas do prvního tokenu**. Log neuvádí hardware, kvantizaci, digest modelů, verzi serveru, počty tokenů nebo stav načtení modelu. Z `latest` neodvozuji velikost či totožnost vah. Z rozdílů proti Linuxu nelze vyvozovat vliv operačního systému: chybí kontrola hardwaru, výstupních délek a shodných verzí modelů. Ani zde nemáme opakované kompletní běhy se shodným seedem.

### První odpověď a načítání modelu

**Q1 (modrá obloha) může obsahovat zavádění modelu do RAM, případně VRAM, i v délce desítek sekund.** Odečtení přípravy CLI výše tuto serverovou dobu neodstraní. Bez `load_duration` a informace o předchozím načtení nelze určit její podíl; rozdíly Q1 proto nejsou čistým srovnáním generování.

| Model | Q1 včetně možného načítání | Součet Q2–Q6 | Průměr Q2–Q6 |
|---|---:|---:|---:|
| Qwen 4B | 28,0 s | 311,8 s | 62,4 s |
| Qwen latest | 56,5 s | 802,1 s | 160,4 s |
| Qwen 3.8 | 190,2 s | 1 696,5 s | 339,3 s |
| GPT-OSS | 55,0 s | 863,6 s | 172,7 s |
| Ornith | 49,5 s | 551,0 s | 110,2 s |
| Gemma | 51,1 s | 431,2 s | 86,2 s |

Pořadí celkového čekání se vynecháním Q1 nemění. Q2–Q6 jsou doplňkový pohled méně citlivý na možné první načítání, nikoli důkaz zahřátého běhu: další načítání log samostatně neidentifikuje a délky odpovědí se liší. Označení nejrychlejší Q1 níže znamená pouze nejkratší zaznamenané čekání.

### Orientační rychlost výstupu v tokenech/s

Pro tento odhad používám společný pracovní přepočet **1 token ≈ 3 znaky** českého výstupu. Nejde o změřenou vlastnost tokenizerů těchto modelů: diakritika, kód, Markdown a konkrétní tokenizer mohou poměr výrazně změnit. Proto uvádím také citlivost výsledku při **2–4 znacích/token**; nejde o statistický interval spolehlivosti a skutečnost může ležet i mimo něj.

Počítám znaky skutečné odpovědi v logu včetně mezer, Markdownu a kódu, po sjednocení konců řádků na LF a odstranění krajního whitespace. Nezapočítávám zadání ani hlášení aplikace. Pro každou odpověď platí **odhad tokenů = znaky / 3** a **odhad tok/s = znaky / (3 × čas)**. Souhrnná rychlost je **součet znaků / (3 × součet časů)**, nikoli aritmetický průměr rychlostí jednotlivých otázek.

**Jde o odhad toku viditelného výstupu za celou dobu čekání, nikoli čisté rychlosti generování modelu.** Čas stále zahrnuje zpracování vstupu, případné načítání a další čekání; text neobsahuje případné skryté generované tokeny. Q2–Q6 omezují vliv prvního načítání, ale neodstraňují ostatní režii. Přesná generovací rychlost se v Ollamě počítá jako `eval_count / eval_duration × 10^9`; tato metadata v dodaných logách nejsou. [Ollama – metriky využití](https://docs.ollama.com/api/usage)

| Model | Znaky Q1–Q6 | Odhad tokenů Q1–Q6 | Odhad tok/s Q1–Q6 | Odhad tok/s Q2–Q6 | Q2–Q6 při 2–4 znacích/token |
|---|---:|---:|---:|---:|---:|
| `qwen3.5:4b` | 8 748 | ≈ 2 916 | ≈ 8,6 | ≈ 8,7 | 6,5–13,1 |
| `qwen3.5:latest` | 12 287 | ≈ 4 096 | ≈ 4,8 | ≈ 4,9 | 3,6–7,3 |
| `qwen3.8:latest` | 8 624 | ≈ 2 875 | ≈ 1,5 | ≈ 1,6 | 1,2–2,4 |
| `gpt-oss:latest` | 6 569 | ≈ 2 190 | ≈ 2,4 | ≈ 2,3 | 1,8–3,5 |
| `ornith:9b` | 8 317 | ≈ 2 772 | ≈ 4,6 | ≈ 4,7 | 3,6–7,1 |
| `gemma4:latest` | 11 015 | ≈ 3 672 | ≈ 7,6 | ≈ 8,0 | 6,0–12,0 |

Stejný přepočet je použit v tabulkách jednotlivých odpovědí a v závěrečném přehledu. Rozdíly mezi stroji nelze přičíst samotnému operačnímu systému bez znalosti hardwaru a přesných vah modelů.

## Zadání a bodování

Otázky jsou stejné jako v linuxové sadě: **Q1** modrá obloha pro dvanáctiletého (~100 slov); **Q2** tabulkové TCP/UDP včetně otázky rychlosti; **Q3** stručná diagnostika Ollama HTTP 404 s příkazy; **Q4** překlad složité anglické podmínkové věty do češtiny; **Q5** tři čeští králové, data a evropský význam s rozlišením římských titulů; **Q6** entropie černé díry, plocha vs. objem a teoretický výsledek vs. holografická hypotéza (~100 slov).

Ruční orientační skóre **0–5**, všechny otázky mají stejnou váhu:

- **Relevantnost (R):** 5 = úplně plní téma a formu, 4 = menší odchylka, 3 = podstatná část chybí nebo nesedí stručnost/formát, 2 = slabé pokrytí, 1 = téměř mimo, 0 = mimo. Pravdivost hodnotím zvlášť.
- **Správnost (S):** 5 = bez nalezené podstatné chyby, 4 = drobné nepřesnosti, 3 = správné jádro s významnými vadami, 2 = zásadní chyby, 1 = převážně nespolehlivé, 0 = prakticky smyšlené. U Q4 zahrnuje gramatiku a významovou věrnost.
- **Rychlost:** sekundy podle výše uvedeného výpočtu; není převáděna na body. Neprovedený test má „nehodnoceno“.

### Referenční opora

- Rozptyl na molekulách atmosféry vysvětluje modrou oblohu; prach ani lom světla nejsou adekvátní náhradou tohoto vysvětlení. [NASA](https://spaceplace.nasa.gov/blue-sky/en/)
- UDP má osmibajtovou hlavičku a kontrolní součet; nedoručení a poškození nejsou totéž. TCP používá proud bajtů, potvrzování, retransmise a okna; automaticky není rychlejší ani pomalejší v každém aplikačním scénáři. [RFC 768](https://www.rfc-editor.org/rfc/rfc768.html), [RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html)
- U Ollamy může 404 znamenat i chybějící model. Správné nativní trasy jsou například `/api/version`, `/api/tags`, `/api/generate`; podporováno je také `/v1/chat/completions`. Kořen standardně vrací text `Ollama is running`. [Chyby API](https://docs.ollama.com/api/errors), [API generate](https://docs.ollama.com/api/generate), [registrace tras](https://github.com/ollama/ollama/blob/main/server/routes.go)
- Karel IV. byl římským králem od 1346 a císařem od 1355. Svatováclavská koruna pochází z jeho doby, nikoli z vlády Přemysla Otakara II. [ČNB – Karel IV.](https://www.cnb.cz/cs/bankovky-a-mince/bankovky/karel-iv/index.html), [Pražský hrad – korunovační klenoty](https://www.hrad.cz/cs/prazsky-hrad-pro-navstevniky/ostatni/korunovacni-klenoty-10202)
- Plošný zákon entropie černých děr motivuje holografický princip; univerzální holografie není jednoduše prokázaný fakt. Zápis `S = A/4` navíc vyžaduje příslušnou volbu jednotek. [Bousso: The holographic principle](https://arxiv.org/abs/hep-th/0203101)

## qwen3.5:4b – nejrychlejší, nízká spolehlivost

Odpovědi jsou v [logu](log.txt), úlohy **502–507**; místní `.md` nejsou dodány.

| Otázka | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| Q1 – obloha | 4 | 3 | 28,0 s | ≈ 7,2 | Správně uvádí krátkovlnný rozptyl, ale čeština je špatná („Nebe jsou modrá“) a závěr se „šedivou dekou“ vysvětlení zatemňuje. |
| Q2 – TCP/UDP | 5 | 3 | 109,4 s | ≈ 9,4 | Pokrývá všechna kritéria. Přehání obecnou rychlostní výhodu UDP a tvrdí, že při nízké ztrátovosti mechanismus oprav TCP „nefunguje“; přesnější by bylo, že nemusí zasahovat. |
| Q3 – HTTP 404 | 3 | 1 | 83,7 s | ≈ 8,7 | Vymýšlí `/api/v1/generate`, `/api/v1/tags` a přepínače naslouchání; zaměňuje port a adresu. Prakticky nepoužitelný postup, přesto nejrychlejší Q3. |
| Q4 – překlad | 5 | 2 | 10,4 s | ≈ 7,4 | „Pokudby“ a „mohli by zamítli“ porušují gramatiku, časové vztahy jsou neobratné. Nejrychlejší překlad, ale vyžaduje opravu. |
| Q5 – králové | 4 | 0 | 81,4 s | ≈ 8,0 | „Bohuslav II.“, „Venceslav III. (Přemysl Otakar I.)“ a smyšlená císařství. Prakticky celá historie je chybná. |
| Q6 – entropie | 4 | 3 | 26,9 s | ≈ 8,6 | Správné jádro plošného zákona a zmínka o hypotéze; `S = A/4` bez jednotek, příliš doslovné „pouze na povrchu“ a nepřesné zobecnění na regiony. |

**Relevantnost 4,2/5; správnost 2,0/5.** Celkem **339,8 s**, průměr **56,6 s**. Nejrychlejší sada i Q1, Q3 a Q4, ale zejména technický návod a historie selhávají. Q5 a Q6 nyní rychleji dokončila Gemma. Rychlost sama zde není důvodem odpověď převzít.

## qwen3.5:latest – delší texty bez odpovídající jistoty

Odpovědi jsou v [logu](log.txt), úlohy **508–513**; místní `.md` nejsou dodány.

| Otázka | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| Q1 – obloha | 4 | 3 | 56,5 s | ≈ 3,5 | Rozptyl a kratší vlny jsou přítomné, ale míchá je s odrazem; závěr a gramatika jsou výrazně neobratné. |
| Q2 – TCP/UDP | 5 | 3 | 238,7 s | ≈ 5,4 | Užitečně rozlišuje latenci a propustnost. Chybně říká, že UDP nezjistí poškození, a zaměňuje pauzu při ztrátě za slow start. |
| Q3 – HTTP 404 | 3 | 2 | 116,9 s | ≈ 4,7 | Obsahuje správný POST endpoint, ale očekává nesmyslnou odpověď `context exceeded` na kořeni a v závěru opět zaměňuje 404 modelu za neexistující endpoint. |
| Q4 – překlad | 5 | 2 | 19,2 s | ≈ 3,9 | „Pokudby“, „mohli by zamítli“, silnější „potvrdily“ místo „podpořily“. Význam je přibližný, jazyk není přirozený. |
| Q5 – králové | 2 | 1 | 383,6 s | ≈ 4,6 | Přes šest minut střídá tabulky a vlastní korekce, aniž opraví výmysly. Vratislav II. jako syn Václava I., Jan Lucemburský jako císař; konec je nedokončený. |
| Q6 – entropie | 4 | 4 | 43,7 s | ≈ 5,2 | Poměrně dobře odděluje plošný výsledek a obecnou hypotézu. Výraz „matematický důkaz“ je třeba vztahovat k danému teoretickému rámci, ne k univerzální holografii. |

**Relevantnost 3,8/5; správnost 2,5/5.** Celkem **858,6 s**, průměr **143,1 s**. Největší slabinou je Q5: opakování a zdánlivé opravování zvyšují čas, nikoli spolehlivost. Celá sada je přibližně **2,5× pomalejší než 4B**.

## qwen3.8:latest – nejlepší správnost, nejvyšší časová cena

| Otázka / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_q38_1.md) | 5 | 4 | 190,2 s | ≈ 0,9 | Nejlépe čitelné vysvětlení v sadě, správná vazba na vlnovou délku. Nepřesně přimíchává prach a „odráží se zpět“. |
| [Q2 – TCP/UDP](compare_q38_2.md) | 4 | 3 | 784,1 s | ≈ 1,7 | Správné velikosti hlaviček a rozlišení latence/propustnosti. Příliš dlouhé; závěr mylně naznačuje doručování poškozených dat jako vlastnost UDP. Výklad flow control na routerech je nepřesný. |
| [Q3 – HTTP 404](diagnose_q38_3.md) | 5 | 4 | 275,4 s | ≈ 1,6 | Nejlepší diagnostika: verze, seznam modelů, POST a rozlišení těla chyby. Ještě je třeba použít skutečnou adresu aplikace a instalovaný model místo příkladového `llama2`; jiný text 404 není absolutní důkaz chybné cesty. |
| [Q4 – překlad](translate_q38_4.md) | 5 | 5 | 59,4 s | ≈ 1,2 | Nejlepší překlad: přirozená čeština, zachovaná podmínka, kalibrační chyba i slabší „podpořily“. Převod budoucnosti v minulosti do českého vyprávěcího minulého času je přirozený. |
| [Q5 – králové](kings_q38_5.md) | 4 | 1 | 435,9 s | ≈ 1,5 | Správná hlavní data Karla a Přemysla, ale smyšlená císařská období Václava IV., „Rudolfovy listiny“ u Karla a anachronismus se Svatováclavskou korunou u Přemysla. |
| [Q6 – entropie](entropy_q38_6.md) | 5 | 4 | 141,7 s | ≈ 1,7 | Dobré odlišení zákona a hypotézy, srozumitelný text. „Myšlenkový experiment“ zjednodušuje teoretické základy a stav holografie. |

**Relevantnost 4,7/5; správnost 3,5/5.** Celkem **1 886,7 s**, průměr **314,4 s**. Nejlepší kvalita sady, ale celkově asi **5,6× pomalejší než 4B**. Q2 zabrala přes 13 minut a Q5 přes 7 minut, přesto obě obsahují chyby. Největší přínos je v Q3 a Q4; nejde o spolehlivý historický zdroj.

## gpt-oss:latest – lepší forma než faktická jistota

| Otázka / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_gpt_1.md) | 4 | 3 | 55,0 s | ≈ 3,0 | Správně zmiňuje i fialové světlo; konečná analogie „bublina s barevným papotem“ je nesrozumitelná. |
| [Q2 – TCP/UDP](compare_gpt_2.md) | 5 | 3 | 106,3 s | ≈ 5,8 | Přehledná, relativně stručná tabulka; nejrychlejší Q2. Výrok, že TCP je efektivní, protože se vyhýbá opakovaným přenosům, je zavádějící vůči jeho retransmisím. |
| [Q3 – HTTP 404](diagnose_gpt_3.md) | 3 | 2 | 139,3 s | ≈ 5,9 | Užitečné čtení těla chyby a správný filtr `.models[]`. Současně tvrdí, že HTTP 404 znamená neotevřený port, nabízí `/api/models` a matoucí GET generování. Tabulka je neúplná. |
| [Q4 – překlad](translate_gpt_4.md) | 5 | 3 | 155,3 s | ≈ 0,4 | „Ne zohlednili“ je pravopisná chyba, „opomenutou kalibrací“ vypouští chybu kalibrace. Podmínka je gramaticky lepší než u 4B, Qwen latest a Ornith, ale ne významově přesná. |
| [Q5 – králové](kings_gpt_5.md) | 2 | 1 | 293,7 s | ≈ 1,0 | Pouze první řádek a část druhého místo tří králů. Směšuje „Václav II (Charles V)“ s 16. stoletím; text končí „Byl prvním“. |
| [Q6 – entropie](entropy_gpt_6.md) | 4 | 4 | 169,0 s | ≈ 1,3 | Správný úplný vzorec a základní rozlišení výsledku/hypotézy. Původ v „kvantové gravitaci a kvantovém poli“ je volný; jazykové vady. |

**Relevantnost 3,8/5; správnost 2,7/5.** Celkem **918,6 s**, průměr **153,1 s**. Proti Qwen latest mírně vyšší skóre za o něco delší čekání; rozdíl nelze z jedné sady zobecnit. Q5 ukazuje, že dokončený API požadavek nemusí znamenat dokončenou odpověď na zadání.

## ornith:9b – na Windows dostupný, kvalitou nepřesvědčil

| Otázka / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_orn9_1.md) | 4 | 3 | 49,5 s | ≈ 3,3 | Správná základní myšlenka rozptylu, ale bizarní analogie s koulí v bazénu a chybějící jasná příčina závislosti na barvě. |
| [Q2 – TCP/UDP](compare_orn9_2.md) | 4 | 2 | 176,0 s | ≈ 5,3 | Základní srovnání je poznatelné, ale zaměňuje hlavičky za 20 vs. 40 bajtů a popírá kontrolu poškození u UDP. Čeština obsahuje ruštinu a výrazy jako „trojní zápotce“. |
| [Q3 – HTTP 404](diagnose_orn9_3.md) | 3 | 1 | 210,0 s | ≈ 4,6 | Správné příklady POST, ale chybná očekávaná odpověď kořene, status **406** pro chybějící model a nesprávné označení `/v1/chat/completions` za špatnou URL. Zásadně narušuje požadované rozlišení chyb. |
| [Q4 – překlad](translate_orn9_4.md) | 5 | 2 | 19,6 s | ≈ 3,8 | Zachovává kalibrační chybu, ale „mohli by odmítli“ je negramatické a „potvrdily“ zesiluje původní podporu hypotézy. |
| [Q5 – králové](kings_orn9_5.md) | 4 | 1 | 93,6 s | ≈ 4,1 | Chybná římská data Karla, neexistující císař „Hugo IV. z Burgunda“, česká vláda Václava IV. chybně ukončena 1400. |
| [Q6 – entropie](entropy_orn9_6.md) | 5 | 4 | 51,8 s | ≈ 4,9 | Nejlepší odpověď tohoto modelu: srozumitelná plošná závislost a rozlišení hypotézy. Závěrečné zobecnění „do celé fyziky“ je příliš široké. |

**Relevantnost 4,2/5; správnost 2,2/5.** Celkem **600,5 s**, průměr **100,1 s**. Třetí nejrychlejší sada po 4B a Gemma, ale technická i jazyková kvalita je nízká. Oproti linuxovému logu nyní existují skutečné odpovědi; linuxové „model nenalezen“ nevypovídalo o jeho schopnostech.

## gemma4:latest – druhá nejrychlejší, překlad tentokrát selhal

Dokončené flow od **11:59:18**, úlohy **532–537**, stejné nastavení jako ostatní české sady. Všech šest dodaných souborů odpovídá tomuto běhu.

| Otázka / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_g4_1.md) | 4 | 3 | 51,1 s | ≈ 4,2 | Základní rozptyl na plynech uvádí správně, ale nevysvětluje závislost na vlnové délce. „Nitrogen“, „modrevé“ a analogie s odrážejícím se modrým balónem zhoršují češtinu i názornost. |
| [Q2 – TCP/UDP](compare_g4_2.md) | 4 | 3 | 171,9 s | ≈ 8,1 | Dobré základní porovnání spojení, doručení a pořadí; zbytečně opakuje tabulku v textu. Tvrzení, že UDP nemá žádnou režii a má nižší latenci pro každý paket, je chybné. Jazyk obsahuje „zácizení“ a cyrilici. |
| [Q3 – HTTP 404](diagnose_g4_3.md) | 3 | 2 | 157,2 s | ≈ 8,2 | Užitečný test `/api/version` a požadavek testovat ze stejného kontextu jako aplikace. Poté ale zaměňuje 404 při generování za neexistující endpoint a v souhrnu HTTP 404 za nedostupný port. Chybí spolehlivé rozlišení podle těla chyby; příliš dlouhé pro `brief`. |
| [Q4 – překlad](translate_g4_4.md) | 5 | 1 | 12,1 s | ≈ 6,0 | „Neuzvolnili možnost“ je nesrozumitelné, „měření … zdály … byly zkreslena“ má chybnou shodu. „Odložit“ mění odmítnutí hypotézy a „potvrdily“ zesiluje pouhou podporu. Rychlé, ale významově i gramaticky velmi slabé. |
| [Q5 – králové](kings_g4_5.md) | 3 | 1 | 65,1 s | ≈ 7,7 | Reálná jména, ale chybné letopočty všech tří řádků, zejména Václav II. v letech 1085–1125. „Zvěsti se liší“ nenahrazuje ověření; vliv k „Teplici na Moravě“ nevysvětluje evropský význam Přemysla Otakara II. Nejrychlejší Q5, obsah nespolehlivý. |
| [Q6 – entropie](entropy_g4_6.md) | 5 | 4 | 24,9 s | ≈ 8,2 | Dobře zachycuje vztah k ploše a rozlišuje teoretický výsledek od širší hypotézy. „Informace může být kvantizována“ je terminologicky volné, ale základní smysl drží. Nejrychlejší Q6 a nejlepší odpověď tohoto běhu Gemma. |

**Relevantnost 4,0/5; správnost 2,3/5.** Celkem **482,3 s**, průměr **80,4 s**; celé flow **499,1 s**. Druhá nejrychlejší sada, přibližně o **42 % delší než 4B**, a druhý nejvyšší odhad toku výstupu (**7,6 tok/s**, bez Q1 **8,0 tok/s**). Kvalitou však zůstává za Qwen 3.8, GPT a Qwen latest. V Q6 se dělí o nejvyšší skóre a je nejrychlejší.

Proti linuxové Gemma je zejména překlad podstatně horší (1/5 oproti 4/5), přestože byl opět rychlý. Jde o jinou odpověď s jiným seedem; rozdíl nelze přičíst Windows ani z něj odvodit obecný pokles schopností modelu.

## Prokliky na nejlepší odpovědi

„Nejlepší“ označuje relativní výsledek této sady, ne záruku bezchybnosti. Odkazy vedou na existující `.md` ve stejné složce.

| Otázka | Nejlepší výsledek | Výhrada / shoda |
|---|---|---|
| Q1 – obloha | [Qwen 3.8](explain_q38_1.md) | 4/5; nejlepší čitelnost, drobné fyzikální nepřesnosti. |
| Q2 – TCP/UDP | [GPT](compare_gpt_2.md), [Qwen 3.8](compare_q38_2.md), [Gemma](compare_g4_2.md) | Nejvyšší skóre jen 3/5; GPT je stručnější a rychlejší. Stejné skóre mají také 4B a Qwen latest, dostupné pouze v logu. |
| Q3 – HTTP 404 | [Qwen 3.8](diagnose_q38_3.md) | 4/5; nejlepší rozlišení příčin, adresu/model je třeba přizpůsobit. |
| Q4 – překlad | [Qwen 3.8](translate_q38_4.md) | 5/5; nejsilnější jednotlivá odpověď sady. |
| Q5 – králové | Žádná spolehlivá odpověď | Nejvyšší správnost pouze 1/5. |
| Q6 – entropie | [Gemma](entropy_g4_6.md), [Qwen 3.8](entropy_q38_6.md), [GPT](entropy_gpt_6.md), [Ornith](entropy_orn9_6.md) | Shodně 4/5; stejnou známku má i Qwen latest, ale jeho `.md` chybí. Gemma je nejrychlejší. |

## Souhrnná tabulka

Řazeno podle průměrné správnosti. **Qwen 3.8 je zde volba pro kvalitu při toleranci dlouhého čekání; žádný model současně nevyniká rychlostí i spolehlivostí napříč všemi úlohami.** Malé rozdíly skóre nejsou statisticky průkazné. Pro další měření je vhodné zaznamenat hardware a přesné modely, počty tokenů a více opakování, zvlášť se studeným a již načteným modelem.

| Model | Hodnoceno | Relevantnost / 5 | Správnost / 5 | Celkem odpovědi | Průměr / odpověď | Odhad tok/s Q1–Q6 | Odhad tok/s Q2–Q6 | Silná stránka | Hlavní slabina / verdikt |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| **qwen3.8:latest** | 6/6 | **4,7** | **3,5** | 1 886,7 s (31:27) | 314,4 s | ≈ 1,5 | ≈ 1,6 | Nejlepší [překlad](translate_q38_4.md), [diagnostika](diagnose_q38_3.md), [obloha](explain_q38_1.md) | Nejvyšší správnost, ale nejpomalejší; historie nespolehlivá. |
| **gpt-oss:latest** | 6/6 | 3,8 | 2,7 | 918,6 s (15:19) | 153,1 s | ≈ 2,4 | ≈ 2,3 | Přehledné [TCP/UDP](compare_gpt_2.md), [entropie](entropy_gpt_6.md) | Slabá diagnostika a neúplná smyšlená historie. |
| **qwen3.5:latest** | 6/6 | 3,8 | 2,5 | 858,6 s (14:19) | 143,1 s | ≈ 4,8 | ≈ 4,9 | Entropie (log, úloha 513) | Historie se zacykluje v neúspěšných opravách; vadný překlad. |
| **gemma4:latest** | 6/6 | 4,0 | 2,3 | 482,3 s (8:02) | 80,4 s | ≈ 7,6 | ≈ 8,0 | [Entropie](entropy_g4_6.md), druhý nejkratší celkový čas | Slabý překlad, chybná historie i diagnostika. |
| **ornith:9b** | 6/6 | 4,2 | 2,2 | 600,5 s (10:01) | 100,1 s | ≈ 4,6 | ≈ 4,7 | [Entropie](entropy_orn9_6.md), třetí nejkratší celkový čas | Technické chyby, slabá čeština i historie. |
| **qwen3.5:4b** | 6/6 | 4,2 | 2,0 | **339,8 s (5:40)** | **56,6 s** | ≈ 8,6 | ≈ 8,7 | Nejrychlejší sada | Nejnižší správnost; smyšlené endpointy a králové. |

---

kredit: "zpracovala GPT-6 Astra Střední"

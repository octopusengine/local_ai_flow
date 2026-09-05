# Test modelů na Linuxu – test1_lx

Vyhodnocení dodaného [logu](log_lx.txt) z **5. 9. 2026**, přibližně 10:31–11:36. Hodnoceny jsou české odpovědi na šest společných otázek. Názvy flow v logu ještě nemají příponu `_cz`; nejde o pozdější anglickou sadu.

**V této sadě vychází Gemma 4 nejlépe jako kompromis kvality a času. Qwen 3.5 4B je nejrychlejší, ale také nejméně spolehlivý. GPT-OSS podal nejlepší porovnání TCP/UDP, za cenu výrazně delšího čekání. Žádný model nepodal spolehlivou odpověď o českých králích a žádný nenabídl bezchybný postup diagnostiky HTTP 404.** Jde o malé lokální srovnání konkrétních běhů, nikoli obecný žebříček modelů.

## Podklady a výběr běhů

Primárním zdrojem je `log_lx.txt`, který obsahuje zadání, nastavení, odpovědi, časy i chyby. Ve složce je také 23 samostatných výsledků `.md`; jejich obsah odpovídá odpovědím vybraných dokončených běhů. Chybí pouze `explain_gpt_1.md`, ale odpověď GPT na první otázku v logu je, takže ji lze hodnotit.

Soubory odpovědí mají doplněné dvouřádkové záhlaví s modelem, parametry, časem a odhadem tokenů/s. Původní odpověď pod oddělovačem zůstává beze změny; záhlaví není započítáno do délky ani odhadu tokenů.

Pro každý model je vybrána jedna kompletní sada šesti odpovědí. Dřívější neúplné pokusy nejsou přimíchány do průměrů ani použity k výběru „nejlepší odpovědi“.

| Model uvedený v logu | Začátek vybraného flow | ID úloh v logu | Dokončené odpovědi |
|---|---|---|---:|
| `qwen3.5:4b` (`q34`) | 10:53:43 | 163–168 | 6/6 |
| `qwen3.5:latest` (`q35`) | 10:59:53 | 169–174 | 6/6 |
| `gpt-oss:latest` (`gpt`) | 11:12:05 | 175–180 | 6/6 |
| `gemma4:latest` (`g4`) | 11:27:00 | 181–186 | 6/6 |

Další události v logu:

- První pokusy s Qwen 4B, Qwen latest a Gemma dokončily vždy Q1 a Q2, ale Q3 zastavila chyba aplikace `OSError: [Errno 36] File name too long`. Nejde o věcnou chybu odpovědi modelu; tyto běhy nejsou součástí srovnání.
- Jeden další pokus s Gemma skončil odpojením `RemoteDisconnected` po 5,1 s. Log neumožňuje určit příčinu; následný kompletní běh uspěl.
- `ornith:9b` byl spuštěn ve třech sadách, pokaždé však všech šest úloh skončilo hlášením, že model není nalezen. Celkem 18 úloh bez inference. Závěrečné hlášení runneru o úspěšném flow zde **neznamená úspěšný test modelu**.
- Poslední pokus s GPT byl přerušen uživatelem během Q1 a není hodnocen.
- `qwen3.8:latest` v dodaném logu není; nelze jej hodnotit.

## Nastavení a význam časů

| Parametr | Hodnota v hodnocených požadavcích |
|---|---|
| Typ úlohy / šablona | `prompt` / `task_base.json` |
| Jazyk | čeština, `--sc-cz` |
| `temperature` | `0.5` |
| `num_predict` | `2048` |
| `num_ctx` | `4096` |
| `repeat_penalty` | `1.1` |
| `think` | `false` |
| Seed | Souhrn uvádí `seed: 0`, ale každý požadavek následně vypisuje jiné konkrétní `Seed:`. Nejde o shodný seed napříč modely. |

Čas odpovědi je údaj `+ …s` u `Ollama response complete`, tedy čekání od odeslání požadavku do jeho dokončení. Může zahrnovat načítání modelu a další režii. **Není to rychlost generování v tokenech/s ani čas do prvního tokenu.** Delší odpovědi přirozeně zvyšují celkové čekání.

Log neobsahuje dost údajů o CPU, GPU, RAM, kvantizaci, verzi Ollamy, přesném digestu modelů ani počtech tokenů. Z aliasů `latest` proto neodvozuji konkrétní velikost či variantu modelu. `think: false` je zaznamenané nastavení požadavku, nikoli ověření vnitřního chování každého modelu.

### První odpověď a načítání modelu

**Q1 (modrá obloha) může zahrnovat zavádění modelu do RAM, případně VRAM, které může trvat i desítky sekund.** Její čas tedy nelze interpretovat jako čistou rychlost odpovědi na jednoduchou otázku. Log neuvádí `load_duration` ani stav modelu před požadavkem, takže nevíme, které běhy začínaly s již načteným modelem a kolik načítání skutečně trvalo.

Pro doplnění uvádím také Q2–Q6 bez první odpovědi. Nejde o prokazatelně zahřátý benchmark ani o tokeny/s, pouze o srovnání méně citlivé na možné první načítání; jednotlivé odpovědi mají různou délku.

| Model | Q1 včetně možného načítání | Součet Q2–Q6 | Průměr Q2–Q6 |
|---|---:|---:|---:|
| Qwen 4B | 22,5 s | 305,8 s | 61,2 s |
| Qwen latest | 39,2 s | 373,8 s | 74,8 s |
| GPT-OSS | 125,9 s | 661,5 s | 132,3 s |
| Gemma | 22,2 s | 372,5 s | 74,5 s |

Po vynechání Q1 zůstává pořadí celkového čekání stejné, ale Gemma a Qwen latest jsou prakticky shodné. Označení nejrychlejší Q1 níže popisuje pouze naměřené čekání včetně možného načítání.

### Orientační rychlost výstupu v tokenech/s

Pro tento odhad používám společný pracovní přepočet **1 token ≈ 3 znaky** českého výstupu. Nejde o změřenou vlastnost tokenizerů těchto modelů: diakritika, kód, Markdown a konkrétní tokenizer mohou poměr výrazně změnit. Proto uvádím také citlivost výsledku při **2–4 znacích/token**; nejde o statistický interval spolehlivosti a skutečnost může ležet i mimo něj.

Počítám znaky skutečné odpovědi v logu včetně mezer, Markdownu a kódu, po sjednocení konců řádků na LF a odstranění krajního whitespace. Nezapočítávám zadání ani hlášení aplikace. Pro každou odpověď platí **odhad tokenů = znaky / 3** a **odhad tok/s = znaky / (3 × čas)**. Souhrnná rychlost je **součet znaků / (3 × součet časů)**, nikoli aritmetický průměr rychlostí jednotlivých otázek.

**Jde o odhad toku viditelného výstupu za celou dobu čekání, nikoli čisté rychlosti generování modelu.** Čas stále zahrnuje zpracování vstupu, případné načítání a další čekání; text neobsahuje případné skryté generované tokeny. Q2–Q6 omezují vliv prvního načítání, ale neodstraňují ostatní režii. Přesná generovací rychlost se v Ollamě počítá jako `eval_count / eval_duration × 10^9`; tato metadata v dodaných logách nejsou. [Ollama – metriky využití](https://docs.ollama.com/api/usage)

| Model | Znaky Q1–Q6 | Odhad tokenů Q1–Q6 | Odhad tok/s Q1–Q6 | Odhad tok/s Q2–Q6 | Q2–Q6 při 2–4 znacích/token |
|---|---:|---:|---:|---:|---:|
| `qwen3.5:4b` | 9 338 | ≈ 3 113 | ≈ 9,5 | ≈ 9,5 | 7,2–14,3 |
| `qwen3.5:latest` | 6 879 | ≈ 2 293 | ≈ 5,6 | ≈ 5,6 | 4,2–8,4 |
| `gpt-oss:latest` | 7 345 | ≈ 2 448 | ≈ 3,1 | ≈ 3,4 | 2,5–5,1 |
| `gemma4:latest` | 11 038 | ≈ 3 679 | ≈ 9,3 | ≈ 9,5 | 7,1–14,2 |

Stejný přepočet je použit v tabulkách jednotlivých odpovědí a v závěrečném přehledu. Rozdíly mezi stroji nelze přičíst samotnému operačnímu systému bez znalosti hardwaru a přesných vah modelů.

## Otázky a způsob hodnocení

| # | Úloha | Požadovaný způsob odpovědi |
|---|---|---|
| Q1 | Proč je nebe modré? | Jednoduše pro dvanáctiletého, přibližně 100 slov (`eli12`, `about100`). |
| Q2 | TCP vs. UDP | Tabulka: spojení, doručení, pořadí, použití; vysvětlit, zda je UDP vždy rychlejší. |
| Q3 | Ollama vrací HTTP 404 | Stručný diagnostický postup, rozlišení adresy/endpointu a modelu (`howto`, `steps`, `brief`). |
| Q4 | Složitá anglická podmínková věta → čeština | Zachovat význam, časové vztahy a přirozenou češtinu. |
| Q5 | Tři čeští králové evropského významu | Období české vlády, důvod významu; rozlišit případné římské královské/císařské období. |
| Q6 | Entropie černé díry | Plocha vs. objem, vazba na holografii; odlišit zavedený teoretický výsledek od širší hypotézy, přibližně 100 slov. |

Hodnocení je ruční, orientační, na škále **0–5**. Každá otázka má v průměru stejnou váhu:

- **Relevantnost (R):** 5 = plní téma i formu; 4 = menší odchylka; 3 = chybí část zadání nebo výrazně nesedí stručnost/formát; 2 = slabé pokrytí; 1 = téměř mimo; 0 = mimo zadání. Faktická chyba sama o sobě nesnižuje R, pokud odpověď formálně reaguje na požadované téma.
- **Správnost (S):** 5 = bez nalezené podstatné chyby; 4 = drobné nepřesnosti; 3 = správné jádro s významnými vadami; 2 = zásadní chyby; 1 = převážně nespolehlivé; 0 = prakticky smyšlené. U překladu zahrnuje i gramatiku a významovou věrnost.
- **Rychlost:** skutečné sekundy z logu, bez převodu na subjektivní body. Neprovedené úlohy mají „nehodnoceno“, nikoli nulu bodů či nulovou latenci.

### Referenční opora pro kontrolu

- Modrá obloha vzniká rozptylem slunečního světla v atmosféře; analogie s lomem světla nebo čočkou mechanismus zkreslují. [NASA](https://spaceplace.nasa.gov/blue-sky/en/)
- TCP poskytuje spolehlivý uspořádaný proud bajtů a používá okno; nemusí čekat na ACK po každém jednotlivém úseku. UDP pracuje s datagramy a má kontrolní součet, i když nezajišťuje opakované doručení. [RFC 9293 – TCP](https://www.rfc-editor.org/rfc/rfc9293.html), [RFC 768 – UDP](https://www.rfc-editor.org/rfc/rfc768.html)
- U Ollamy je třeba rozlišit chybnou trasu a neexistující model podle těla chyby. `GET /api/tags` vrací objekt s polem `models`; generování používá `POST /api/generate`. Kořen `/` standardně vrací text `Ollama is running`; samotné `/api` není spolehlivý zdravotní test serveru. [Chyby API](https://docs.ollama.com/api/errors), [seznam modelů](https://docs.ollama.com/api/tags), [generování](https://docs.ollama.com/api/generate), [registrace tras](https://github.com/ollama/ollama/blob/main/server/routes.go). Konkrétní verze testovaného serveru v logu chybí.
- Karel IV. byl českým i římským králem od roku 1346, císařem od 1355; roku 1348 založil Nové Město pražské a univerzitu, nikoli celou Prahu. Václav II. vládl v letech 1278–1305 a nebyl římským císařem. [ČNB – Karel IV.](https://www.cnb.cz/cs/bankovky-a-mince/bankovky/karel-iv/index.html), [Hrvatska enciklopedija – Václav II.](https://www.enciklopedija.hr/clanak/vaclav-ii)
- Bekensteinova–Hawkingova entropie je úměrná ploše horizontu. Jde o výsledek teorie černých děr se zapojením kvantových jevů; širší holografický princip nelze vydávat za univerzálně experimentálně potvrzený fakt. [Bousso: The holographic principle](https://arxiv.org/abs/hep-th/0203101)

## qwen3.5:4b – nejrychlejší, ale s největšími chybami

| Úloha / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_q34_1.md) | 4 | 3 | 22,5 s | ≈ 8,6 | Správné jádro rozptylu a rozdílu vlnových délek. Vadná čeština („Nebe jsou modrá“) a nepomáhající přirovnání s prachem ve skleněné nádobě. |
| [Q2 – TCP/UDP](compare_q34_2.md) | 5 | 3 | 81,9 s | ≈ 10,6 | Pokrývá požadovaná kritéria a správně odmítá „UDP vždy rychlejší“. Chybně tvrdí, že TCP musí čekat na ACK před každou další částí dat; nepřesně popisuje opravy chyb. |
| [Q3 – HTTP 404](diagnose_q34_3.md) | 3 | 1 | 108,2 s | ≈ 9,7 | Dlouhý postup s chybnými API předpoklady: `/generate` bez `/api`, očekávání `206/JSON` a špatné čtení seznamu modelů z JSON. Prakticky nespolehlivý návod. |
| [Q4 – překlad](translate_q34_4.md) | 5 | 2 | 9,8 s | ≈ 7,5 | Základní smysl je poznat, ale „mohli by odmítli“ je chybně. Posouvá časy a mění podporu hypotézy na silnější „potvrdily“. |
| [Q5 – králové](kings_q34_5.md) | 4 | 0 | 74,5 s | ≈ 8,2 | Prakticky smyšlená historie: „Václav II (Křížovník)“, „Jindřich II (Václav)“, nesouvisející data a události. Tabulkový formát nezachraňuje obsah. |
| [Q6 – entropie](entropy_q34_6.md) | 4 | 2 | 31,4 s | ≈ 10,2 | Správně uvádí úměrnost ploše a pokouší se oddělit hypotézu. Původ vztahu ale vysvětluje nesmyslným spojením „speciální relativity obecné teorie gravitace“; kódování pouze na povrchu podává příliš doslovně. |

**Souhrn:** relevantnost **4,2/5**, správnost **1,8/5**. Součet čekání **328,3 s**, průměr **54,7 s/odpověď**. Nejrychlejší celá sada i jednotlivé Q2 a Q4. Hodí se zde spíše pro rychlý návrh k následné kontrole; u faktografie a technického návodu hrozí přesvědčivě formulované nesmysly.

## qwen3.5:latest – více času bez výrazného kvalitativního posunu

| Úloha / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_q35_1.md) | 4 | 3 | 39,2 s | ≈ 4,9 | Hlavní myšlenka je správná, ale míchá rozptyl a odraz; přirovnání k obrazové ploše nepomáhá přesnosti. Jazykově neobratné. |
| [Q2 – TCP/UDP](compare_q35_2.md) | 5 | 2 | 180,1 s | ≈ 6,1 | Formálně úplné porovnání. UDP označuje jako stream a chybně přisuzuje Nagleovu algoritmu / Delayed ACK snižování počtu handshakeů. |
| [Q3 – HTTP 404](diagnose_q35_3.md) | 3 | 2 | 74,8 s | ≈ 5,4 | Nejrychlejší diagnostická odpověď a relativně stručná. Chybně interpretuje kořen `/`; chybí přesný POST test, který by oddělil neexistující trasu od chybějícího modelu. |
| [Q4 – překlad](translate_q35_4.md) | 5 | 2 | 18,3 s | ≈ 4,0 | Podobné chyby jako 4B: „mohli by zamítli“, narušené časové vztahy a „potvrdily“ místo slabšího „podpořily“. |
| [Q5 – králové](kings_q35_5.md) | 3 | 1 | 55,2 s | ≈ 4,7 | Jména a české letopočty jsou výrazně lepší než u 4B, důvody významu však obsahují zásadní výmysly: Václav I. jako zakladatel Přemyslovců, Jan Lucemburský jako římský král či účastník husitských konfliktů. |
| [Q6 – entropie](entropy_q35_6.md) | 4 | 3 | 45,4 s | ≈ 5,8 | Správné základní rozlišení plochy a objemu i zmínka o hypotéze. Formulace „potvrzený v rámci kvantové gravitace“ přeceňuje status výsledku; výklad povrchu je zjednodušený. |

**Souhrn:** relevantnost **4,0/5**, správnost **2,2/5**. Součet **413,0 s**, průměr **68,8 s/odpověď**. Celkově přibližně o **26 % pomalejší než 4B** a zároveň pomalejší než Gemma. Tato sada nedává přesvědčivý důvod preferovat jej před Gemma; výhodou byl čas Q3, nikoli správnost postupu.

## gpt-oss:latest – nejlepší TCP/UDP, nejdelší čekání

| Úloha / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| Q1 – obloha ([log](log_lx.txt), úloha 175) | 4 | 2 | 125,9 s | ≈ 1,6 | Správně jmenuje Rayleighův rozptyl, ale míchá jej s rozkladem světla a přidává nesrozumitelnou analogii s křišťálovým prstenem. Pro jednoduché dětské vysvětlení slabé. |
| [Q2 – TCP/UDP](compare_gpt_2.md) | 5 | 4 | 116,3 s | ≈ 6,8 | Nejlepší odpověď této otázky v sadě: dobré pokrytí kritérií i podmíněnosti rychlosti. Zůstává zjednodušené absolutní „zaručení“ doručení a místy volná terminologie. |
| [Q3 – HTTP 404](diagnose_gpt_3.md) | 3 | 2 | 111,9 s | ≈ 7,3 | Užitečně rozlišuje JSON chybu „model not found“. Současně opakovaně doporučuje samotné `/api` jako kontrolní endpoint a vyvozuje z jeho 404 chybný závěr. Rozbitá tabulka snižuje použitelnost. |
| [Q4 – překlad](translate_gpt_4.md) | 5 | 3 | 102,3 s | ≈ 0,7 | Podmínková konstrukce je lepší než u Qwenů. „Přehlédnutou kalibrací“ ale ztrácí význam chyby kalibrace, chybí „se“ a časová návaznost není přesná. |
| [Q5 – králové](kings_gpt_5.md) | 5 | 2 | 194,2 s | ≈ 1,8 | Dobře strukturované oddělení titulů; podstatné části o Přemyslu Otakarovi II. a Karlu IV. jsou správné. Václava II. však posouvá do let 1305–1306 a vymýšlí mu císařství 1310–1316. Římskou královskou vládu Karla od 1346 neuvádí. |
| [Q6 – entropie](entropy_gpt_6.md) | 4 | 3 | 136,8 s | ≈ 1,6 | Správný úplný vzorec entropie. Plošný zákon ovšem nazývá „klíčovým důkazem holografického principu“, což je silnější závěr, než lze obecně učinit; formulace o vypouštění informací je zavádějící. |

**Souhrn:** relevantnost **4,3/5**, správnost **2,7/5**. Součet **787,4 s**, průměr **131,2 s/odpověď**. Celá sada trvala přibližně **2,4× déle než u Qwen 4B**. Lepší technické porovnání se zde nepřeneslo do spolehlivé historie ani diagnostiky. Na překlad čekal přes 100 s, zatímco lepší překlad Gemma dodala za přibližně 10 s.

## gemma4:latest – nejlepší místní kompromis, stále nutná kontrola faktů

| Úloha / odpověď | R / 5 | S / 5 | Čas | Odhad tok/s | Posouzení |
|---|---:|---:|---:|---:|---|
| [Q1 – obloha](explain_g4_1.md) | 4 | 3 | 22,2 s | ≈ 6,7 | Jednoduché a převážně správné vysvětlení rozptylu, jazykové vady a příliš kategorické „modré nejvíce“. Nejrychlejší Q1, jen těsně před 4B. |
| [Q2 – TCP/UDP](compare_g4_2.md) | 4 | 3 | 147,3 s | ≈ 9,8 | Správné základní porovnání, ale dlouhé a opakující se. Chybné tvrzení, že UDP nezjistí změnu paketu, ignoruje kontrolní součet; „nemá žádnou režii“ je také nepravda. |
| [Q3 – HTTP 404](diagnose_g4_3.md) | 3 | 2 | 143,2 s | ≈ 9,3 | Nabízí konkrétní příkazy, ale test s libovolným `llama2` může sám vyvolat chybu chybějícího modelu. Z 404 příliš rychle usuzuje na neexistující endpoint; licenční spekulace nepomáhají. Příliš dlouhé pro `brief`. |
| [Q4 – překlad](translate_g4_4.md) | 5 | 4 | 10,1 s | ≈ 7,2 | Nejlepší překlad sady: přirozená podmínka a zachovaná chyba kalibrace i význam podpory hypotézy. Závěrečné „podpoří“ mírně zplošťuje časový pohled původní věty. |
| [Q5 – králové](kings_g4_5.md) | 3 | 1 | 52,2 s | ≈ 9,4 | Přemysl Otakar II. je zpracován přijatelně. U Václava IV. je význam vágní a chybí římská vláda; třetí „Jiří Ladislav“ s vládou 1368–1402 je výmysl. |
| [Q6 – entropie](entropy_g4_6.md) | 4 | 4 | 19,7 s | ≈ 9,6 | Nejlepší stručný výklad otázky: plošná závislost a srozumitelné odlišení teoretického výsledku od širší hypotézy. Popis holografie zůstává zjednodušený. Nejrychlejší Q6. |

**Souhrn:** relevantnost **3,8/5**, správnost **2,8/5**. Součet **394,7 s**, průměr **65,8 s/odpověď**. Přibližně o **20 % pomalejší než Qwen 4B**, ale nejlepší překlad a výklad entropie. Nižší relevantnost odráží hlavně rozvláčnost a neúplné splnění zadání o králích. Náskok správnosti před GPT je malý a závisí na ručním bodování.

## Jak výsledky použít

Pro tuto českou sadu bych jako výchozí model zvolil **Gemma 4**, pro samotné porovnání síťových protokolů byl lepší **GPT-OSS**. **Qwen 4B** dává smysl tam, kde rozhoduje krátké čekání a výstup projde kontrolou. Sebevědomý tón ani úhledná tabulka zde nepředpovídaly správnost: nejviditelnější příklad je Q5.

Pro další srovnání má smysl zopakovat stejná zadání vícekrát, zaznamenat konkrétní verze modelů a hardware a oddělit první načítání od zahřátých běhů. Počty vstupních/výstupních tokenů by umožnily rozlišit pomalé generování od prostě delší odpovědi. Chyby runneru a chybějící modely je vhodné evidovat zvlášť od kvality odpovědí.

## Prokliky na nejlepší odpovědi

Výběr podle správnosti v této sadě; „nejlepší“ neznamená bezchybná. Odkazy vedou na existující `.md` ve stejné složce.

| Otázka | Nejlepší výsledek | Poznámka |
|---|---|---|
| Q1 – obloha | [Gemma](explain_g4_1.md), [Qwen 4B](explain_q34_1.md), [Qwen latest](explain_q35_1.md) | Shodně 3/5; všechny mají významné vady, Gemma odpověděla nejrychleji. |
| Q2 – TCP/UDP | [GPT-OSS](compare_gpt_2.md) | 4/5, nejlepší technické porovnání. |
| Q3 – HTTP 404 | Žádná spolehlivá odpověď | Nejvyšší správnost pouze 2/5; postupy nelze doporučit k převzetí. |
| Q4 – překlad | [Gemma](translate_g4_4.md) | 4/5, nejlepší jazyková kvalita a významová věrnost. |
| Q5 – králové | Žádná spolehlivá odpověď | I relativně nejlepší výsledek obsahuje zásadní historické výmysly. |
| Q6 – entropie | [Gemma](entropy_g4_6.md) | 4/5, nejlepší stručné rozlišení výsledku a hypotézy. |

## Souhrnná tabulka

Součet a průměr níže zahrnují pouze šest dokončených požadavků vybrané sady. Celé flow včetně režie trvalo postupně 330,0 s (Qwen 4B), 414,9 s (Qwen latest), 789,2 s (GPT) a 396,5 s (Gemma). Řádky jsou seřazeny podle průměrné správnosti; rozdíl 0,1 bodu mezi Gemma a GPT není průkazný kvalitativní odstup.

| Model | Hodnoceno | Relevantnost / 5 | Správnost / 5 | Celkem odpovědi | Průměr / odpověď | Odhad tok/s Q1–Q6 | Odhad tok/s Q2–Q6 | Silná stránka v testu | Hlavní slabina / verdikt |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| **gemma4:latest** | 6/6 | 3,8 | **2,8** | 394,7 s (6:35) | 65,8 s | ≈ 9,3 | ≈ 9,5 | Nejlepší [překlad](translate_g4_4.md) a [entropie](entropy_g4_6.md) | **Nejlepší kompromis této sady**; smyšlený král, slabá diagnostika. |
| **gpt-oss:latest** | 6/6 | **4,3** | 2,7 | 787,4 s (13:07) | 131,2 s | ≈ 3,1 | ≈ 3,4 | Nejlepší [TCP/UDP](compare_gpt_2.md) | Nejpomalejší; závažné chyby historie i HTTP 404. |
| **qwen3.5:latest** | 6/6 | 4,0 | 2,2 | 413,0 s (6:53) | 68,8 s | ≈ 5,6 | ≈ 5,6 | Nejkratší čekání na Q3 | Proti Gemma zde horší kvalita i celkový čas; slabý překlad a historie. |
| **qwen3.5:4b** | 6/6 | 4,2 | 1,8 | **328,3 s (5:28)** | **54,7 s** | ≈ 9,5 | ≈ 9,5 | Nejrychlejší sada, Q2 a Q4 | Nejnižší správnost; zásadní výmysly v historii a chybný technický návod. |
| `ornith:9b` | 0/18 pokusů | — | — | — | — | — | — | Nehodnoceno | Model nenalezen; žádná dokončená inference. |
| `qwen3.8:latest` | 0 | — | — | — | — | — | — | Nehodnoceno | V dodaném logu není test tohoto modelu. |

---

kredit: "zpracovala GPT-6 Astra Střední"

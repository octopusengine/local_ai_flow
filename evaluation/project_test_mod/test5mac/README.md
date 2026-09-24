# Vyhodnocení test5mac: pět modelů na Macu M5 Max, 36 GB RAM

Vyhodnocení tří reportů pořízených 24. 9. 2026. Každý flow obsahuje pět otázek pro pět modelů: obecnou faktografii (flow 1), fyzikální nerdovské otázky (flow 2) a školní biologii, elektroniku, zeměpis a matematiku (flow 3). Bodování je ruční posouzení konkrétního odevzdaného textu; rychlost do bodů nevstupuje. Nejde o univerzální pořadí modelů.

## 1. Hodnocení podle odpovědí

### Obecné otázky – flow 1

**Nejlepší celkově: `ornith-1.5:35b`.** Jako jediný správně upozornil, že „výprosa“ je samostatný právní institut, a odpověď k Čapkovi rozumně odmítla vynucenou třetí položku; i tak však zaměnil výprosu za výpůjčku. V historii a cestování má chyby a jazykové deformace. **Slušný poměr rychlost/správnost: `gemma4:26b`** – je rychlá a slušně pokryla cestu i základ roku 1968, ale právo i Čapek jsou podstatně chybné. Pokud je důležitější celková správnost než čas, Ornith je bezpečnější volba, ale stále vyžaduje ověření.

V právní otázce všichni kromě částečně Ornithu míchají zápůjčku, výpůjčku a výprosu; `qwen3.5:latest` navíc výprosu popsal nesprávně jako půjčku na spotřebu. U Prahy–Ostravy většina trefuje řádově realistické časy, ale Qwen 27B tvrdí nemožných 2,5 hodiny autem a přidává chybná tvrzení o dopravcích. U roku 1968 je jádro (Pražské jaro a invaze) obecně rozpoznáno, přesto Qwen 27B vymýšlí „Alexeje Čepíka“ a další události, Gemma má silně poškozenou češtinu. U Čapka jsou nejhorší Qwen 3.5 a Gemma; opakují smyšlené tituly. Qwen 3.8 27B zná R.U.R., ale přidává nesouvisející Hordubala a chybná tvrzení o Věci Makropulos. Ornith korektně zmíní R.U.R. a Válku s mloky.

### Fyzika a matematika – nerdovské otázky

Za nerdovský vzorek považuji fyzikální flow 2 a doplňující elektroniku a matematiku z flow 3 (6 věcných otázek). **Nejlepší: `qwen3.8:27b-mlx`**, těsně před Ornith. Jeho správné a rozsáhlé výklady entropie, Maxwellových rovnic a Hawkingova záření převáží nad několika odbornými nepřesnostmi; elektronika i matematika jsou velmi dobré. **Nejlepší poměr rychlost/správnost: `ornith-1.5:35b`**. Má srovnatelnou kvalitu a je rychlejší na fyzikálních otázkách, přestože v nerovnoměrné Verlindeho odpovědi podává méně úplný výklad. Qwen 27B je robustnější volba pro podrobnou odpověď; Ornith pro rychlejší, stále kvalitní výstup.

`qwen3.5:latest` odpovídá na fyziku asi o třetinu rychleji než Qwen 27B, ale výrazně hůř: dlouhé texty skrývají chybné nebo přehnaně sebejisté závěry o Verlindem a Hawkingově záření. `qwen3.8:latest` má v nerdovských odpovědích překvapivě nízké skóre: na rozdíl od 27B varianty chybně popisuje vztah entropie k informaci i experimentální stav, byť správně vypisuje Maxwellovy rovnice. Gemma je nejrychlejší či téměř nejrychlejší, ale fyzikální skóre je nejnižší. V jednoduché matematice a elektronice jsou všechny modely podstatně lepší než v teoretické fyzice.

### Školní otázky – flow 3

`qwen3.5:latest`, Ornith a Qwen 27B jsou zde si blízcí. Qwen 3.5 nejvyrovnanější; Ornith má nejlepší nebo téměř nejlepší jednoduché výpočty a je rychlý; Qwen 27B nabídne nejpodrobnější řešení, ale občas přidá zbytečné či rozporné vysvětlování. Gemma odpovídá rychle a obstojně v biologii a zeměpisu, ale matematický výklad obsahuje chyby. `qwen3.8:latest` správně vysvětluje biologii, ale v testu je nejpomalejší a jeho dlouhé odpovědi jsou místy rozvláčné.

## 2. Modely: kvalita a rychlost

Doba je průměr časů Q2–Q5 v sekundách z daného flow, zaokrouhlená na sekundu. Zahrnuje generování celé odpovědi, proto ji ovlivňuje i délka textu. `1_1`, `2_1`, `3_1` jsou krátký init „agama“ a nejsou zahrnuty.

| Model | Obecné body /4 | Nerd body /6 | Školní body /4 | Flow 1 s | Flow 2 s | Flow 3 s | Zhodnocení |
|---|---:|---:|---:|---:|---:|---:|---|
| qwen3.5:latest | 33 | 81 | 90 | 13 | 28 | 17 | Nejvyrovnanější školní výsledky; obecná faktografie slabá, fyzika proměnlivá. |
| qwen3.8:latest | 58 | 71 | 84 | 26 | 68 | 36 | Lepší obecné jádro, ale fakta o Čapkovi a části fyziky jsou nespolehlivá; dlouhé časy. |
| qwen3.8:27b-mlx | 33 | 85 | 89 | 15 | 40 | 20 | Nejlepší nerdovský obsah; obecné otázky zatěžují halucinace a faktické chyby. |
| gemma4:26b | 47 | 72 | 84 | 9 | 18 | 11 | Rychlá a použitelná na jednodušší úkoly; nízká důvěra v právo, Čapka a teorii. |
| ornith-1.5:35b | 62 | 82 | 92 | 4 | 17 | 9 | Nejlepší obecný výsledek, velmi rychlá a kvalitní; právní odpověď má zásadní záměnu. |

Skóre v souhrnných sloupcích je průměr bodů věcných otázek příslušného flow. Každé otázce náleží stejná váha. Všech pět modelů má v každém reportu dokončený výstup; init „agama“ splnily Qwen 3.5, 27B a Ornith, zatímco Qwen 3.8 latest a Gemma odpověděly `no`.

### Jednotlivá hodnocení

- **`qwen3.5:latest`** – Silné vysvětlení rostlinného dýchání, elektronika i matematika. Ve fyzice správný základní vzorec často doprovází chybnou interpretací. Obecné odpovědi k právu a Čapkovi halucinují. Rychlý v obecných a školních otázkách.
- **`qwen3.8:latest`** – V právní otázce správně rozliší zápůjčku od výpůjčky, ale mine výprosu. Cestu a rok 1968 pokrývá částečně, Čapek je chybný. Fyzikální výklady jsou velmi dlouhé, ale kvalita nepřekonává 27B variantu. Init pokyn nesplnil.
- **`qwen3.8:27b-mlx`** – Nejlepší fyzikální výklad v tomto vzorku; správně zachází s Maxwellovými rovnicemi a předkládá nejlepší řešení matematiky. Má závažné faktické chyby v cestování, historii i právu. Na Macu je navzdory velikosti relativně svižný, nikoli nejrychlejší.
- **`gemma4:26b`** – Rychlá napříč flow, dobré jádro některých školních vysvětlení. Právní definice zápůjčky jsou chybné, Čapek obsahuje smyšlené tituly a v historii deformovanou češtinu. Ve fyzice podává méně úplné či zavádějící výklady.
- **`ornith-1.5:35b`** – Nejlepší skóre v obecných i školních otázkách a druhý nejlepší nerdovský výsledek; mimořádně krátké časy. Největší jednotlivý problém je záměna výprosy a výpůjčky. Odpovědi jsou stručnější, což je pro rychlost výhodné, ale někdy snižuje úplnost.

## 3. Konzistence výstupů a vliv nenulové teploty

V této složce je **jen jeden běh každého modelu v každém flow**. Kvalitu ani přesnou textovou reprodukovatelnost proto nelze vyhodnotit mezi opakovanými reporty. Seed 42 při nenulové temperature neznamená automaticky různorodost odpovědí; stejný seed a stejné podmínky mohou dát stejný vzorek. Zároveň nezaručuje stejný výstup mezi modely či běhy s jinými podmínkami. Rozdíly mezi pěti modely nelze nazývat nekonzistencí jednoho modelu.

Vnitřní konzistence odpovědi je samostatný problém: Qwen 3.5 si při řešení odmocnin nejprve chybně spočítá kořen 4, následně chybu opraví a správný výsledek uzavře jako 2. Qwen 3.8 latest při vysvětlování Čapka nejprve vytvoří neexistující tituly a pak se sám snaží korigovat smyšlenou premisu. Takové samoopravy jsou lepší než neopravená chyba, ale snižují důvěru i čitelnost. Pro skutečný test konzistence by bylo třeba spustit každý model opakovaně se stejným promptem a zaznamenat úplné nastavení včetně teploty, seedu, verze flow a identifikátoru modelu.

## 4. Přehled bodů po otázkách (1–99)

Body hodnotí správnost, splnění zadání, úplnost a srozumitelnost. 90–99 znamená téměř správnou a úplnou odpověď; 75–89 převážně správnou s výhradami; 50–74 použitelné jádro, ale významné chyby; 25–49 silně nespolehlivou; 1–24 převážně chybnou. Skóre nejsou procenta správných vět. Rozdíl pár bodů nepředstavuje přesnou vědeckou míru. `1_1` atd. hodnotí pouze init odpověď `agama` (99), `no` (1).

| Otázka | qwen3.5:latest | qwen3.8:latest | qwen3.8:27b-mlx | gemma4:26b | ornith-1.5:35b |
|---|---:|---:|---:|---:|---:|
| 1_1 init | 99 | 1 | 99 | 1 | 99 |
| 1_2 právo | 8 | 78 | 45 | 40 | 35 |
| 1_3 Praha–Ostrava | 35 | 75 | 35 | 78 | 70 |
| 1_4 rok 1968 | 62 | 55 | 20 | 55 | 65 |
| 1_5 Karel Čapek | 25 | 25 | 30 | 15 | 78 |
| 2_1 init | 99 | 1 | 99 | 99 | 99 |
| 2_2 entropie černé díry | 88 | 60 | 88 | 72 | 82 |
| 2_3 Verlinde | 62 | 55 | 78 | 52 | 60 |
| 2_4 Maxwellovy rovnice | 78 | 76 | 85 | 68 | 80 |
| 2_5 Hawkingovo záření | 65 | 55 | 82 | 74 | 82 |
| 3_1 init | 99 | 1 | 99 | 99 | 99 |
| 3_2 biologie | 91 | 84 | 88 | 86 | 90 |
| 3_3 elektronika | 96 | 92 | 94 | 95 | 98 |
| 3_4 zeměpis | 75 | 74 | 90 | 82 | 88 |
| 3_5 matematika | 99 | 85 | 85 | 73 | 91 |


## 5. Srovnání s test5 na CPU / 16 GB RAM PC

Předchozí [test5/README.md](../test5/README.md) hodnotil jiné sestavy a v několika případech jiné varianty modelů. Přímé pořadí tedy není kontrolovaný benchmark. V test5 na obecné faktografii nebyl spolehlivý vítěz; na tomto Macu Ornith dosahuje nejlepšího relativního skóre, ale právo stále nezvládl. Fyzika byla v test5 nejsilnější u Ornithu a GPT-OSS; v test5mac se k nim výbornými odpověďmi přidává Qwen 27B MLX. Školní elektronika a matematika jsou silné v obou sadách.

Nejvýraznější praktický rozdíl jsou časy: na M5 Max 36 GB jsou kompletní odpovědi nejčastěji v jednotkách až desítkách sekund. V předchozím PC testu nerdovské odpovědi běžně zabíraly stovky sekund (např. Qwen 3.5 4B zhruba 215–243 s na otázku ve flow 2, Qwen latest přibližně 347–359 s, Ornith okolo 412 s). Modelové varianty ale nejsou stejné: zde jsou Qwen 3.8 a 27B MLX, Gemma 26B a Ornith 35B; dříve Qwen 3.5, Gemma latest a Ornith 9B. Časový náskok proto ukazuje zkušenost s touto sestavou a těmito modely, ne čistý poměr výkonu M5 Max proti CPU.


# Mozek octomilky – jednoduchá 2D vizualizace

Spuštění z kořene projektu:

```powershell
.\venv\Scripts\python.exe neuron_viewer.py
```

Používá již instalované pygame, numpy, pandas a pyarrow. Jejich instalaci
pokrývá `requirements-simulation.txt`. Nevyžaduje stahování dat ani běžící Brian 2.
Při startu načte celou síť; potřebuje přibližně 1–2 GB volné RAM.

## Ovládání

- Světlo / tma pro každé oko se vzájemně vylučují. Tlačítko „Obě oči“
  přepíná obě současně. Tma nastaví světelný vstup na nulu, nemodeluje OFF dráhu.
- „Vůně cukru“ zapne obě čichové skupiny z existujícího `interface.json`.
  Jde o obecný umělý čichový podnět převzatý z koncepce `pygame_fly.py`;
  mapování není specifické pro chemickou látku. Chuťové neurony cukru
  (`sugar`, kontakt) tento checkbox nebudí.
- Tři posuvníky u levého oka, pravého oka a vůně mění **podíl přímo buzených
  vstupních neuronů** v rozsahu 0–100 %. Výchozí podíl je 10 %. Pod každým
  je uvedeno zvolené množství vstupů. U vůně platí procento zvlášť pro levou
  a pravou skupinu; uvedený počet je jejich součet.
- Samostatný posuvník síly mění společnou intenzitu buzení vybraných neuronů.
  Mezera pozastaví vývoj, N provede
  jeden krok a ponechá pauzu, R vynuluje aktivitu i podněty.
- „Rychlost“ přepíná požadované 2 / 6 / 12 kroků za sekundu. Při pomalejším
  výpočtu běží simulace pomaleji; nepřeskakuje části sítě.
- Kliknutím na neuron se zobrazí jeho root ID, typ, skupina, strana a aktivita.
  Při překryvu se vybere jedno nejbližší ID; text se aktualizuje i v pauze.
- Checkbox skutečných XY přepíná prostorové zobrazení. Checkbox pozadí
  ovlivňuje mikroskopickou maketu, u skutečných XY se fotografie nezobrazuje.

Šedý bod má přesně 1×1 pixel okna, aktivní bílý / žlutý bod 2×2 pixely.
Okno má pevně 1280×820, aby se neměnilo měřítko pixelů. Počty aktivních jsou
počty ID, nikoli viditelných bodů: neurony se mohou překrývat.

## Data a návaznost na dosavadní pokusy

- `data/fly_annotations/model_neuron_annotations.csv`: všech 138 639 ID,
  anatomické skupiny, strany, typy a referenční souřadnice.
- `data/fly_annotations/interface.json`: stejné `visual_left`, `visual_right`,
  `odor_left`, `odor_right` jako v `fly_connectome.py` a `pygame_fly.py`.
- `external/Drosophila_brain_model/Connectivity_783.parquet`: všech
  15 091 983 orientovaných spojů včetně znamének a vah. Tento soubor už je
  v projektu; samotné `./data` kompletní spoje neobsahuje. Konce spojů se
  ověřují podle skutečných ID, nikoli předpokládaného pořadí řádků.
- `img/adult-fruit-fly-brains-microscopy.jpg`: horní izolovaný mozek slouží
  jako silueta pro schematické rozmístění. Maketa není segmentace ani registrace
  jednotlivých neuronů na mikroskopický snímek. Body mají skutečná ID, jejich
  polohy v tomto režimu jsou deterministicky náhodné uvnitř odpovídající oblasti.

Alternativní projekce používá `pos_x`, `pos_y` z anotací, sloučí osu Z
a přizpůsobí osy ploše. Je to projekce referenčních bodů, nikoli celých
neuronových arborizací. Motorické a sestupné neurony jsou v obou režimech
přesunuté do odděleného dolního panelu a seskupené podle strany. Tento panel
není úplná ventrální nervová páska ani přesná mapa svalů.

Jiné lokální soubory lze předat přes `--data C:\cesta\data` a
`--connections C:\cesta\Connectivity_783.parquet`; musí mít shodná ID/verzi.

## Co znamená aktivita

Tento prohlížeč používá **zjednodušený diskrétní model aktivity** pro rychlou
interakci s celou sítí. Nepoužívá membránové rovnice, Poissonovy vstupy ani
spike monitor z existujícího Brian 2 experimentu. Výsledky obou modelů nelze
číselně srovnávat a krok zde nemá kalibrovaný význam v biologických milisekundách.

Při výchozím nastavení pro každý neuron: sečte podepsané příchozí váhy krát aktivitu zdrojů,
vydělí součet odmocninou součtu absolutních příchozích vah (nejméně 1), aplikuje
`tanh(0.18 * součet + 3 * síla_vstupu - 0.003 - 4 * adaptace)` a smísí jej s předchozím stavem
v poměru 0,4 : 0,6. Záporný výsledek se ořízne na nulu, horní mez je 1.
Hodnoty menší než 0,0001 se vynulují, zvýraznění začíná na 0,01.
Adaptace se aktualizuje po každém kroku jako `0.98 * adaptace + 0.02 * aktivita`.
Déle aktivní neuron má tím vyšší práh odezvy; adaptace po zhasnutí postupně
ustupuje. Reset vynuluje aktivitu i adaptaci.
Inhibiční spoje se tedy nezaměňují za excitační a účinek prochází skutečnými
směrovanými spoji. Vstup se nepropíše přímo do motorického panelu.

Zhasnutí automaticky nemaže stav sítě: aktivita postupně doznívá. Adaptace
tlumí dlouhodobě opakované buzení. Výchozí nastavení je otestované na lokální
síti; stabilita není zaručena pro libovolné změny parametrů či podnětů. Pro
porovnávání izolovaných pokusů použijte R před novým podnětem. Žlutá pouze označuje aktivní ID anotované
jako `descending` nebo `motor`, nikoli předpověď konkrétního pohybu.

## Ověření

```powershell
.\venv\Scripts\python.exe -m unittest test_neuron_viewer test_neuron_recording test_neuron_viewer_settings test_neuron_damping -v
.\venv\Scripts\python.exe neuron_viewer.py --smoke-test
.\venv\Scripts\python.exe verify_neuron_damping.py
```

Testy prověřují směrovost a znaménka spojů, postupný průchod do motorického
výstupu, izolaci vstupů, shodu sparse výpočtu s maticovým výpočtem, útlum na
acyklické i rekurentní síti, podprahové buzení, ovládání i rozměry pixelů. Smoke test načte kompletní lokální
data a samostatně vyzkouší tmu, levé oko, pravé oko, čich a kombinaci.
Výstup uloží do `results/neuron_viewer/smoke.json`, náhledy do `preview.png`
a `preview_xy.png`. Tyto testy ověřují software, nikoli biologickou validitu.

## Reporty a příprava redukovaného modelu

Záznam je standardně **vypnutý** (`"report": false` v `neuron_viewer.json`).
Zapněte jej hodnotou `true` a restartem, nebo přepínačem `--report`.
Při vypnutí se nezakládá žádná relace a tlačítko S žádný report nezapíše.
Každé spuštění se zapnutým záznamem vytvoří vlastní adresář
`results/neuron_viewer/sessions/<čas_UTC>_<unikátní_id>/`. Tlačítko **Uložit
report + návrh redukce** nebo **S** uloží samostatný snapshot. Report se ukládá
také při resetu a běžném ukončení okna. Reset R zahájí nový pokus od nulového
stavu; předchozí pokus zůstane uložený a souhrn za celou relaci se nemaže.
Pauza nepřidává vzorky. Při změnách podnětů bez resetu pokračuje tentýž pokus.

Adresář lze změnit přes `report_dir` nebo `--reports cesta`. Název hlavního
JSON reportu určuje `report_file` (např. `"pokus_svetlo.json"`), případně
`--report-file pokus_svetlo.json`; čitelný Markdown má stejný základ názvu.
Snapshoty zůstávají v unikátních podadresářích, aby se pokusy nepřepisovaly.
Ostatní pomocné CSV/JSON soubory si zachovávají názvy uvedené níže.
Přepínač `--no-record` záznam vypne i přes `report: true` v konfiguraci.
Při chybě zápisu kroků se simulace zastaví a vzniklý report
je označený jako neúplný, bez návrhu odstranění neuronů.

Soubory v relaci:

- `timeline.jsonl`: průběžně zapisovaný podnět a intenzita pro každý dokončený
  krok, čísla kroku v síti i relaci, reset, počty aktivních neuronů a souhrn
  motorické aktivity. Podněty popisují nastavení při výpočtu, nikoli dobu
  kliknutí v pozastavené aplikaci. Jeden krok nemá biologickou časovou jednotku.
- `initial_activity.npy` a `neuron_ids.json`: počáteční stav a přesné pořadí ID.
- `initial_adaptation.npy`: počáteční adaptace, nutná pro reprodukci nové dynamiky.
- `trial_XXXX.csv`: statistiky jednotlivých dokončených pokusů.
- `latest.json`: odkaz na poslední kompletně uložený report.
- `report_.../report.json` a `report.md`: metadata a čitelný souhrn; obsahují
  modelové parametry, SHA-256 zdrojových dat i implementace, prahy, počet
  zaznamenaných kroků a rozsah pokusů. Snapshot se nepřepisuje.
- `report_.../neurons.csv`: **všechny neurony**, skutečné ID a anotace,
  maximum, průměr a součet aktivity, počet kroků nad nastaveným prahem (výchozí 0,01), počet
  nenulových stavů, přijetí signálu, předchozích nenulových stavů vstupujících
  do propagace a přímého buzení. První/poslední aktivace je číslovaná od 1
  v celé relaci; `-1` znamená, že nadprahová aktivace nebyla pozorována.
- `excited_neurons.csv`: pouze ID alespoň jednou nad prahem, se stejnými
  statistikami. `current_trial.csv` obsahuje dosud probíhající pokus.
- `reduction_candidate.json`: **návrh**, seznam ponechaných ID a kandidátů
  na odstranění. ID v JSON jsou řetězce, aby nedošlo ke ztrátě přesnosti.

„Účast“ je pro návrh širší než bílý pixel: zahrnuje jakýkoli nenulový
uložený stav, přímé buzení a přijetí nenulového signálu přes spoj. Příchozí
příspěvky se sledují v absolutní hodnotě před vzájemným odečtením, takže
inhibiční vstup ani přesné vyrušení buzení a inhibice nezmizí z evidence.
Unie se vytváří přes všechny pokusy **této relace**. Všechna vstupní ID
z `interface.json` a všechny motorické/sestupné neurony jsou navíc chráněné,
i když byly neaktivní. Prázdný nebo neúplný záznam nenavrhuje žádné odstranění.

Neúčast znamená jen „nepozorováno v zaznamenaném protokolu tohoto modelu“.
Report neprokazuje kauzalitu, nezaznamenává výboje a podprahové hodnoty pod
numerickým cutoffem mohou zaniknout. Detailní časová řada každého neuronu
se zatím neukládá; přesné podněty, počáteční stav a identifikace implementace
slouží jako podklad pro deterministické přehrání. Statistiky zabírají paměť
úměrnou počtu neuronů, nikoli délce běhu. Timeline roste s počtem kroků.
Při násilném ukončení procesu zůstane timeline a poslední ruční/resetový
snapshot; neexportované neuronové statistiky jsou pouze v paměti.

### Druhá fáze – připravený kontrakt, zatím bez odstranění neuronů

Budoucí reduktor vezme unii účastníků z vybraných kompatibilních reportů,
ponechá chráněné rozhraní a vytvoří indukovaný podgraf skutečných spojů.
Zachová jejich znaménka, váhy a **původní normalizační konstanty** uložené
v `neurons.csv`: přepočet normalizace pouze ze zbylých spojů by změnil model
i při odstranění neuronů s nulovou aktivitou. Originální data se nepřepisují.

Před přijetím redukce je potřeba přehrát stejné protokoly na plné a zmenšené
síti, porovnat motorické výstupy i časový průběh aktivity a přidat jiné
intenzity, kombinace, pořadí a délky podnětů včetně tmy a doznívání. Kritéria
a tolerance shody patří až k validaci druhé fáze. Současný export tuto
validaci nedělá a **nevytváří ani nespouští redukovanou síť**.

## Nastavení `neuron_viewer.json`

Soubor se načítá při startu; úpravy platí po restartu. Posuvníky mění pouze
aktuální běh a JSON automaticky nepřepisují. Reset vynuluje stav a vypne
podněty, ale ponechá zvolené podíly, intenzitu a modelové parametry.

| Nastavení | Výchozí hodnota | Význam |
|---|---|---|
| `report` | `false` | Záznam a export reportů |
| `report_dir` | `./results/neuron_viewer/sessions` | Nadřazený adresář relací |
| `report_file` | `report.json` | Název hlavního reportu, bez cesty, přípona `.json` |
| `left_input_percent`, `right_input_percent`, `odor_input_percent` | `10` | Podíl vstupů, 0–100 % |
| `input_selection_seed` | `42` | Opakovatelný výběr konkrétních vstupních ID |
| `intensity` | `0.65` | Síla buzení vybrané podmnožiny, 0–1 |
| `left_light`, `right_light`, `odor` | `false` | Zapnuté podněty při startu |
| `steps_per_second` | `6` | Požadovaná rychlost, 1–30 kroků/s |
| `playing`, `photo`, `anatomical` | `true`, `true`, `false` | Běh, pozadí, skutečné XY |
| `activation_threshold` | `0.01` | Práh zvýraznění a reportované excitace, neovlivňuje šíření |
| `retention` | `0.6` | Paměť předchozí aktivity, 0–0,99; menší hodnota = rychlejší odezva a doznívání, nová odpověď má váhu `1-retention` |
| `propagation_gain` | `0.18` | Zisk síťového šíření, 0–0,99; vyšší hodnoty mohou způsobit samobuzení |
| `drive_gain` | `3.0` | Zisk přímého vstupu před `tanh` |
| `response_threshold` | `0.003` | Základní práh vlastní odezvy před `tanh` |
| `activity_cutoff` | `0.0001` | Numerické ořezání malých aktivit |
| `adaptation_strength` | `4.0` | Přírůstek prahu za jednotku adaptace; 0 adaptaci vypne |
| `adaptation_retention` | `0.98` | Paměť adaptace, 0–0,99; vyšší hodnota zpomaluje její vznik i ústup |
| `data_dir`, `connections_file` | Lokální cesty projektu | Anotace a spoje |

Neznámé klíče a neplatné hodnoty jsou odmítnuty s chybou. Relativní cesty
v JSON se vztahují k adresáři **konfiguračního souboru**, ne k pracovnímu
adresáři terminálu. Přepínač `--config cesta.json` načte jiné nastavení.
Cesty z CLI mají přednost a vztahují se k pracovnímu adresáři terminálu.

Výběr pro každý kanál je pevné, podle ID a seedu reprodukovatelné pořadí.
Při podílu `p` se vezme prvních `floor(N*p/100)` neuronů. Zvýšení procenta
tedy přidává neurony a nemění stávající výběr; nula nebudí žádný, 100 % všechny.
Malé skupiny mají hrubší kroky: např. 10 % z 32 znamená 3 neurony.
Report ukládá skutečné nastavení, seed a procenta v každém kroku, takže je
možné stejný výběr při pozdějším porovnání reprodukovat.

**Podíl vstupů není limitem aktivity celé sítě.** I několik buzených vstupů
může přes rekurentní spoje aktivovat mnoho dalších neuronů. Pro kontrolu
je v okně uvedeno skutečné procento aktivních ID (vizuální plocha bílých
pixelů může kvůli velikosti 2×2 a překryvům působit jinak). Při porovnávání
podílů resetujte R stav sítě, aby výsledek neobsahoval předchozí aktivitu.
Úprava modelových zisků mění dynamiku, proto se její hodnoty ukládají do reportu.

### Přenos mezi oblastmi a útlum – model verze 4

Původní verze normalizovala vahami pod odmocninou a používala síťový zisk 2.
Na plné lokální síti při 3 % vstupů a intenzitě 3 % bylo po 40 krocích
37 867 neuronů nad prahem; po dalších 40 krocích bez podnětu stále 38 061.
Takový výsledek byl artefaktem zjednodušené dynamiky, ne dokladem reakce mozku.

Následná příliš konzervativní normalizace celým součtem vah potlačila i
přenos očí do centrálního mozku. Aktuální verze proto používá odmocninovou
normalizaci s podstatně menším ziskem 0,18 a dynamickou adaptací. Silný vstup
může projít mezi oblastmi; následná adaptace omezuje dlouhodobé opakované buzení.
Nevkládáme žádné nové spoje, přímé buzení centrálních neuronů ani motorických
výstupů. Parametry se ladily podle přenosu **i** odeznění po vypnutí.
Nejde o obecný matematický důkaz stability: po změně JSON je potřeba znovu
vyzkoušet více podnětů a následné zhasnutí. Předchozí garance kontrakce modelu
verze 3 pro tuto dynamiku neplatí.

Prahy mají různé role: **response_threshold mění výpočet**, zatímco
**activation_threshold pouze klasifikuje stav** pro vykreslení a report.
Zvýšením zobrazovacího prahu se nestabilita modelu neopravuje.
`activity_cutoff` odstraňuje malé nenulové stavy z výpočtu a také může ovlivnit
účast neuronů v přípravě redukce. Menší podnět neznamená automaticky inhibici;
inhibiční vliv závisí na znaménkách a aktivitě konkrétních spojů. Dostatečně
slabý vstup však nyní zůstane pod prahem a klidně se neprojeví vůbec.

Ověření `verify_neuron_damping.py` používá 120 kroků podnětu a dalších 200
kroků bez podnětu. Samostatně testuje slabé, střední a silné oči i vůni,
sleduje maximum a první aktivaci v každé oblasti a požaduje přenos do centra
i motoriky při silném očním a čichovém vstupu a nulovou aktivitu na konci
doznívání. Výsledky s uloženými parametry jsou v
`results/neuron_viewer/damping_verification.json`.

Pod mozkem se zobrazují okamžité počty a maxima od resetu: levá optika,
centrální mozek, pravá optika a motorické výstupy. Maxima zachytí i krátké
průchody aktivity, které by jinak v animaci zanikly. Centrální počet zahrnuje
jen skutečnou anotaci `super_class=central`, nikoli přímo buzené čichové vstupy.
Report ukládá `active_by_region` v každém kroku a `peak_active_by_region`
a `ever_active_by_region` v souhrnu. Zařazení do oblasti není důkazem, že
konkrétní motorický neuron dostal signál právě přes konkrétní centrální neuron;
takový závěr by vyžadoval trasování příspěvků po jednotlivých spojích.

Pozor: 3 % z 32 čichových neuronů na každé straně se při zaokrouhlení dolů
rovná nule.
Pro alespoň jeden čichový vstup na stranu nastavte nejméně 4 %.

Jde o konzervativní stabilizaci vizualizačního modelu, nikoli kalibraci
biologické odpovědi ani záruku konkrétní motorické reakce. Publikovaný
[model Shiu et al.](https://www.nature.com/articles/s41586-024-07763-9) používá
leaky integrate-and-fire neurony a upozorňuje mimo jiné na omezení způsobená
nezahrnutím bazální inhibice při nulové klidové aktivitě. Pro biologické
závěry je potřeba ověřit dynamiku a podněty vůči datům, případně navázat na
existující Brian 2 experiment. Reporty modelu verze 4 se nesmí pro účely redukce
bez ověření slučovat se starými reporty; liší se normalizace, dynamika i prahy.

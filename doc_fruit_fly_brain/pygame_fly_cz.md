# Muška, konektom a prostředí: návod k pokusům

Pohyb se nyní ovládá checkboxem **`Motion (brain drives body)`**. Zaškrtnutý
aplikuje výstupy mozku na tělo, nezaškrtnutý pouze měří odezvy. Výchozí stav
je **zapnutý**, uložený jako `"motion_enabled": true` v `pygame_fly_motor.json`.
Tento soubor obsahuje přepínač pohybu, `adapter_gain` a řádky `forward` a `turn`.
Starší označení Motion ON/OFF v příkladech níže znamenají zaškrtnutí/odškrtnutí.

Tento dokument rozšiřuje [anglický návod](pygame_fly.md). Popisuje současnou
implementaci `pygame_fly.py`; názvy tlačítek zůstávají anglické, aby odpovídaly
programu. Cílem je zkoušet vztah **podnět → aktivita sítě → výstup → pohyb**.
Učení zatím není zapnuté a váhy spojů se během pokusu nemění.

## 1. Co vlastně simulujeme

Používáme model neuronové dynamiky nad konektomem FlyWire 783. Anatomická síť
říká, které neurony jsou propojené, model určuje vývoj jejich stavu a vznik
výbojů. Vstupy budíme umělými impulzy a vybrané výstupy převádíme jednoduchým
řadičem na pohyb po mřížce. Tento řadič jsme navrhli my; není to ověřené
přiřazení konkrétních mozkových neuronů ke svalům mušky.

Svět má 30 × 30 polí. Fialové kolečko představuje tělo, oranžové body cukr.
Při kontaktu s cukrem se tělo i jeho nákres vpravo zbarví zeleně, ihned i po
ručním položení cukru pod mušku. Zelená trvá po dobu aktuálního kontaktního
signálu, potom se vrátí fialová. V pauze se čas signálu neposouvá. Barva označuje
vstupní kontakt, nikoli prokázanou aktivaci výstupních neuronů.
Obrázek nohou pouze znázorňuje společný pohybový povel. Křídla nejsou napojená.
Kompletní ventrální nervová páska (VNC), jednotlivé svaly a fyzika letu chybějí.
Proto případný pohyb znamená, že pracuje naše spojení sítě s řadičem, nikoli
že jsme reprodukovali přirozenou chůzi nebo let.

**Chuťový vstup cukru se aktivuje pouze při kontaktu.** Cukr nyní navíc vydává
umělou vůni ve svém okolí. Oči stále vidí jen umělou texturu podlahy a stěny,
nikoli oranžové body ani žluté značení vůně. Vůně dává informaci o blízkosti,
nyní se snímá zvlášť v sousedním poli vlevo a vpravo od těla podle jeho natočení.
Nejde tedy o dvě kopie intenzity na poli, kde muška stojí. Natočení se zaokrouhluje
na stejný ze čtyř směrů jako pohyb po mřížce; mimo hranice je vzorek nulový.

### Vůně cukru a žluté okolí

V JSON nastav `sugar_odor_radius` na 1, 2 nebo 3; výchozí je **2**. Jde o pole
mřížky, nikoli obrazové pixely. Počítá se čtvercová vzdálenost, tedy maximum
vodorovné a svislé vzdálenosti od cukru:

| Poloměr | Oblast | Síla vůně |
|---|---|---|
| 1 | 3 × 3 | Střed a první prstenec 100 % |
| 2 | 5 × 5 | Navíc druhý prstenec 50 % |
| 3 | 7 × 7 | Navíc třetí prstenec 25 % |

Za zvoleným poloměrem je síla nula. Překryv cukrů používá nejsilnější signál,
nesčítá se. Čichové strany snímají dvě různá sousední pole. Žlutý nádech mapy
má maximální krytí 18 %, dále 9 % a 4,5 % — je pouze pomůckou pro uživatele.
Po sebrání zdroj vůně zmizí; trvající chuťový kontakt je samostatný signál.

Checkboxy **`Left odor enabled` / `Right odor enabled`** zapínají příjem vůně
prostředí pro danou stranu. Výchozí jsou oba zapnuté (`left_odor: true`,
`right_odor: true`). Zaškrtnutý neznamená stálých 100 %: intenzitu určuje okolí.
Vypnutý posílá 0 %. Původní nucené 100% sondy byly nahrazeny tímto ovládáním.
Řádek `Odor neighbors L / R` ukazuje intenzity v obou snímaných polích.
V 1/20 naše čichové neurony chybějí, a vůně proto síť nebudí.

Zrak má společný checkbox **`Vision`**, výchozí vypnutý (`eye: false`). Při
vypnutí se nepočítá obraz prostředí ani skalární oční senzory a vizuální vstupy
jsou nulové. Neurony zrakové části však zůstávají v konektomu; nejde o jejich
odstranění ani záruku velkého zrychlení celé simulace. Pro pohled očima a
všechny zrakové pokusy nejdřív zapni `Vision`. Přepínače očí L/R jsou podřízené
tomuto společnému přepínači.

Pro izolované pokusy bez vůně nastav `"sugar_odor_enabled": false` a restartuj.
Přiřazení vůně cukru těmto čichovým neuronům je experimentální, nikoli ověřená
simulace konkrétní chemické látky a jejích receptorů.

## 2. Spuštění a orientace v okně

V adresáři `D:\data_codex\fruit_fly_brain` spusť:

```powershell
.\venv\Scripts\python.exe pygame_fly.py
```

Velikost sítě se načte z konfigurace. Pro jednorázové přepsání:

```powershell
.\venv\Scripts\python.exe pygame_fly.py --size twentieth
.\venv\Scripts\python.exe pygame_fly.py --size fifth
.\venv\Scripts\python.exe pygame_fly.py --size full
```

Výchozí okno má 1360 × 790 px a obsah se při změně rozměrů přizpůsobí.
Po načtení je simulace pozastavená. Jeden dokončený krok je **50 ms modelového
času**, nezávisle na tom, kolik sekund trval skutečný výpočet.

| Ovládání | Účinek |
|---|---|
| `Run` / mezerník | Spustí další kroky; další stisk pozastaví |
| `Step [Enter]` / Enter | Jeden krok a pauza; při probíhajícím kroku se další neřadí do fronty |
| `Reset state` | Nový mozek a svět se stejnými nastavenými seedy |
| `Full`, `Reduced 1/5`, `Reduced 1/20` | Změna sítě, současně reset mozku a světa |
| `Real connections`, `Shuffled targets`, `Direct sensors` | Změna způsobu zpracování, současně reset |
| `Motion ON` | Pohyb je povolený; kliknutím jej vypneš |
| `Motion OFF / assay` | Výstupy se měří, ale nepřenášejí na pohyb |
| Šipky nebo tlačítka `L / R / T / D` | Vnější posun o jedno pole; pozastaví běh a přepne oči na svět |
| `Place sugar under fly` | Položí cukr přímo pod tělo; počkej na dokončení rozběhnutého kroku |
| F12 | Uloží PNG při zapnutém logování |
| Esc | Ukončí aplikaci |

Reset zachovává aktuální obraz, zapnutí očí, ruční čichové sondy, sílu stimulace
a zesílení řadiče. **Reset tedy sám nevytvoří tmu ani nevypne čich.** Před
každým pokusem zkontroluj i tyto ovládací prvky.

### Vnější pohyb a pohled očima mušky

Šipka vlevo nebo `L` posune tělo o jedno pole vlevo, vpravo / `R` vpravo,
nahoru / `T` nahoru a dolů / `D` dolů. Písmena označují tlačítka v okně;
na klávesnici použij kurzorové šipky. Posun nemění natočení těla a nepředstavuje
povel jeho mozku. Na hranici světa se tělo zastaví a aktivuje se dotykový vstup.

Náhled obou očí se ihned aktualizuje v režimu `World`. Vypnuté oko zůstává
vypnuté; pro oba náhledy zapni L i R. Pozoruješ umělou texturu a stěny, cukr
je stále neviditelný. Samotný posun neposouvá modelový čas ani nepočítá mozek.
Stiskni Enter pro odeslání nového pohledu a měření reakce. Pokud chceš tělo
posouvat výhradně ručně, nastav `Motion OFF / assay`.

Při rozběhnutém výpočtu šipka pozastaví další automatické kroky, ale tělo
nepřesune. Po dokončení aktuálního kroku ji stiskni znovu. Vnější pohyby se
zapisují do logu jako `manual_move`, včetně původní a nové polohy.

V levém panelu je prostředí. Uprostřed jsou oční obrazy a vstupy. Vpravo jsou
výstupy a jejich převod na tělo. Oční náhled ukazuje **příští požadovaný vstup**,
zatímco tabulka vstupních událostí a výstupy patří k **poslednímu dokončenému
kroku**. Po změně obrázku proto nejdřív nech dokončit nový krok.

## 3. Co znamenají čísla a barvy

- Bílý pixel žádá maximální frekvenci nastavenou posuvníkem, černý 0 Hz.
  Šedá ji násobí jasem 0–1. Barva obrázku se převádí na jas.
- Fialový pixel v očním náhledu znamená odstraněný neuron. Nepřenáší podnět.
- Číslo 0–1 v přehledu vstupů vyjadřuje požadovanou intenzitu; u oka průměr
  celého původního obrázku. V redukci nemusí odpovídat průměru přeživších pixelů.
- Počet událostí je počet externích Poissonových impulzů do dané skupiny za
  posledních 50 ms. Není to počet všech výbojů mozku ani počet neuronů.
- Výstup `Descending L`, `Descending R` apod. je průměrná frekvence výbojů
  na neuron v této skupině. Například jediný výboj v 50 ms odpovídá u jednoho
  neuronu 20 Hz, ale průměr velké skupiny může být velmi malý.
- `absent` znamená, že ve skupině nezůstal žádný neuron. `0.000` znamená,
  že skupina existuje a průměr je nulový nebo se na tuto hodnotu zaokrouhlil.
- `Active descending neurons` ukazuje jen několik nejaktivnějších sestupných
  neuronů v daném okně. Není to seznam všech aktivních neuronů mozku.
- V `Direct sensors` jsou výstupní čísla umělé hodnoty řadiče, **nikoli Hz**.

Příklad pro odhad vstupu: 100 bílých připojených pixelů při 150 Hz vytvoří
v průměru `100 × 150 × 0,05 = 750` externích impulzů za krok. Jednotlivé kroky
kolísají. Při 0 Hz musí být externí impulzy nulové, ale dříve rozbuzená síť
může ještě pokračovat v aktivitě.

## 4. Full, 1/5 a 1/20 nejsou stejně funkční mozky

| Síť | Neurony | Řádky spojení | Typický čas následného kroku v krátkém lokálním testu |
|---|---:|---:|---:|
| Full | 138 639 | 15 091 983 | 4,49–5,57 s |
| 1/5 | 30 583 | 722 762 | 0,39–0,42 s |
| 1/20 | 6 932 | 35 567 | 0,18–0,22 s |

Načtení a první krok mají další režii. Rychlost se může měnit s aktivitou sítě
a zatížením počítače. U 1/5 se zachovává celé připojené rozhraní a každý pátý
ostatní neuron podle seřazených ID. U 1/20 každý dvacátý neuron celkově, navíc
s ochranou nejsilnějšího vybraného cukerného vstupu. Ten už v aktuálním vzorku
byl, takže ochrana počet nezvýšila.

Spoj zůstane jen tehdy, když přežily oba jeho konce. Jeho původní váha se nemění.
Ztracené cesty se nenahrazují ani nezkracují. **Redukce je rozsáhlé odstranění
neuronů a cest, nikoli zaručeně ekvivalentní komprese mozku.**

| Připojená skupina | Full a 1/5 | 1/20 |
|---|---:|---:|
| Levé / pravé oko | 1 024 / 1 024 | 58 / 58 |
| Čich vlevo / vpravo | 32 / 32 | 0 / 0 |
| Mechanosenzorika vlevo / vpravo | 16 / 16 | 0 / 1 |
| Cukerné vstupy | 20 | 1 |
| Sestupné vlevo / vpravo / střed | 645 / 646 / 8 | 39 / 31 / 1 |
| Motorické neurony hlavy | 106 | 9 |
| MN9, zahrnutý i v předchozí skupině | 1 | 0 |

To jsou počty našeho připojeného rozhraní. Celý model obsahuje 16 351 senzorických
neuronů, z nichž je 10 855 zrakových, 2 279 čichových, 343 chuťových a 2 636
mechanosenzorických; další patří menším skupinám. Ne všechny přímo stimulujeme.

### Proč jsou PNG u 1/20 pořád podobná

Je možné, že oči dostávají impulzy, ale aktivita nedojde k sestupným výstupům.
Pak se tělo nepohne, pohled na svět se nezmění a další PNG bude téměř stejný.
Přesto mohou mezi kroky kolísat počty vstupních impulzů či vnitřních výbojů.
V logu hledej `input_events`, `total_spikes`, `active_neurons` a `outputs`.

Samotná změna pohybu nebo obrázku není spolehlivou mírou aktivity mozku. Stejná
PNG proto nejsou automaticky chyba ukládání. Interval jsme zvýšili na 50 kroků;
záznam číselné odezvy se tím neředí.

## 5. Konfigurace a ukládání

Soubor [pygame_fly.json](../pygame_fly.json) se čte při startu. Po editaci aplikaci
restartuj. V JSON se píše `true` / `false` malými písmeny a nejsou povolené komentáře.
Neznámé názvy parametrů a neplatné hodnoty program odmítne.

| Parametr | Výchozí hodnota | Co lze zkoušet |
|---|---|---|
| `network_size` | `full` | `full`, `fifth`, `twentieth`; argument `--size` má přednost |
| `connection_mode` | `real` | `real`, `shuffled`, `direct` |
| `stimulus_hz` | 150 | 0–300 Hz; například 0, 50, 150, 300 |
| `adapter_gain` (v motorovém JSON) | 8 | 1–32; například 1, 4, 8, 16 |
| `motor_matrix_file` | `./pygame_fly_motor.json` | Samostatný soubor vah převodníku na pohyb |
| `eye` | false | Společné zapnutí zraku; při vypnutí se nepočítá obraz prostředí |
| `left_odor`, `right_odor` | true | Zapnutí příjmu vůně vlevo a vpravo |
| `vision_mode` | `world` | `world`, `image` (počáteční pruhy), `dark` |
| `motion_enabled` (v motorovém JSON) | true | Výchozí stav checkboxu Motion; false pro měření bez pohybu |
| `brain_seed` | 42 | Například 42, 43, 44 pro opakování se změnou náhodných impulzů |
| `world_seed` | 31 | Rozložení a doplňování cukru |
| `food_count` | 24 | 1–899 bodů; ruční položení může přidat další |
| `sugar_odor_enabled` | true | Vůně prostředí; false pro izolaci ostatních podnětů |
| `sugar_odor_radius` | 2 | Čtvercový dosah vůně 1, 2 nebo 3 pole |
| `contact_windows` | 4 | Počet 50ms oken cukerného kontaktu, včetně prvního |
| `benchmark_world_steps` | 12 | Délka části automatického testu s pohybem |
| `window_width`, `window_height` | 1360, 790 | Výchozí rozměry okna |
| `log` | true | Dodatečný textový log a PNG |
| `screenshot_every_steps` | **50** | PNG po každých 50 dokončených krocích; lze zvýšit např. na 200 |
| `data_dir` | `./data` | Podadresáře `fly_annotations` a `fly_stimuli` |
| `model_data_dir` | `./external/Drosophila_brain_model` | Datové soubory `Completeness_783.csv`, `Connectivity_783.parquet` |
| `results_dir` | `./results` | Výsledky v podadresáři `fly` |
| `log_dir` | `./log` | Textové logy a PNG |

Relativní cesty vycházejí z adresáře programu na D:, nikoli z aktuálního adresáře
terminálu. Absolutní cestu lze napsat například `"D:/my_fly_results"`. Změna
cesty soubory nepřesune. Datové soubory a anotace musejí odpovídat verzi 783.
Modelový Python kód se stále importuje z původní instalace v `external`.

PNG vznikají po načtení sítě, po prvním a potom každém **50. kroku**, při pauze,
při zavření a po F12. Padesát kroků je 2,5 s modelového času, nikoli 50 sekund
skutečného času. Například `260918_1430_20_real_step000050.png` obsahuje datum,
čas, selektor sítě (`full`, `05`, `20`), režim spojů a důvod snímku. Opakovaná
jména dostanou číselný příznak. Program zatím podobné snímky automaticky neporovnává.

První záznam každého běhu v `log/RRMMDD_HHMM_log.txt` je `configuration`:
obsahuje účinné nastavení a absolutní cesty. Při opakovaném startu ve stejné
minutě se do stejného souboru připojí nový běh s vlastním konfiguračním záznamem.
Ovládání v okně mění aktuální hodnoty a zapisuje události, ale nepřepisuje JSON.

Podrobnosti jsou v `results/fly/sessions/<čas_režim>/`:

| Soubor | Co v něm hledat |
|---|---|
| `settings.json` | Nastavení při spuštění daného experimentu |
| `configuration.json` | Skutečné počty neuronů a spojů, seedy, přeživší oční pixely |
| `mapping.json` | Skupiny a identifikátory připojených neuronů |
| `telemetry.jsonl` | Každý požadovaný obraz, síla, odezva, poloha a pohyb |
| `worker.log` | Diagnostika výpočetního procesu a případné chyby |

`log: false` vypne dodatečné textové logy a PNG. Podrobná telemetrie a diagnostika
ve výsledcích zůstávají. PNG je přehledový obrázek, **telemetrie je podklad pro
porovnání**. Všechny výstupy mohou postupně zabírat místo na disku.

## 6. Společný postup pro srovnatelné pokusy

Začni s 1/5, pokud chceš rychlost i zachované rozhraní. 1/20 je dobrá pro rychlé
ověření ovládání a účinků velkého poškození; vybrané nálezy pak ověř ve Full.

Pro izolované pokusy A–J (kromě čichového H) nejdřív vypni `sugar_odor_enabled` v JSON
a restartuj. Jinak i ve tmě a s nezaškrtnutými čichovými sondami může mozek
dostávat vůni z blízkého cukru. Starší logy vzniklé před přidáním vůně popisují
jiné podmínky než současný výchozí svět.

1. Zvol síť a režim spojů. Počkej na `Ready`.
2. Vypni pohyb, nastav `Dark`, vypni obě čichové sondy. Nastav požadovanou sílu.
3. Dej `Reset state`. Udělej přesně dva kroky ve tmě jako základní měření.
4. Nastav podnět a proveď například šest kroků, tedy 300 ms modelového času.
5. Vrať tmu a proveď čtyři kroky, tedy 200 ms pozorování doznívání.
6. Poznamenej složku výsledků, podmínku a počet kroků. F12 lze uložit po
   dokončení zajímavého kroku.
7. Pro další variantu zopakuj **celý stejný postup**, včetně resetu a základních kroků.

Měň vždy jeden parametr. Stejný seed a stejná posloupnost kroků umožňují
reprodukovatelnost. Stejný seed při jiné posloupnosti podnětů sám nezaručuje
shodný experiment. Náhodné vstupy je vhodné později zopakovat s několika seedy.

## 7. Pokusy krok za krokem

### Pokus A: tma a kontrola, že do mozku nic neposíláme

Použij základní postup, ale všech dvanáct kroků nech `Dark`, čich 0 %, cukr
nepokládej a tělo neposouvej. Sleduj všechny `input_events`.

**Co čekat:** externí události mají být nulové. V této implementaci má čerstvě
resetovaná nebuzená síť zůstat tichá. Tma po předchozím podnětu není totéž jako
tma po resetu; případné doznívání porovnávej odděleně.

**Co zjistíme:** základní stav a případný zapomenutý vstup. Nenulové události
nejdřív prověř v čichu, kontaktu cukru a dotyku stěny, neinterpretuj je rovnou
jako spontánní aktivitu mozku.

### Pokus B: funguje samotný převod světla na impulzy?

V 1/20 nebo 1/5 zvol `Image`, načti `bars_32x32.png` přes `Load L`, pravé oko
vypni. Po resetu porovnej šest kroků s `stimulus_hz` 0, potom 50, 150 a 300;
každé intenzitě dej vlastní reset a stejnou základní sekvenci.

**Sleduj:** události `Vision L`, `Vision R`, celkové výboje a aktivní neurony
v logu. Pravý externí vstup má být nulový. Levý se má při nenulovém počtu
světlých připojených pixelů s intenzitou v průměru zvyšovat.

**Co zjistíme:** zda podnět skutečně dorazil. Nemusí přitom vzniknout jediný
pohyb ani sestupný výboj. Růst vstupních událostí není sám o sobě důkaz přenosu
k výstupu. Výstup může kvůli dynamice a inhibici reagovat nelineárně.

### Pokus C: levé versus pravé oko

Použij `Load 64×32` a soubor `left_only_64x32.png`. Obě oči nech povolené:
pravou stranu soubor vypíná černou. Udělej společnou sekvenci. Potom přepni
na tmu, resetuj a ve stejné fázi sekvence načti `right_only_64x32.png`.

**Sleduj:** zda se externí události přesunuly ze skupiny L do R, pak rozdíly
`Descending L/R`, čas prvních výbojů a ID aktivních sestupných neuronů.

**Co zjistíme:** asymetrii odpovědi na naši stimulaci. Nelze z ní hned odvodit,
že muška poznala levou stranu prostoru nebo že se má otáčet konkrétním směrem.
Výběr neuronů a jejich přiřazení k pixelům nejsou ověřená mapa sítnice.

### Pokus D: oba obrazy současně

Po stejné tmavé základní sekvenci načti `binocular_64x32.png`. Levá polovina
obsahuje pruhy, pravá šachovnici. Porovnej s oddělenými variantami každé poloviny,
při nichž druhé oko vypneš.

**Sleduj:** stejné výstupní skupiny a celkovou aktivitu. Současná odpověď může
být větší, menší, nebo jinak rozložená než jednotlivé odpovědi.

**Co zjistíme:** případné nelineární působení souběžných vstupů. Samotné zesílení
při obou očích může být jen důsledkem většího celkového buzení. Není důkazem
stereoskopického vidění ani odhadu vzdálenosti.

### Pokus E: pruhy versus šachovnice se stejným průměrným jasem

V 1/5 nebo Full načti střídavě `bars_32x32.png` a `checker_32x32.png` do stejného
oka; druhé vypni. Každému obrázku dej vlastní reset a stejný časový protokol.
Oba obrázky mají stejný podíl bílých a černých pixelů.

**Sleduj:** zda je podobný počet vstupních událostí, ale jiné výstupy nebo jiná
aktivní sestupná ID. `Direct sensors` pracuje jen s průměrným jasem, takže pro
takto shodné průměry má dávat stejné umělé hodnoty řadiče.

**Pozor u 1/20:** maska přeživších pixelů může z obou obrazů vybrat různý počet
bílých bodů. Shodný průměr celého obrázku tam nezaručuje shodné buzení. Rozdíl
pak může být dán jen počtem připojených světlých pixelů. Pro první porovnání
prostorového vzoru je proto vhodnější 1/5 nebo Full.

**Co zjistíme:** citlivost na experimentální rozložení stimulovaných neuronů,
nikoli rozpoznávání objektů nebo přirozených tvarů.

### Pokus F: kontakt cukru a MN9

Začni ve Full, `Dark`, čich 0 %, pohyb vypnutý. Po resetu udělej dva kroky.
Stiskni `Place sugar under fly` a proveď osm kroků. Při výchozích čtyřech
kontaktních oknech mají být první čtyři s cukerným vstupem, další bez něj.
Neumisťuj během této sekvence další cukr.

**Sleduj:** `Sugar contact`, vstupní události, `MN9` a `Head motor`, potom
sestupné výstupy. Zaznamenej, kdy odpověď začala a kdy odezněla. MN9 přímo
neovládá přesun po mřížce, takže jeho aktivita nemusí pohnout tělem.

Zopakuj v 1/5 a 1/20. V 1/20 je MN9 **absent** — jeho odpověď tam měřit nejde.
Nejsilnější vybraný cukerný vstup `720575940639198653` je chráněný. Ve Full má
93 cílových neuronů, součet vah 719 a nejsilnější jednotlivý spoj 91. V 1/20
mu zůstávají jen čtyři cíle se součtem vah 7. Tyto strukturální hodnoty samy
neurčují výslednou odezvu. Žebříček je v `data/fly_annotations/sugar_input_weights.csv`.

**Co zjistíme:** zda a jak se v dané variantě přenáší cukerné buzení. Ztráta
reakce po redukci může odpovídat přerušené cestě, nikoli neúčinnému vstupu.

### Pokus G: délka cukerného kontaktu

Proveď pokus F s `contact_windows` 1, 4 a 10. Mezi změnami JSON restartuj
aplikaci a zachovej síť, seed i sílu. Po položení cukru vždy měř alespoň
14 kroků, aby zbyl čas i na odeznění nejdelšího podnětu.

**Sleduj:** nástup, maximum a přetrvání odpovědi. Delší kontakt dodává více
impulzů; rozdíl tedy není automaticky paměť. Aktivita po skončení kontaktu
může být doznívání dynamiky sítě. Synaptické učení tento program neprovádí.

### Pokus H: ruční čichová sonda

V 1/5 nebo Full povol `sugar_odor_enabled`, vypni zrak a pohyb a dej reset.
Šipkami přesuň tělo vedle cukru, ne přímo na něj, aby se při kroku nesebral.
Vypni oba čichové checkboxy a udělej dva základní kroky. Potom zapni
`Left odor enabled` na šest kroků a vypni jej na čtyři kroky. Pro pravou stranu
a obě strany postup zopakuj od resetu a stejné ruční polohy u stejného cukru.

**Sleduj:** vstupní události a výstupy. V 1/20 obě naše připojené čichové skupiny
chybějí, takže zapnutí sondy nemá kam poslat impulzy. To je užitečná kontrola
významu `absent`, nikoli důkaz, že skutečná muška necítí pach.

Vybrané čichové neurony nemají v tomto programu ověřené ladění na konkrétní
látku. Tlačítko proto nepředstavuje například skutečný pach cukru.

### Pokus I: původní versus promíchané spoje

Vyber jeden dobře definovaný podnět z pokusů C, E nebo F. Proveď stejnou
sekvenci v `Real connections` a `Shuffled targets`, při stejném seedu, velikosti,
síle a vypnutém pohybu. Přepnutí režimu resetuje mozek; zopakuj základní kroky.

Promíchání mění cílové konce zachovaných spojů. Zachovává počty vstupních
a výstupních hran a váhy u jejich zdrojů, ale může vytvořit smyčky a opakované
hrany mezi stejnými neurony. Není to univerzální náhodný model všech možných sítí.

**Co zjistíme:** zda je daná odpověď citlivá na původní zapojení. Rozdíl v jednom
pokusu není důkaz konkrétní biologické funkce. Stejný výsledek může znamenat
necitlivé měření, slabý podnět nebo v obou případech neaktivní výstup.

### Pokus J: celá síť versus redukce

Zopakuj jeden zrakový a jeden cukerný pokus v pořadí 1/20, 1/5, Full. Použij
shodné podněty a seedy; zapisuj i skutečné počty stimulovaných neuronů.

**Sleduj:** dobu výpočtu, aktivní neurony, výstupní frekvence a chybějící skupiny.
U 1/20 se mění jak vnitřek sítě, tak počet připojených receptorů a výstupů.
Pokles aktivity proto nelze přičíst pouze vnitřním spojům. Ani surové celkové
počty výbojů nelze porovnávat jako rovnocenné u sítí různých velikostí.

1/5 oproti Full zachovává celé naše rozhraní, a je proto vhodnější pro první
porovnání vlivu odstranění vnitřních neuronů. Pořád však nejde o kontrolované
odstranění jediné konkrétní dráhy.

### Pokus K: co přidává samotný pohybový řadič

Zvol `Direct sensors`, `World`, zapni pohyb a použij gain 1, 4, 8 a 16.
Pro každou hodnotu resetuj svět a pozoruj stejný počet kroků, například 50.
Potom zkus totéž ve skutečné síti, pokud poskytuje nenulové sestupné výstupy.

Řadič používá průměry L a R:

```text
forward = clip(gain × (L + R) / 2, 0, 1)
turn    = clip(gain × (R - L) × 30, -45, 45) stupňů za krok
```

Pohybový kredit se sčítá, dokud nevystačí na přesun o políčko. Směr pohybu se
zaokrouhluje na čtyři směry mřížky. Při nule na obou výstupech nepomůže vyšší
gain. Při saturaci už další zvýšení gain nemusí rychlost zvětšit.

**Co zjistíme:** citlivost našeho převodníku, nikoli učení mozku. V otevřené
smyčce s vypnutým pohybem gain nemění neuronové výpočty. V pohybujícím se světě
ale mění budoucí podněty, a tím může nepřímo změnit i aktivitu. Vyšší počet
sebraných cukrů může být pouze důsledkem více navštívených polí.

### Pokus L: opakovatelnost a náhodnost

Vyber jeden podnět a proveď jej dvakrát se stejným `brain_seed`, od resetu,
se stejným počtem kroků a vypnutým pohybem. Potom změň seed na 43 a 44 a
opakuj. Zaznamenej všechny pokusy, nejen ten s největším efektem.

**Co zjistíme:** zda nález závisí na konkrétním náhodném průběhu. U promíchané
sítě změna `brain_seed` mění i promíchání, protože jeho seed je odvozen jako
`brain_seed + 100`. Tímto ovládáním tedy zatím nelze oddělit nejistotu z
náhodných impulzů od nejistoty z náhodného zapojení.

## 8. Automatické porovnání a jeho meze

### Nastavitelná pohybová matice a kroužení

Soubor [pygame_fly_motor.json](../pygame_fly_motor.json) je samostatná editovatelná
matice. Hlavní konfigurace na něj odkazuje přes `motor_matrix_file`. Po úpravě
program restartuj. Log i `settings.json` obsahují skutečně načtené váhy, takže
se další pokus dá zpětně odlišit. Změna souboru během běhu se nepoužije.

Také **`adapter_gain` je v `pygame_fly_motor.json`**, nikoli v hlavním setupu.
Motorový soubor obsahuje `adapter_gain`, `forward` a `turn`. Posuvník v okně
mění zesílení aktuálního pokusu, ale soubor nepřepisuje. Do logu se uloží
účinná hodnota; pro trvalou změnu uprav motorový JSON a restartuj aplikaci.

Každý ze dvou řádků obsahuje váhu pěti výstupů: `dn_left`, `dn_right`,
`dn_center`, `head_motor` a `mn9`. Součin váhy a příslušné výstupní aktivity
se sečte a násobí `adapter_gain`. `forward` se ořízne na 0–1 a určuje dopředný
pohybový kredit. `turn` se ořízne na −45 až +45 stupňů za krok.

Výchozí `forward` používá váhy 0,5 a 0,5 pro levé a pravé sestupné neurony.
Výchozí `turn` používá −30 a +30; ostatní váhy jsou nulové. Matice tak
zachovává dosavadní chování. Záporný úhel na obrazovce znamená zatáčení proti
směru hodinových ručiček, kladný po směru. Vyšší aktivita vlevo tedy nyní
vede k zápornému zatočení. Anatomická strana není ověřená motorická funkce;
tohle přiřazení je naše hypotéza.

Pro úvodní pokusy uprav pouze hodnoty řádku `turn`, ostatní položky ponech:

| Pokus | `dn_left` | `dn_right` | Význam |
|---|---:|---:|---|
| Bez zatáčení | 0 | 0 | Při ostatních nulových vahách `turn` pouze dopředný pohyb |
| Slabší zatáčení | −3 | 3 | Desetina původního neomezeného povelu |
| Opačné přiřazení | 3 | −3 | Obrácený směr stejné asymetrie |
| Pokusné vyrovnání | −1 | 3 | Nulový součet při poměru aktivity L:R = 3:1 |

Poslední řádek je pouze příklad, nikoli automaticky vhodné nastavení. Změř
průměry L a R při definované základní stimulaci a vypnutém pohybu. Vyber
váhy tak, aby `wL × průměr(L) + wR × průměr(R)` bylo přibližně nula, a pak
ověř reakce na jiné podněty a seedy. Při nulovém pravém výstupu nelze asymetrii
vyrovnat pouhým násobením pravé strany; nula zůstane nulou.

V telemetrii `body.command` jsou `raw_forward` a `raw_turn_degrees` před
ořezem. Když máš například −100 stupňů před ořezem a −45 po něm, může několik
různých vah dávat totožné zatáčení. Proto nejdřív zkoušej menší váhy. Změnou
této matice se **nemění synapse mozku a nejde o učení**. Zrak či čich působí
přes mozkové výstupy; matice si nebere přímo obrázek ani polohu cukru.
Výjimkou je kontrolní režim `Direct sensors`, kde mozek záměrně obcházíme.

`head_motor` už zahrnuje MN9. Nenulové váhy obou těchto sloupců proto započítají
část stejné aktivity dvakrát. Výchozí nuly toto zdvojování nezavádějí.

### Spuštění automatického testu

`Compare 3 modes` zastaví interaktivní výpočet a postupně spustí skutečné
spoje, promíchané spoje a přímý řadič pro vybranou velikost sítě. Použije aktuální
sílu, gain, pohybovou matici, společné zapnutí zraku a čichových stran,
nakonfigurované seedy a prostředí. Jeho vlastní protokol nahrazuje aktuální
obrázek a přepínače jednotlivých očí. V pohybové části řadič běží i tehdy, když byl
interaktivní pohyb vypnutý.

První část má 34 kroků: dvě tichá okna, potom pro každý ze sedmi vstupních
kanálů intenzity 0,5, 1, 1 a jedno tiché okno, nakonec čtyři tichá okna.
Oči jsou zde buzeny rovnoměrně, nejde o test obrázků. Druhá část vytvoří nový
mozek a krátký světový běh. Používá skalární jas textury/stěn, nikoli přesný
obrazový pohled GUI. Po dokončení stiskni `Reset state` pro návrat k interakci.

Výstupy jsou v `results/fly/benchmark_ui/`; další kliknutí je přepíše. Pro
uchování více variant použij samostatné výstupní adresáře:

```powershell
.\venv\Scripts\python.exe fly_experiment.py --size twentieth --output results/fly/trial_20_a
.\venv\Scripts\python.exe fly_experiment.py --size fifth --output results/fly/trial_05_a
```

V dřívějším Full testu `benchmark_pixels_v2` byly externí události skutečné
a promíchané sítě pro sondovací sekvenci shodné. Nejvyšší MN9 za celý protokol
bylo 100 Hz u skutečných spojů a 0 Hz u promíchaných. Krátké světové běhy obou
sítí měly nula přesunů, přímý řadič pět. Jde o konkrétní historický test, ne
o očekávaný výsledek každé nové konfigurace ani důkaz navigace za cukrem.

## 9. Jak číst výsledky a korelace

U každého pokusu si udělej malou tabulku. Hodnoty níže jsou názvy položek,
nikoli naměřené výsledky:

| Podmínka | Síť / seed | Skutečné vstupní události | Výstup L/R | MN9 nebo absent | Počet přesunů | Složka |
|---|---|---|---|---|---|---|
| Tma | 1/5 / 42 | … | … | … | … | … |
| Levé pruhy | 1/5 / 42 | … | … | … | … | … |
| Pravé pruhy | 1/5 / 42 | … | … | … | … | … |

Porovnávej stejný počet dokončených oken. Uváděj jak maximum, tak průměr
za stejné období, případně první okno s výbojem. Při změně frekvence nebo
velikosti sítě zkontroluj, kolik stimulace skutečně dorazilo.

| Pozorování | První interpretace a další kontrola |
|---|---|
| Vstupní události jsou nula | Tma, 0 Hz, vypnuté oko, odstraněná skupina, nebo ještě nedokončený krok |
| Vstupní události rostou, výstupy jsou nula | Stimulace funguje, přenos k měřenému výstupu zatím neprokázán |
| Celkové výboje rostou, sestupné zůstávají nula | Aktivita může zůstávat v senzorech či jiných částech sítě |
| MN9 reaguje, tělo se nehýbe | MN9 se nepoužívá pro mřížkový pohyb |
| Výstupy reagují, tělo stojí | Zkontroluj vypnutý pohyb, malý kredit a hranici světa |
| Všechny varianty se hýbou podobně | Možná převládá řadič; není doložen přínos konkrétního zapojení |
| 1/20 nereaguje, Full ano | Může jít o ztrátu receptorů, výstupů i cest; rozlišuj chybějící skupiny |

Korelační panel počítá Pearsonovu korelaci vstupu s výstupem o jedno okno
(50 ms) později, nejvýše z posledních 300 oken. Potřebuje alespoň osm párů
a proměnlivé signály. Konstantní řady se vynechávají. U vizuálních vstupů
používá průměrný jas, takže změnu pruhů na šachovnici se stejným jasem nemusí
vůbec zachytit, i když se neuronová odezva změní.

Panel vybírá nejsilnější korelace; náhodná shoda proto může působit výrazně.
Pohyb navíc mění budoucí vstupy a může korelaci vytvářet zpětnou vazbou.
**Korelace není prokázaná příčina ani identifikovaná funkce neuronu.** Nejprve
porovnávej kontrolované sekvence bez pohybu, potom několik seedů a teprve pak
uvažuj o cílených zásazích do konkrétní dráhy.

## 10. Co je rozumný první výsledek

Pro začátek stačí prokázat tři oddělené věci: změna obrazu mění skutečný
vstup, změna vstupu mění měřený výstup a tento výstup dokáže přes řadič změnit
pohyb. Každý krok ověř zvlášť. Pokud selže prostřední krok v 1/20, nesnaž se
ho zakrýt zvýšením gain — vrať se k 1/5 nebo Full a ověř přenos.

Úspěch zde neznamená, že muška „pochopila obrázek“, „naučila se cukr“ nebo
„má přirozené vidění“. Současná aplikace umožňuje měřit odezvy pevné sítě,
porovnávat redukce a zkoušet hypotézy o jejím připojení k prostředí.

## Zdroje a kontrola implementace

Počty vycházejí z lokálního modelu a připnutých anotací, nikoli automaticky
z celkových počtů uváděných v článcích pro jiný výběr dat.

- [Původní anglický návod](pygame_fly.md)
- [FlyWire annotations v2.1.0](https://github.com/flyconnectome/flywire_annotations/tree/v2.1.0)
- [Shiu a kol.: výpočetní model mozku](https://www.nature.com/articles/s41586-024-07763-9)
- [Článek o anotaci buněčných typů](https://www.nature.com/articles/s41586-024-07686-5)
- [Propojení mozku a VNC](https://www.nature.com/articles/s41586-025-08925-z)

Technické kontroly lze spustit takto; druhý příkaz počítá i velkou síť:

```powershell
.\venv\Scripts\python.exe -m unittest test_fly -v
.\venv\Scripts\python.exe verify_fly_sizes.py
```

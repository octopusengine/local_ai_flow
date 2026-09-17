# Mozek octomilky v Pygame: průvodce a pokusy

Tato aplikace umožňuje stimulovat vybrané neurony modelu mozku octomilky,
odpojovat jejich prostředníky a sledovat, jak se změní odpověď sítě.
Pygame poskytuje ovládací okno; vlastní neuronovou simulaci počítá **Brian 2**.

## 1. Spuštění a první orientace

V PowerShellu v adresáři `D:\data_codex\fruit_fly_brain` spusť:

```powershell
.\venv\Scripts\python.exe pygame_brain.py
```

Při spuštění se připraví výchozí pokus: **150 Hz, 200 ms biologického času, seed 42**.
Počkej na stav **VÝSLEDEK PŘIPRAVEN**. Nový výpočet může trvat několik až desítky
sekund; již uložený stejný pokus se načte rychleji.

![Ukázka rozhraní s odpojeným prostředníkem](../results/pygame_lab/pygame_preview.png)

Na obrázku je výsledek zásahu, nikoli výchozí stav: jeden prostředník má odpojené výstupy.

## 2. Jak to funguje

### Data, model a obrázek jsou tři různé věci

**Data** pocházejí z konektomu FlyWire 630: obsahují identifikátory neuronů,
jejich spojení, počty synapsí a modelové znaménko účinku.
Simulovaná síť má **127 400 neuronů**, **14 687 178 řádků spojení**
a součet **52 793 639 anatomických synapsí**. Jeden řádek může zastupovat více synapsí.

**Model** pochází z projektu [Shiu a kol.](https://github.com/philshiu/Drosophila_brain_model).
Každý neuron je zjednodušená jednotka typu *leaky integrate-and-fire*:

1. Přijímá budivé a tlumivé vstupy.
2. Jeho membránové napětí se průběžně mění a bez vstupu se vrací ke klidové hodnotě.
3. Po překročení prahu vytvoří výboj a jeho napětí se resetuje.
4. Výboj přes spoje ovlivní další neurony.

V použitém modelu je klidové a resetovací napětí −52 mV, práh výboje −45 mV
a zpoždění synaptického přenosu 1,8 ms. Výpočet má krok 0,1 ms.
Počítají se společně všechny neurony sítě, včetně těch, které v okně nejsou nakreslené.

**Obrázek** je přehledové schéma vybraných spojení. Není to anatomická mapa,
3D mozek ani zobrazení všech cest. Původní výřez Hemibrain v Neuroglanceru
je jiný dataset; Pygame ho nepoužívá jako vstup simulace.

### Co znamená síla vstupu

Posuvník určuje frekvenci náhodných Poissonových vstupních událostí pro každý
z **21 chuťových neuronů**, převzatých z příkladu autorů jako vstupy citlivé na cukr.

Například 150 Hz znamená v průměru 150 vstupních událostí za sekundu na neuron.
Za 200 ms je to průměrně 30 událostí, ale konkrétní počet se může lišit.
Události nejsou pravidelný metronom a nastavená frekvence není zárukou totožné
naměřené frekvence výbojů. Posuvník nemění synaptické váhy ani přímo nenastavuje MN9.

### Co jsou váhy

Model používá vztah:

```text
váha = počet synapsí × znaménko účinku × 0,275 mV
```

Kladná váha má budivý účinek, záporná tlumivý. Hodnota je přírůstek synaptické
proměnné, která následně ovlivňuje membránové napětí; není to přímo okamžitý
skok napětí neuronu. Parametr 0,275 mV je součást modelu. Nejde o individuálně
změřenou biologickou sílu každého spojení.

### Co znamená odpojit neuron

Kliknutí na prostředníka **vynuluje všechny jeho výstupní váhy v celé síti**,
nejen viditelný spoj do MN9. Jeho vstupy zůstanou zapojené a neuron může dál
vytvářet výboje. Ty však přes jeho odpojené výstupy nepůsobí na další neurony.

Proto může i červeně označený odpojený neuron při přehrávání blikat.
Není to chyba: odpojujeme jeho účinek, nemažeme samotný neuron.

### Jak vzniká srovnání

Po stisknutí **Přepočítat** aplikace připraví dvě podmínky:

| Podmínka | Vstup | Odpojení |
|---|---|---|
| Reference | Aktuální hodnota posuvníku | Žádné |
| Zásah | Stejná hodnota | Vybraní prostředníci |

Obě podmínky začínají od klidového stavu, mají délku 200 ms a seed 42.
V ověřeném pokusu byly výboje stimulovaných vstupních neuronů mezi podmínkami totožné.
Žádný stav ani učení se nepřenáší z předchozího experimentu.

Výpočet běží v samostatném procesu, aby ovládací okno reagovalo.
Stejné pokusy se ukládají do cache: opětovné stisknutí tlačítka za stejných
podmínek není nové nezávislé opakování.

## 3. Co vidíme v okně

### Horní schéma: vstupy → prostředníci → MN9

Zelený uzel **CUKR** zastupuje všech 21 vstupních neuronů.
Uprostřed je **13 prostředníků**, pro které v datech existují obě spojení:
některý cukrový vstup → prostředník a prostředník → MN9.
Vpravo je sledovaný neuron **MN9**, ID `720575940660219265`.

Prostředníci jsou řazeni podle absolutní velikosti váhy jejich spoje do MN9.
Horní pozice tedy znamená silnější přímý spoj, nikoli automaticky největší
vliv na celý výsledek. Ten závisí také na aktivitě neuronu a okolní síti.

| Značka | Význam |
|---|---|
| Modrý spoj do MN9 | Budivá modelová váha |
| Červený spoj do MN9 | Tlumivá modelová váha |
| Šedý výstupní spoj | Prostředník má odpojené výstupy |
| Tloušťka spoje | Přibližné znázornění absolutní velikosti váhy, s omezeným rozsahem |
| Číslo u prostředníka | Původní váha spoje do MN9 v mV; po odpojení zůstává číslo pro orientaci |
| Žluté bliknutí uzlu | Alespoň jeden zaznamenaný výboj v posledních 3 ms přehrávaného času |
| Žlutý rámeček řádku | Vybraný prostředník, jehož detail je vlevo |

Levé šipky od CUKRU agregují spoje od všech 21 vstupů.
Údaj **Ze vstupů** je součet jejich vah do vybraného prostředníka.
Bliknutí CUKRU může vyvolat kterýkoli z jeho 21 neuronů.

Žlutá aktivita je převzatá ze skutečně vypočtených výbojů. Pohyb či svícení
v obrázku ale neprokazují, po které konkrétní cestě výboj vznikl.

### Spodní graf: napětí a výboje MN9

- **Šedá křivka:** napětí MN9 v referenci.
- **Zelená křivka:** napětí MN9 po zásahu.
- **Svislé čárky pod grafem:** skutečné časy výbojů, zvlášť pro každou podmínku.
- **Žlutá svislice:** právě přehrávaný čas.
- **Výsledek MN9:** průměrná frekvence v celém 200ms okně.
- **Změna:** výsledek zásahu minus reference při stejné síle vstupu.
- **Aktivní síť A → B:** počet neuronů celé sítě s alespoň jedním výbojem,
  nejprve v referenci, potom po zásahu.

Například **18 výbojů / 0,2 s = 90 Hz**. Jeden výboj navíc či méně v tomto
krátkém okně změní zobrazenou frekvenci o 5 Hz.

Křivka není podrobný biologický tvar akčního potenciálu: LIF model po výboji
resetuje napětí. Při počítání výbojů se řiď čárkami a číselným výsledkem,
ne jen vizuálními vrcholy křivky.

### Dva posuvníky, dvě různé funkce

**Vlevo** nastavuješ vstupní frekvenci. **Pod schématem** posouváš čas již
vypočteného záznamu. Přehrávání je zpomalené: 200 ms modelového času trvá asi
8 sekund a opakuje se. Opakování animace nespouští další výpočet.

Po změně parametrů se zobrazí **ZMĚNY ČEKAJÍ**. Spodní graf stále patří
poslednímu dokončenému pokusu a blikání se pozastaví. Teprve **Přepočítat**
provede nové nastavení.

## 4. Co se dá dělat

| Ovládání | Akce |
|---|---|
| Levý posuvník | Vstup 0–300 Hz po 5 Hz |
| Šipka vlevo / vpravo | Změna vstupu o −5 / +5 Hz |
| Kliknutí na prostředníka | Výběr detailu a přepnutí odpojení jeho výstupů |
| Přepočítat / Enter | Výpočet nebo načtení výsledku pro aktuální nastavení |
| Zapojit všechny / R | Zrušení odpojení; nový výsledek vyžaduje přepočet |
| Pauza / mezerník | Pozastavení či spuštění přehrávání |
| Spodní posuvník | Prohlížení konkrétního okamžiku záznamu |
| Zrušit výpočet | Ukončení právě běžícího výpočtu |
| Esc / zavření okna | Ukončení aplikace a jejího běžícího výpočtu |

Při výpočtu nelze měnit nastavení experimentu. Zobrazení a přehrávání zůstávají
ovladatelné. Změna velikosti okna přizpůsobí zobrazení.

V současném GUI nelze měnit délku pokusu, seed, zvolit jiný sledovaný neuron,
odpojit libovolné ID mimo zobrazených 13 prostředníků ani ručně přepsat nenulovou váhu.
To by vyžadovalo úpravu nebo rozšíření aplikace.

## 5. Co vlastně testujeme

Základní otázka je: **Jak se změní výstup sítě, když při stejném vstupu
odstraníme vliv vybraného neuronu?**

Testujeme přenos aktivity, citlivost na vstup a význam určitých spojení
v daném výpočetním modelu. Zásah může odpověď oslabit, zesílit, změnit její
časování, nebo nemít v tomto pokusu patrný účinek.

Slabší odpověď po odpojení podporuje závěr, že neuron pomáhal dané odpovědi
v modelu. Neprokazuje, že účinek přenášel pouze viditelným přímým spojem:
odpojili jsme všechny jeho výstupy a změnili i zpětné vazby v celé síti.

Netestujeme zde pohyb těla, skutečné ochutnání cukru, učení ani chování živé
mouchy. Model nemá připojené tělo či prostředí a váhy se během pokusu neučí.

## 6. Návodné pokusy

Před každým samostatným pokusem použij **Zapojit všechny**. Po každé změně
stiskni **Přepočítat** a počkej na dokončení. Zapisuj si nastavení i výsledek.
U dalších pokusů níže jsou uvedené otázky a hypotézy, nikoli předem zaručené výsledky.

### Pokus A: nulový vstup — kontrola klidového stavu

1. Zapoj všechny prostředníky.
2. Nastav 0 Hz a přepočítej.
3. Sleduj MN9 a počet aktivních neuronů celé sítě.

**Ověřený výsledek:** 0 výbojů, 0 aktivních neuronů.
V této konfiguraci není spontánní vstup a síť začíná v klidu.
Tento výsledek neznamená, že skutečný mozek bez cukru nevykazuje aktivitu.

### Pokus B: odpověď na rostoucí vstup

1. Nech všechny prostředníky zapojené.
2. Postupně vyzkoušej 25, 50, 100, 150, 200 a 300 Hz.
3. Pro každou hodnotu zapiš frekvenci MN9 a počet aktivních neuronů.

**Otázka:** Od jaké intenzity MN9 v tomto pokusu reaguje? Roste odpověď
plynule, skokově, nebo se mění nelineárně?

Bez odpojení budou reference a zásah stejné, tedy **Změna = 0 Hz**.
To neznamená, že posuvník nic nedělá: změnu mezi intenzitami uvidíš ve
svých zapsaných hodnotách **Výsledek MN9**. Aktuální reference se totiž
vždy přepočítává na stejnou intenzitu jako zásah.

### Pokus C: odpojení silného budivého prostředníka

1. Nastav 150 Hz a všechny prostředníky zapoj.
2. Přepočítej a zaznamenej referenci.
3. Klikni na horní neuron `720575940627847752` se spojem **+20,350 mV** do MN9.
4. Přepočítej a porovnej výsledek.

**Ověřený výsledek pro seed 42 a 200 ms:**

| Metrika | Reference | Po odpojení |
|---|---:|---:|
| Výboje MN9 | 18 | 13 |
| Frekvence MN9 | 90 Hz | 65 Hz |
| Aktivní neurony celé sítě | 353 | 316 |

**Interpretace:** Odpojení snížilo, ale neodstranilo odpověď.
Síť má i další funkční zdroje ovlivňující MN9. Z tohoto pokusu samotného
nelze určit, kolik z účinku způsobilo přímé spojení a kolik ostatní výstupy prostředníka.

### Pokus D: odstranění tlumivého vlivu

1. Zapoj všechny prostředníky a ponech 150 Hz.
2. Odpoj neuron `720575940616864217`, jehož spoj do MN9 má **−1,925 mV**.
3. Přepočítej a porovnej frekvenci i časování výbojů MN9 s referencí.

**Hypotéza:** Odstranění tlumivého vlivu může odpověď zvýšit.
Není to zaručené: zásah působí na celou síť a v konkrétním okně nemusí být
prostředník dostatečně aktivní. Pokud frekvence zůstane stejná, zkontroluj
také časování výbojů a počet aktivních neuronů.

### Pokus E: dva zásahy současně

1. Při 150 Hz samostatně odpoj neuron `720575940627847752` a zapiš změnu MN9.
2. Zapoj všechny, odpoj `720575940616857174` (**+6,875 mV**) a zapiš změnu.
3. Odpoj oba současně a přepočítej.

**Otázka:** Je společný účinek stejný jako součet samostatných změn?
Pokud například jednotlivé změny označíš ΔA a ΔB, porovnej je se společnou
změnou ΔAB. Odlišnost od ΔA + ΔB ukazuje nelineární interakci v tomto pokusu,
nikoli automaticky konkrétní mechanismus. Výsledek mohou ovlivňovat prahy,
zpětné vazby a další cesty.

### Pokus F: odpojení všech zobrazených prostředníků

1. Ponech 150 Hz a postupně odpoj všech 13 řádků.
2. Přepočítej. Ověř, že vlevo je **Odpojené výstupy: 13**.
3. Sleduj, zda MN9 ztichl, nebo stále vytváří výboje.

**Otázka:** Zůstává odpověď i po přerušení všech zobrazených dvoukrokových cest?
Případná zbývající aktivita může vycházet z jiných cest celé sítě.
Pokud MN9 ztichne, neprokazuje to, že žádné jiné cesty anatomicky neexistují:
pouze za těchto podmínek neudržely výstup. Ani jeden výsledek není předem zaručený.

### Pokus G: stejný počet výbojů, jiné časování

1. Vrať se k jednomu zásahu z předchozích pokusů.
2. Pozastav přehrávání a posouvej spodní časový posuvník.
3. Porovnej čárky výbojů reference a zásahu: kdy vzniká první výboj,
   jak dlouhé jsou mezery a zda se odpověď soustředí do začátku nebo konce okna.

**Otázka:** Popisuje samotná průměrná frekvence celý rozdíl?
Dvě podmínky mohou mít stejnou frekvenci, ale odlišnou časovou strukturu.
Pouhá současnost bliknutí dvou neuronů však není důkaz přímého přenosu mezi nimi.

## 7. Jednoduchý záznam experimentů

Pro ruční poznámky lze použít tuto tabulku:

| Pokus | Vstup Hz | Odpojená ID | MN9 reference Hz | MN9 zásah Hz | Rozdíl Hz | Aktivní síť A → B | Poznámka k časování |
|---|---:|---|---:|---:|---:|---|---|
| C | 150 | 720575940627847752 | 90 | 65 | −25 | 353 → 316 | Doplnit pozorování |
| … | | | | | | | |

Výsledek „beze změny“ je také užitečný. Znamená, že se nezměnila daná
sledovaná metrika za daného vstupu a délky pokusu. Neznamená, že neuron
obecně nemá funkci.

Seed je v GUI pevný a opakované pokusy se cachují. Klikání na Přepočítat
proto nenahrazuje statistické opakování s různými náhodnými vstupy.
Pro robustnější závěr by bylo potřeba doplnit více seedů, delší okna
a porovnat model s biologickými měřeními.

## 8. Kde jsou výsledky a jak pokračovat

Vše se ukládá pod `D:\data_codex\fruit_fly_brain`:

| Umístění | Obsah |
|---|---|
| `results/pygame_lab/graph.json` | Zobrazené prostředníky, ID a agregované váhy |
| `results/pygame_lab/runs/<klíč>/config.json` | Parametry konkrétního výpočtu |
| `results/pygame_lab/runs/<klíč>/result.json` | Metriky, zobrazené výboje a napětí MN9 |
| `results/pygame_lab/runs/<klíč>/all_spikes.npz` | Výboje celé sítě a převod indexů na FlyWire ID |
| `results/pygame_lab/runs/<klíč>/rates.csv` | Počet výbojů a frekvence všech neuronů |
| `results/pygame_lab/jobs/<id>/` | Požadavek okna, odpověď a diagnostický `worker.log` |
| `.runtime/` | Dočasné soubory a cache na D: |

Velká FlyWire ID při načítání CSV do Excelu importuj jako text, aby se
nezaokrouhlila. V JSON jsou uložená jako řetězce.

Další dokumentace:

- [Stručné ovládání Pygame](pygame_cz.md)
- [Model, instalace a původní tři kontrolní simulace](simulace_cz.md)
- [Původní zdrojový model a příklady autorů](https://github.com/philshiu/Drosophila_brain_model)

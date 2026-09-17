# Simulace mozku octomilky

## Co máme a co simulujeme

Neuroglancer zobrazuje anatomii. Původní soubory `data/em.npy` a
`data/segmentation.npy` obsahují malý výřez Hemibrain, nikoli spustitelnou neuronovou síť.

Pro simulaci jsme stáhli původní projekt autorů studie
[Shiu a kol., Nature 2024](https://doi.org/10.1038/s41586-024-07763-9):
[Drosophila_brain_model](https://github.com/philshiu/Drosophila_brain_model).
Nachází se v `external/Drosophila_brain_model`, commit
`91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`. Původní kód a jeho MIT licence zůstávají zachované.

Repozitář obsahuje kompletní tabulky neuronů a spojení pro verze FlyWire 630 a 783.
Náš první experiment používá **FlyWire 630: 127 400 neuronů a 14 687 178 řádků spojení**,
tedy síť použitou v původním příkladu autorů. Řádek spojení může představovat více anatomických synapsí.
Nejde o stažení všech EM snímků, tvarů neuronů ani všech výsledků autorů.

Hemibrain a FlyWire jsou různé datasety; jejich číselné identifikátory neuronů nejsou zaměnitelné.
Tento experiment není napojen na dosavadní barevný fragment v Neuroglanceru.

## Spuštění

V PowerShellu v kořenovém adresáři projektu:

```powershell
.\install_simulation.ps1
.\venv\Scripts\python.exe simulate_brain.py
```

Brian 2 simuluje celou síť na CPU. Používáme NumPy backend, aby nebyl nutný C++ kompilátor.
Instalační skript ukládá cache pipu a dočasné soubory do `.runtime` v projektu na D:.
Simulátor tam také směruje vlastní cache, logy a konfiguraci Matplotlibu.
Brian 2 při importu na Windows používá uživatelský profil; skript jej pouze pro dobu importu
v aktuálním procesu přesměruje do `.runtime/profile` a ihned obnoví. Systémové nastavení se nemění.
Výchozí pokus má 200 ms biologického času, krok 0,1 ms a seed 42.
Čas běhu počítače není biologický čas. Simulace vyžaduje několik GB operační paměti.

Delší pokus nebo jiný vstup:

```powershell
.\venv\Scripts\python.exe simulate_brain.py --ms 1000 --hz 100 --seed 43
```

Pouhá kontrola sítě a export vah bez simulace:

```powershell
.\venv\Scripts\python.exe simulate_brain.py --inspect-only
```

Výstupy jsou v `results/sugar_200ms_150Hz_seed42/`, případně v adresáři podle argumentů.
Opakované spuštění se stejnými argumenty přepíše výsledky tohoto pokusu.

## Jaký experiment provádíme

1. **baseline:** síť bez vnější stimulace, z klidových počátečních podmínek.
2. **sugar:** stimulace 21 neuronů označených jako cukrové chuťové vstupy
   v původním `example.ipynb`. Každý dostává Poissonův vstup o zadané frekvenci.
3. **sugar_disconnected:** stejné vstupy a seed, ale jejich výstupní váhy jsou nulové.
   Tím ověřujeme, zda další aktivitu skutečně zprostředkují spoje sítě.

Sledujeme výboje všech neuronů a membránové napětí neuronu MN9,
FlyWire ID `720575940660219265`, který sledují i autoři příkladu.
Odpojení znamená vypnutí výstupních spojů, nikoli zablokování výbojů stimulovaných neuronů.
To odpovídá funkci `silence` v původním kódu; popis README je v tomto bodě obecnější.

Skript kontroluje shodu indexů s FlyWire ID a předpokládá, že bez vstupu nevzniknou výboje
a že odpojené vstupy nevyvolají výboje jiných neuronů.

## Kde vidět váhy a aktivitu

- `weights_sugar_and_MN9.csv`: všechny výstupní spoje cukrových vstupů a všechny vstupní
  spoje MN9. Sloupce obsahují ID zdroje a cíle, počet synapsí, znaménko a `weight_mV`.
- `connectome_summary.json`: velikost sítě, součty, znaménka vah a kontrolní součty zdrojů.
- `comparison.png`: výboje celé sítě a průběh napětí MN9 pro tři podmínky.
- `comparison.csv`: počty výbojů, aktivních neuronů a frekvence MN9.
- `*_rates.csv`: počet výbojů a průměrná frekvence každého neuronu, včetně neaktivních.
- `*_spikes.npz`: časy výbojů v ms, indexy neuronů a převod na FlyWire ID.
- `experiment.json`: parametry, seed a výsledky experimentu.

Velká FlyWire ID při importu CSV do Excelu nastav jako **text**, jinak může Excel
zaokrouhlit poslední číslice. Python je v těchto souborech čte jako 64bitová celá čísla.

Všechny váhy jsou dostupné v původním Parquet souboru:

```python
import pandas as pd

edges = pd.read_parquet(
    "external/Drosophila_brain_model/2023_03_23_connectivity_630_final.parquet"
)
edges["weight_mV"] = 0.275 * edges["Excitatory x Connectivity"]
print(edges.loc[edges["Postsynaptic_ID"] == 720575940660219265].head())
```

Vzorec původního modelu:

**váha = počet anatomických synapsí × znaménko účinku × 0,275 mV**.

Kladná váha v modelu budí, záporná tlumí. Váha je přírůstek synaptické proměnné `g`,
která dále ovlivňuje napětí neuronu; není to okamžitý skok membránového napětí.
Hodnota 0,275 mV je modelový parametr. Účinek spojení závisí i na dynamice a ostatních vstupech.
Počty spojů pocházejí z rekonstrukce; funkční síla každé biologické synapse přímo změřena nebyla.

## Jak vyhodnocovat „co to dělá“

Změna aktivity po vstupu a její zánik po odpojení ukazují příčinnou roli spojení **v modelu**.
Pozitivní výsledek není důkaz, že virtuální moucha vnímá cukr nebo vykonala pohyb.
Tato instalace nemá fyzikální tělo, smyslový model prostředí ani motorickou zpětnou vazbu.

Jde o zjednodušené neurony typu leaky integrate-and-fire se společnými parametry,
pevnými vahami a bez implementovaného učení. Jeden krátký pokus je technická demonstrace,
nikoli statistická reprodukce článku. Pro vědecké ověření je potřeba více seedů/opakování,
delší okno, křivka odpovědi na sílu vstupu, cílené vypínání prostředníků a srovnání
s měřeními na skutečných zvířatech. Autoři poskytují podrobnější experimenty v `figures.ipynb`.

Pro následné spojení s tělem lze zkoumat
[NeuroMechFly](https://neuromechfly.org), ale mapování výstupů mozku
na řízení těla a zpětných senzorických vstupů je další samostatný modelovací úkol.

## Ověřený první běh

Výchozí experiment (200 ms, 150 Hz, seed 42) proběhl 17. 9. 2026:

| Podmínka | Aktivní neurony | Výboje celkem | Výboje MN9 |
|---|---:|---:|---:|
| Bez vstupu | 0 | 0 | 0 |
| Cukrové vstupy | 353 | 2764 | 18 |
| Cukrové vstupy s odpojenými výstupy | 21 | 637 | 0 |

MN9 měl ve stimulovaném pokusu průměrnou frekvenci 90 Hz za celé 200ms okno.
Po odpojení zůstaly výboje pouze ve stimulovaných neuronech.
Každá podmínka včetně konstrukce sítě trvala na tomto počítači přibližně 7–9 sekund.
Ověření indexů, znamének vah a všechny tři kontroly simulace prošly.
Kompletní tabulka verze 630 zahrnuje součet 52 793 639 anatomických synapsí.

![První experiment](../results/sugar_200ms_150Hz_seed42/comparison.png)

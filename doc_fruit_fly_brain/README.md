# Mozek octomilky v Neuroglanceru

Nově je dostupný také jednoduchý **svět 30 × 30 s cukrem a Q-learningem**:

```powershell
.\venv\Scripts\python.exe pygame_world.py
```

[Návod ke světu a učení](doc/pygame_world_cz.md). Jde o samostatný herní model,
zatím bez napojení na neuronovou síť FlyWire.

Pro simulaci neuronové aktivity je nově připraven `simulate_brain.py` s kompletní sítí
FlyWire a simulátorem Brian 2. Postup, váhy a význam výsledků popisuje
[český návod k simulaci](doc/simulace_cz.md).

Interaktivní okno s posuvníkem vstupu a odpojováním prostředních neuronů:

```powershell
.\venv\Scripts\python.exe pygame_brain.py
```

Podrobnosti: [ovládání laboratoře v Pygame](doc/pygame_cz.md).

Připraveno pro existující `venv` s Pythonem 3.10 na Windows.
Neuroglancer zobrazuje 3D mikroskopická data a segmentaci; nesimuluje aktivitu mozku.

## Spuštění v PowerShellu

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe view_brain.py
```

Otevři adresu vypsanou v terminálu v prohlížeči s WebGL2 (například Chrome).
Terminál nech běžet; server ukončíš Ctrl+C. Server je dostupný pouze na localhostu.
Aktivace venv není nutná, příkazy používají přímo jeho Python.

V řezech se pohybuj kolečkem myši a tažením. Dvojklikem na segment vybereš neuron;
jeho část se může zobrazit i v 3D panelu. Vrstvu `Neurony` můžeš vypnout pro čistý EM obraz.
Lokální výřez obsahuje pouze fragmenty neuronů, jejich povrchy končí na hranicích výřezu.

## Stažená data

Veřejný **Janelia FlyEM Hemibrain v1.2**, výřez 256 × 256 × 256 voxelů
v původním rozlišení 8 × 8 × 8 nm (krychle o hraně 2,048 µm).
Hemibrain pokrývá část mozku dospělé octomilky, nikoli celý mozek.

- `data/em.npy`: obraz elektronové mikroskopie, uint8, přibližně 16 MiB.
- `data/segmentation.npy`: identifikátory neuronových segmentů, uint64, přibližně 128 MiB.
- `data/manifest.json`: zdroje, souřadnice XYZ, rozlišení a SHA-256 souborů.
- `data/*_info.json`: původní metadata veřejných objemů.

NumPy pole mají pořadí os **XYZ**, nikoli ZYX. Obě vrstvy mají stejný výřez
od [14976, 14976, 19968] do [15232, 15232, 20224] (horní mez se nezahrnuje).
ID segmentu není intenzita ani automaticky název typu neuronu.

Data již jsou stažena. Obnovení výřezu (přepíše lokální soubory):

```powershell
.\venv\Scripts\python.exe download_data.py
```

Pro průzkum celého dostupného objemu Hemibrain použij streamování z internetu:

```powershell
.\venv\Scripts\python.exe view_brain.py --remote
```

Tento režim načítá bloky podle pohledu; celý dataset nestahuje na disk.
Základní lokální režim používá již stažené pole a klienta dodaného v balíčku Neuroglancer.

## Zdroje

- [Neuroglancer: Python integration](https://github.com/google/neuroglancer/blob/master/python/README.md)
- [Oficiální vydání a zdroje dat Hemibrain v1.2](https://dvid.io/blog/release-v1.2/)
- [TensorStore: čtení Hemibrain](https://google.github.io/tensorstore/python/tutorial.html#reading-the-janelia-flyem-hemibrain-dataset)

Pro citování dat a podmínky použití navazuj na původní zdroj Hemibrain.

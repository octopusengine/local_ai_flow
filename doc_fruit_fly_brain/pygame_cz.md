# Interaktivní laboratoř v Pygame

## Spuštění

```powershell
.\venv\Scripts\python.exe pygame_brain.py
```

Závislosti jsou nainstalované. Při nové instalaci použij `install_simulation.ps1`;
obsahuje i Pygame 2.6.1 a směruje instalační cache na D:.

Při spuštění se automaticky připraví referenční pokus (150 Hz, 200 ms, seed 42).
První nový výpočet chvíli trvá. Okno mezitím reaguje; Brian 2 běží v samostatném procesu.
Opakované stejné pokusy používají uložené výsledky. Při zavření okna se jeho výpočet ukončí.

## Ovládání

1. **Síla chuťového vstupu:** táhni posuvník mezi 0 a 300 Hz. Jde o frekvenci
   Poissonova vstupu pro každý z 21 chuťových neuronů; nemění se tím váhy sítě.
2. **Prostředníci:** kliknutím na řádek neuronu odpoj jeho výstupní spoje.
   Dalším kliknutím je zapoj zpět. Lze vybrat více neuronů současně.
3. **Přepočítat / Enter:** provede pokus a porovná ho s referencí bez odpojení.
   Oba běhy mají stejnou frekvenci, délku a náhodný seed.
4. **Zapojit všechny / R:** zruší všechna odpojení. Potom použij Přepočítat.
5. **Pauza / mezerník:** ovládá zpomalené přehrávání vypočtených výbojů.
   Spodní posuvník pod sítí mění čas záznamu, nikoli sílu vstupu.
6. **Šipky vlevo/vpravo:** změna vstupu o 5 Hz. **Esc:** zavření okna.
7. Během výpočtu lze použít **Zrušit výpočet**. Nastavení experimentu je do jeho
   dokončení či zrušení zamčené; okno a přehrávání zůstávají ovladatelné.

## Co zobrazení znamená

Počítá se kompletní síť FlyWire 630: 127 400 neuronů. Pro přehlednost se zobrazuje
jen 13 skutečných prostředníků na dvoukrokových spojeních
**chuťové vstupy → prostředník → MN9**. Ostatní neurony a delší cesty se nadále účastní simulace.
Souřadnice v okně jsou schéma, nikoli anatomické umístění.

- Zelený uzel CUKR zastupuje 21 samostatně stimulovaných neuronů.
- Modré spoje jsou budivé, červené tlumivé; tloušťka přibližně odpovídá velikosti váhy.
- Číslo u prostředníka je původní modelová váha jeho spojení do MN9, v mV.
- Levý detail obsahuje celé FlyWire ID, součet vah z chuťových neuronů a váhu do MN9.
- Odpojený prostředník má červeně označený řádek a šedý výstupní spoj. Číslo původní
  váhy zůstává viditelné, ale simulátor vynuluje **všechny** jeho výstupní váhy v celé síti.
- Žluté bliknutí znamená výboj v posledních 3 ms přehrávaného záznamu. Není to
  animace odhadnutá z grafu. I neuron s odpojenými výstupy může dál vysílat výboje.
- Šedý průběh dole je reference, zelený zásah. Pod napětím jsou skutečné časy výbojů MN9.
- „Aktivní síť“ uvádí počet neuronů s alespoň jedním výbojem v celé síti.

Po změně parametrů je stav označen **ZMĚNY ČEKAJÍ**, blikání se pozastaví a spodní
graf zůstává jasně označený jako poslední výpočet. Nové nastavení začne platit až po přepočtu.
Čas záznamu se přehrává zpomaleně (200 ms biologického času za 8 sekund), nejde o živou simulaci.

## První pokus

Nech 150 Hz a odpoj horního prostředníka `720575940627847752`.
Při ověření se odpověď MN9 snížila z **18 na 13 výbojů**, tedy z **90 na 65 Hz**
v okně 200 ms. Počet aktivních neuronů celé sítě klesl z 353 na 316.
Při 0 Hz nevznikly žádné výboje. Při 150 Hz byly vstupní výboje ve srovnávaných
podmínkách totožné, takže rozdíl nebyl způsoben jiným náhodným vstupem.

Výsledek ukazuje vliv zásahu v tomto modelu a pokusu. Samotný nákres dvoukrokové cesty
neprokazuje, že odezva proběhla výhradně přes ni: působí i zbytek sítě a zpětné vazby.
Vypnutí tlumivého neuronu může odpověď také zesílit. Pro silnější závěr potřebujeme
další intenzity, opakování a experimentální data. Viz [popis simulace](simulace_cz.md).

## Soubory a ověření

Všechny výstupy jsou na D: v adresáři projektu:

- `results/pygame_lab/graph.json`: odvozené dvoukrokové cesty a váhy.
- `results/pygame_lab/runs/<klíč>/`: konfigurace, JSON výsledku, výboje celé sítě
  v `all_spikes.npz` a frekvence všech neuronů v `rates.csv`.
- `results/pygame_lab/jobs/<id>/`: konkrétní požadavek GUI, odpověď a `worker.log` pro chyby.
- `.runtime/`: dočasné soubory a cache simulátoru na D:.

Klíč uloženého výpočtu zahrnuje parametry i kontrolní součty backendu, modelu a dat.
V JSON jsou velká FlyWire ID řetězce, aby se neztrácela přesnost.

Test ovládání bez nativního okna a integrační test se skutečným modelem:

```powershell
.\venv\Scripts\python.exe -m unittest test_pygame_brain -v
```

Testuje se posuvník, přepínání neuronů, změna velikosti okna, zrušení vlastního procesu,
odezva okna během výpočtu, porovnání zásahu s referencí a nulový vstup.

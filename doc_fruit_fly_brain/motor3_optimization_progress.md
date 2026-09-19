# Průběžný stav optimalizace motor3 — 18. 9. 2026

## Zadání a stav

Cíl: slepá muška má sledovat vůni cukru. Výchozí podklady jsou
`temp_report/navrh.md`, `260918_1945_log.txt` a snímek posledního stavu.
Uživatel dodatečně navrhl upravit intenzitu vůně a požádal o uložení
průběžného stavu. **Optimalizace není dokončena a spolehlivé navádění
čichem zatím nebylo prokázáno.**

`pygame_fly.json` už při zahájení práce odkazoval na `pygame_fly_motor3.json`;
motor3 byl obsahově shodný s motor2. Motor1 a motor2 zůstaly nezměněné.
Aktuální motor3 je pokusná, zatím nepotvrzená varianta a při příštím spuštění
aplikace se načte automaticky. Pro původní chování lze v hlavním JSON nastavit
`motor_matrix_file` na `./pygame_fly_motor2.json`.

## Zjištění z dodaného logu

- Plná síť, skutečné spoje, brain seed 42, world seed 31, čich 150 Hz,
  vypnuté oči, 101 kroků, 3 snězené cukry.
- 92 ze 101 zatáček mělo požadavek alespoň 45° a bylo omezeno limitem těla.
  Už první požadavek byl +1391,24°. Jednotlivé výstupy jsou v Hz, nikoli 0–1.
- Rozdíl DNge037 R−L koreloval se současným rozdílem vůně R−L jen r≈0,147;
  DNg35 r≈0,075. Anatomická strana sama neprokazuje funkci zatáčení.
- Původní motor2 měl všechny 3 cukry už v prvních 48 krocích. Počet cukrů
  sám nerozlišuje náhodné prohledávání od skutečného následování gradientu.

## Provedené změny

1. `pygame_fly_motor3.json`: gain 1, dopředné váhy DN L/R po 0,085,
   MN9 −0,015; zatáčení DN L/R −0,8/+0,8, DNge037 L/R −0,5/+0,48.
   DNg35 má nulovou váhu. Vyvážení DNge037 přibližně kompenzuje rozdílnou
   průměrnou aktivitu při stejné levé a pravé vůni v dodaném logu.
   Jde o konzervativní odstranění saturace, ne o prokázaný dekodér směru.
2. `fly_settings.py`: volitelné `odor_stimulus_hz`, null nebo číslo 0–300.
   Null zachovává původní ovládání společným `stimulus_hz`.
3. `fly_connectome.py`: čich má vlastní intenzitu, ostatní kanály se nemění.
   Funguje pro skutečnou síť i direct režim. `requested_hz` ukazuje skutečné
   požadované frekvence; koncentrace v `inputs` zůstávají nezměněné.
   `Brain.step(..., odor_strength=...)` umožňuje explicitní testovací override.
4. `pygame_fly.py`: zobrazení maxima čichu v Hz a zápis nastavení do logu.
5. `test_fly.py`: kontrola validace, oddělení čichu od ostatních vstupů,
   vypnutí nulovou intenzitou a předání nastavení subprocessu.
6. `optimize_fly_motor3.py`: opakovatelné sondy plné sítě, analýza a simulace
   pohybu s uložením skutečně použité matice, nastavení a úplné trajektorie.

Hlavní `pygame_fly.json` se zatím neměnil. Čich proto zůstává na 150 Hz.
Pro samostatné nastavení stačí přidat například `"odor_stimulus_hz": 75`;
`"odor_stimulus_hz": null` obnoví společnou intenzitu. Změny platí po restartu.
Synaptické váhy, mapa smyslových neuronů ani fyzika světa se neměnily.

## Dokončená měření

Výsledky: `results/fly/motor3_optimization/`.

- Přepočet původních 101 neuronových výstupů novou maticí: 0 oříznutých
  zatáček, maximum |turn| 27,69°, průměr forward 0,599. **Toto není nová
  trajektorie:** po změně pohybu by síť dostávala jiné vstupy.
- `probes.json`: pouze částečná sonda 150 Hz, 16 oken; byla přerušena po
  rozšíření zadání o intenzitu. Nepoužívat jako dokončené porovnání.
- `probes_30hz.json`, `probes_75hz.json`: každá 32 oken po 50 ms, brain seed
  42, 8 podmínek po 4 oknech v deterministicky promíchaném pořadí.
  Síť se resetuje mezi intenzitami, nikoli mezi podmínkami; test tedy zahrnuje
  přetrvávání aktivity po změně či odebrání vůně.
- Zkoušely se L/R koncentrace (1,0), (0,1), (0.5,0.5), (0.25,1), (1,0.25),
  (0,0), (0.5,1), (1,0.5). Měřeny byly všechny sestupné neurony.
- Analýza vynechává první 4 okna po resetu. Výběr 2/4/8 neuronů probíhá
  uvnitř každého trénovacího oddílu; vynechaná podmínka slouží ke kontrole.
  Nejlepší MSE pro odhad odor R−L: 30 Hz **0,484**, 75 Hz **0,568**;
  konstantní nulový odhad má **0,4375**. Zde se tedy použitelný dekodér nenašel.
  Jde o malý průzkumný test, ne o důkaz nemožnosti jiné matice nebo intenzity.
- `python -m unittest test_fly`: **15 testů prošlo**.

## Rozpracovaná zkouška a pokračování

Při zahájení ukládání checkpointu běží:

```powershell
.\venv\Scripts\python.exe optimize_fly_motor3.py compare --names motor3 --steps 48 --seeds 31 --odor-strength 150
```

Poslední známý dílčí stav byl 36/48 kroků, 0 cukrů, 24 různých buněk.
Výsledek se ukládá po dokončení do
`motor3_world31_brain42_150hz.json`. Před opakováním zkontrolovat jeho
existenci a závěrečný záznam níže. Nelze zatím vydávat motor3 za zlepšení
úspěšnosti hledání potravy; méně saturace může znamenat pouze rovnější pohyb.

Další postup:

1. Vyhodnotit dokončenou trajektorii a porovnat prvních 48 kroků dodaného
   motor2, nikoli 48 kroků s celými 101 kroky baseline.
2. Pokud hledání zhoršuje, zatím nepovažovat tento motor3 za hotový výsledek.
   Původní motor2 zůstává dostupný. Zkoušet kompromis intenzity zatáčení,
   případně vyšší čichový vstup; nižší intenzity zatím nepomohly dekódování.
3. Přesvědčivého kandidáta zkontrolovat na jiném world/brain seedu a s
   vypnutým nebo prohozeným čichem. Dosud nebyla provedena nezávislá
   validace nového řízení ani test 300 Hz.
4. Statická matice nemá paměť pro filtrování šumu. Ve světě navíc existují
   oblasti bez vůně a ploché úseky čichového pole. Případné další zásahy do
   motorického adaptéru či profilu vůně je nutné odlišit od úprav vah motor3.

Checkpoint je kopie zdrojů, konfigurace a měření; ne serializovaný stav
membránových potenciálů běžící sítě.

## Závěrečný záznam při uložení

Zkouška doběhla: **48 kroků, 0 cukrů, 29 různých buněk, 28 úspěšných
přesunů, 2 kolize, 0 oříznutých zatáček**. Výše uvedený výsledkový JSON
je kompletní. Oproti 3 cukrům v prvních 48 krocích dodaného motor2 jde
na této mapě o zhoršení sběru; zlepšila se pouze saturace motorického příkazu.
Žádná experimentální úloha nyní neběží. Uživatel bude variantu dále testovat
a dodá reporty. Na jeho přání ponecháváme průběžnou variantu motor3
k testování, bez dalšího automatického přelaďování.

Uloženo v `results/fly/checkpoints/20260918_210105_motor3/` spolu se zdroji,
konfigurací, vstupním reportem, naměřenými výsledky a SHA-256 manifestem.
Velké datové soubory, prostředí venv a nezměněný externí model nejsou
duplikovány; kopie slouží k obnově souborů v původním projektu.

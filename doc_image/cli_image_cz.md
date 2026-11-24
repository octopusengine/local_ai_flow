# cli_image.py — český návod

`cli_image.py` je konzolový nástroj pro práci s obrázky pomocí `QwenImage21Pipeline` z knihovny Diffusers. Umí vytvořit obrázek z textového zadání, upravit jeden existující obrázek, stejným zadáním upravit více souborů nebo vytvořit společný výsledek z několika referencí. Tento návod popisuje implementaci skriptu ve verzi `0.91` a runner `runner_image.py` ve verzi `v0.82`.

## 1. Soubory a příprava

Nástroj používá dva základní soubory:

- `cli_image.py`: spustitelný Python skript.
- `cli_image.json`: konfigurace modelu, zadání, výstupu a parametrů výpočtu.

Dále může používat textový soubor se zadáním, vstupní obrázky a adresáře `src` a `dest`.

```text
pracovní_adresář/
├── cli_image.py
├── cli_image.json
├── prompt.txt
├── src/
│   ├── 01_osoba.png
│   └── 02_pozadi.jpg
└── dest/
```

Příkazy v návodu spouštějte z kořenového adresáře projektu. Konfigurace se vždy hledá pod názvem `cli_image.json` v **aktuálním pracovním adresáři**, nikoli automaticky vedle skriptu. Stejně se vyhodnocují relativní cesty k modelu, přímo zadaným souborům zadání, vstupům a výstupům. Výjimkou je hledání promptů přes pole `prompt_file` a zkratky `/název`, viz kapitola 3. Skript nemá přepínač pro jiný konfigurační soubor.

Je potřeba Python prostředí s knihovnami `torch`, `Pillow` a verzí `diffusers`, která obsahuje `QwenImage21Pipeline`, včetně závislostí požadovaných modelem. Model musí být již uložen v místním adresáři. Položka `model` se kontroluje jako existující adresář; samotný identifikátor vzdáleného modelu nestačí. Instalační postup pro prostředí na Macu je archivován v [qwen_img_install.md](qwen_img_install.md).

Zobrazení nápovědy a verze:

```sh
python cli_image.py --help
python cli_image.py --version
```

Tyto příkazy nenačítají model ani konfiguraci, ale importy knihoven proběhnou ještě před zpracováním argumentů. Chybějící knihovna tedy může zabránit i zobrazení nápovědy.

## 2. Konfigurace cli_image.json

Příklad konfigurace s parametry, které skript skutečně používá:

```json
{
  "model": "/Users/yenda/ai/models/Qwen-Image-2.1",
  "prompt_file": "prompt.txt",
  "input": {
    "edit_file": "./src/image.png"
  },
  "output": {
    "name": "out_",
    "format": "png"
  },
  "generation": {
    "width": 1024,
    "height": 1024,
    "num_inference_steps": 30,
    "seed": null,
    "strength": 1.0
  },
  "device": "mps",
  "dtype": "bfloat16"
}
```

Cestu k modelu upravte podle počítače. Ve Windows lze v JSONu použít například `"D:/models/Qwen-Image-2.1"`; zpětná lomítka je potřeba zdvojit, například `"D:\\models\\Qwen-Image-2.1"`. JSON nepovoluje komentáře ani čárku za poslední položkou.

| Položka | Výchozí hodnota při vynechání | Význam |
| --- | --- | --- |
| `model` | Povinná | Cesta k místnímu adresáři modelu. |
| `prompt_file` | Povinná | Cesta k výchozímu zadání nebo neprázdné pole cest pro hledání v pořadí; obsah se použije, pokud není zadáno `-p`. |
| `input.source` | `"./src"` | Zdrojový adresář pro `-a`; přepíše jej `--src`. |
| `output.destination` | `"./dest"` | Cílový adresář pro `-a`; přepíše jej `--dest`. |
| `output.overwrite` | `true` | Povolit přepsání; při `false` přidá při kolizi `-d`. Přijímá také řetězce `"true"` a `"false"`. |
| `generation.num_inference_steps_turbo` | `8` | Počet kroků při `-M turbo`; přepíše jej `-t`. |
| `input.edit_file` | Žádná | Skript položku načítá, ale v současném CLI není dostupná cesta, která by ji použila jako výchozí vstup: `-e` vyžaduje vlastní argument. |
| `output.name` | `"output"` | Základ názvu výstupu; může obsahovat cestu. |
| `output.format` | `"png"` | `png`, `jpg` nebo `jpeg`; přijímá i velká písmena či úvodní tečku. |
| `generation.width` | `1024` | Šířka pro generování a spojení referencí, celé číslo alespoň 1. |
| `generation.height` | `1024` | Výška pro generování a spojení referencí, celé číslo alespoň 1. |
| `generation.num_inference_steps` | `30` | Počet kroků výpočtu, celé číslo alespoň 1. |
| `generation.seed` | `null` | Počáteční seed; `null` znamená náhodný seed pro každý výstup. Používejte celé číslo nebo `null`. |
| `generation.strength` | `1.0` | Řízení počáteční hodnoty sigma při editaci a spojení referencí; rozsah 0 až 1. |
| `device` | `"mps"` | Zařízení: `mps`, `cuda` nebo `cpu`. |
| `dtype` | `"bfloat16"` | Datový typ: `float32`, `float16` nebo `bfloat16`. |

**Pozor na `sigma_start`:** současný soubor `cli_image.json` obsahuje `"sigma_start": 0.99`, ale skript tuto položku vůbec nečte. Pro odpovídající nastavení použijte `"strength": 0.99` v sekci `generation` nebo argument `-r 0.99`. Pokud `strength` chybí, použije se `1.0`.

### Zařízení a datový typ

- `mps` je určeno pro dostupný backend Apple MPS.
- `cuda` vyžaduje dostupnou CUDA v PyTorchi.
- `cpu` spouští výpočet na procesoru.

Skript kontroluje dostupnost MPS a CUDA a při nedostupnosti skončí chybou. Nepřepíná automaticky na CPU. U `dtype` ověřuje pouze název typu; funkčnost konkrétní kombinace zařízení a typu závisí na prostředí a pipeline.

Příklad změny konfigurace pro prostředí s CUDA:

```json
"device": "cuda",
"dtype": "bfloat16"
```

Příklad nastavení CPU:

```json
"device": "cpu",
"dtype": "float32"
```

Jde o části JSONu, které je potřeba vložit do celého konfiguračního objektu. Zařízení ani datový typ nelze změnit argumentem příkazové řádky.

## 3. Zadání neboli prompt

Bez `-p` se načte obsah souboru z `prompt_file`. Soubor může být víceřádkový a musí obsahovat neprázdný text v UTF-8.

`prompt_file` může být také pole adresářů, například `"prompt_file": ["prom", "prom_test"]`.
Každá položka pole je vždy adresář, bez odvozování podle přípony či existence.
CLI (`-p /dance` nebo `-b /dance`) i runner (`@join(/dance, "kresba")`) hledají `dance.txt` ve stejném pořadí: `./prom/dance.txt`, potom `./prom_test/dance.txt`.
Pole s jedinou položkou, například `["prom_test"]`, hledá pouze v tomto adresáři.
Bez `-p` CLI hledá výchozí `prompt.txt` postupně v uvedených adresářích.
Relativní adresáře v poli jsou v obou programech vůči adresáři skriptu. Totéž platí pro zkratky `/název`. Řetězcový výchozí `prompt_file` bez `-p` vyhodnocuje CLI vůči pracovnímu adresáři. Při spuštění přes runner se pracovní adresář nastaví na adresář runneru.
Přechází se dál pouze při nenalezení souboru; prázdný nebo nečitelný nalezený soubor je chyba.
Původní zápis s řetězcem nadále vybírá výchozí soubor CLI; `/název` se v obou programech hledá vedle tohoto souboru.

```sh
python cli_image.py
```

Přímé zadání textu:

```sh
python cli_image.py -p "Fotografie horského jezera za úsvitu, jemná mlha, přirozené světlo."
```

Použití jiného textového souboru:

```sh
python cli_image.py -p ./prompts/krajina.txt
```

Pokud hodnota `-p` ukazuje na existující soubor, skript načte jeho obsah. V opačném případě ji považuje za samotný text zadání. Překlep v cestě tedy může způsobit, že se jako prompt použije například text `./prompts/neexistuje.txt`.

Položka `prompt_file` musí být v JSONu přítomná i při použití `-p`, ale její cílový soubor v takovém případě nemusí existovat. Bílé znaky na začátku a konci zadání se odstraňují; prázdné zadání je chyba.

Od verze `v0.76` lze pomocí `-b` / `--base` předřadit základní prompt. Stejně jako `-p` přijímá text nebo cestu k existujícímu textovému souboru. Základ a hlavní prompt se oddělí prázdnou řádkou (`\n\n`). Bez `-b` se zadání nemění. Základ se přidává také před prompt načtený z konfigurace; prázdný základ je chyba.

```sh
python cli_image.py -b "pes" -p "velký černý"
python cli_image.py --base ./prompts/base.txt -p ./prompts/detail.txt
```

První příkaz složí zadání `pes\n\nvelký černý`.

## 4. Přehled argumentů

| Argument | Význam |
| --- | --- |
| `-h`, `--help` | Zobrazí nápovědu. |
| `-V`, `--version` | Zobrazí verzi skriptu. |
| `-N POČET` | Počet výstupů, minimálně 1; výchozí je 1. Má význam pro generování, editaci jednoho obrázku a merge. |
| `-p`, `--prompt TEXT_NEBO_SOUBOR` | Přímé zadání nebo cesta k textovému souboru. |
| `-b`, `--base TEXT_NEBO_SOUBOR` | Základní prompt předřazený před hlavní zadání s prázdnou řádkou. |
| `-f`, `--file ZÁKLAD` | Základ názvu výsledných souborů. |
| `-n`, `--name ZÁKLAD` | Přepíše základ názvu; má přednost i před `-f`. |
| `-s`, `--seed ČÍSLO` | Přepíše seed z JSONu. |
| `-t`, `--steps POČET` | Přepíše počet kroků, minimálně 1. |
| `-r`, `--strength HODNOTA` | Síla v rozsahu 0 až 1 pro editaci a merge. |
| `-W`, `--width PIXELY` | Šířka pro generování a merge, minimálně 1. |
| `-H`, `--height PIXELY` | Výška pro generování a merge, minimálně 1. |
| `-e`, `--edit OBRÁZEK` | Editace konkrétního vstupního obrázku. Cesta je povinná. |
| `-a`, `--all` | Hromadná editace obrázků z `./src` do `./dest`. |
| `--src ADRESÁŘ`, `--dest ADRESÁŘ` | Přepíšou zdrojový a cílový adresář pro `-a`. |
| `-x`, `--suffix PŘÍPONA` | Přípona názvu pro `-a`, výchozí `e`; například `-x j` vytvoří `foto_j.jpg`. |
| `-M`, `--model turbo` | Použije model Qwen-Image-2.1-Turbo ze sousedního adresáře modelu. |
| `-m`, `--merge` | Vytvoření výsledku ze všech vhodných referencí v `./src`. |
| `--files OBRÁZEK [OBRÁZEK ...]` | Výběr konkrétních vstupů pro `-m` v zadaném pořadí místo načtení `./src`. |

Velikost písmen je důležitá: počet výstupů je `-N`, šířka `-W` a výška `-H`. `-h` zobrazí nápovědu.

Argumenty obvykle přepisují JSON. Výjimkou je validace: šířka, výška, kroky a `strength` v JSONu se kontrolují **před** aplikací přepínačů. Chybnou hodnotu v JSONu tedy nelze obejít platným argumentem. Také `output.format` a neprázdný název výstupu se kontrolují v hromadném režimu, i když se pro jeho výsledné názvy nepoužívají.

## 5. Režim generování z textu

Generování je výchozí režim, pokud nepoužijete `-e`, `-a` ani `-m`. Přítomnost `input.edit_file` v JSONu editaci nezapíná.

```sh
python cli_image.py -p "Ilustrace starého majáku u moře." -f majak_
```

Při formátu `png` vznikne `majak_.png` (jeden výstup se nečísluje).

### Více variant

```sh
python cli_image.py -N 4 -p "Ilustrace starého majáku u moře." -f majak_ -s 1234
```

Výstupy jsou `majak_1.png` až `majak_4.png`; použité seedy jsou 1234, 1235, 1236 a 1237. Každý obrázek vzniká samostatným voláním pipeline.

### Variace rozměrů a kroků

```sh
python cli_image.py -p ./prompts/krajina.txt -W 1536 -H 1024 -t 40 -f krajina_
python cli_image.py -p "Portrét v měkkém světle." -W 768 -H 1024 -t 30 -f portret_
python cli_image.py -p "Jednoduchá ikona stromu." -W 512 -H 512 -t 20 -f ikona_
```

Příklady ukazují syntaxi pro vodorovný, svislý a čtvercový výstup. Skript sám kontroluje pouze kladné rozměry; další omezení a případné úpravy rozměrů závisí na pipeline. Vyšší rozlišení a více kroků obvykle zvyšují výpočetní náročnost. `strength` se při běžném generování nepoužívá.

## 6. Editace jednoho obrázku

```sh
python cli_image.py -e ./src/foto.jpg -p "Změň pozadí na zasněžené hory, zachovej hlavní postavu." -f uprava_
```

Při `output.format: "png"` se výsledek uloží jako `uprava_.png`. Vstup může být PNG, JPG nebo JPEG; výstupní formát se řídí JSONem a nemusí odpovídat vstupu.

### Více úprav stejného vstupu

```sh
python cli_image.py -e ./src/foto.jpg -N 3 -p ./prompts/uprava.txt -s 200 -t 35 -r 0.8 -f uprava_
```

Vzniknou tři varianty s hodnotami seedu 200, 201 a 202. Každá vychází ze stejného původního obrázku, nikoli z výsledku předchozí úpravy.

`-W` a `-H` se při editaci jednoho obrázku nepředávají pipeline. Rozměry výsledku zde určuje pipeline z editovacího vstupu. Skript sice nastavenou velikost vypisuje, ale tento výpis neznamená, že se při editaci uplatní.

Samotné `-e` bez cesty není platný příkaz. Pro vstup z uvedeného JSONu proto použijte například `-e ./src/image.png`.

## 7. Hromadná editace

```sh
python cli_image.py -a -p "Uprav fotografii do teplých podzimních barev." -r 0.8 -t 30 -s 500
```

Cesty se načítají z `input.source` a `output.destination` v JSONu (výchozí hodnoty `./src` a `./dest`). Parametry `--src` a `--dest` je přepíšou, každý samostatně:

```sh
python cli_image.py -a --src "./src2" --dest "./dest2"
```

Skript prochází přímo zdrojový adresář, vybere PNG/JPG/JPEG a zpracuje každý soubor jednou. Podadresáře neprochází. Použije stejné zadání a nastavení pro všechny vstupy.

| Vstup | Výstup |
| --- | --- |
| `src/foto.jpg` | `dest/foto_e.jpg` |
| `src/obrazek.png` | `dest/obrazek_e.png` |
| `src/scan.JPEG` | `dest/scan_e.jpeg` |

Adresář `dest` se vytvoří automaticky. Zachová se přípona vstupu, převedená na malá písmena. Soubory, jejichž název bez přípony končí na `_e` bez ohledu na velikost písmen, se ve `src` přeskočí.

V tomto režimu:

- `-N` nemění počet úprav; vzniká právě jeden výstup pro každý vybraný soubor.
- `-f`, `--name` a `output.format` neurčují názvy ani formáty výsledků.
- `-W` a `-H` se při editaci nepoužívají.
- Vstupy jsou seřazené podle cest. Pevný seed je v režimu `-a` stejný pro všechny vstupy. Bez pevného seedu dostane každý vstup náhodný seed.

Pokud jedna úprava selže, skript pokračuje dalšími soubory. Na konci vypíše počty úspěchů a chyb; při alespoň jedné chybě vrátí návratový kód 1.

## 8. Spojení více referencí — merge

Režim `-m` předá pipeline seznam obrázků z `./src` a společné textové zadání. Jde o tvorbu výsledku s více referencemi; způsob propojení určujete promptem.

Konkrétní reference lze vybrat pomocí `--files`; `-f / --file` nadále označuje název výstupu:

```sh
python cli_image.py -m --files ./dest/temp/t_bg7.png ./dest/temp/t_gr7.png -p "A graphic." -n ./dest/temp/t_fin7
```

V runneru sestavíte seznam pomocí `@files(...)`. Jednotlivé cesty se předají samostatně, včetně cest s mezerami:

```text
@for S in 7..8
  $i1 = "./dest/temp/${A}_bg${S}"
  $i2 = "./dest/temp/${A}_gr${S}"
  $f = @files($i1,$i2)
  python cli_image.py -m --files $f -p "$G" -n ./dest/temp/${A}_fin${S} -t $T -s $S
@endfor
```

Před tímto úsekem nastavte `$A`, `$G`, `$T` a vytvořte vstupní obrázky.
Cestám bez přípony se doplní `output.format` z konfigurace. Explicitně vybrané soubory se použijí v zadaném pořadí, včetně názvů končících `_e`. Platí limit 10 referencí a kontrola existence a formátu PNG/JPG/JPEG. Bez `--files` zůstává výběr ze `./src`.

Například připravte tyto vstupy:

```text
src/
├── 01_osoba.png
└── 02_zahrada.jpg
```

```sh
python cli_image.py -m -p "Umísti osobu z prvního obrázku do zahrady z druhého obrázku. Sjednoť osvětlení." -W 1536 -H 1024 -f spojeni_
```

Při formátu PNG vznikne `spojeni_.png`. Pořadí referencí odpovídá seřazenému seznamu cest; skript vypisuje přiřazení `<image1>`, `<image2>` atd. Číselné prefixy souborů usnadňují kontrolu pořadí.

### Několik variant stejného spojení

```sh
python cli_image.py -m -N 3 -p ./prompts/spojeni.txt -s 1000 -r 0.9 -t 35 --name ./vysledky/spojeni_
```

Vzniknou `vysledky/spojeni_1.png` až `vysledky/spojeni_3.png`, pokud je výstupní formát PNG. Všechny varianty používají stejnou sadu referencí.

Výběr souborů je stejný jako při `-a`: pouze přímé soubory PNG/JPG/JPEG, bez názvů končících na `_e`. Skript vyžaduje alespoň jednu referenci a povoluje nejvýše 10. Při větším počtu skončí chybou; nevybírá automaticky prvních deset.

## 9. Podrobnosti parametru strength

`-r` / `--strength` a `generation.strength` platí pro editaci jednoho obrázku, hromadnou editaci a merge. Skript tento parametr realizuje vlastním rozvrhem hodnot sigma, protože použitá pipeline nemá nativní argument `strength`.

- `1.0` použije výchozí rozvrh pipeline a předá počet kroků jako `num_inference_steps`.
- Hodnota menší než `1.0` vytvoří lineární seznam sigma o délce počtu kroků.
- Počáteční sigma je `max(strength, 1 / steps)`, konečná sigma je `1 / steps`.
- Při vlastním rozvrhu skript předává `sigmas` a vynechá `num_inference_steps`.

Například při 30 krocích a `-r 0.8` vznikne 30 hodnot od 0.8 do přibližně 0.0333. Hodnoty síly pod `1 / steps` vedou ke stejnému rozvrhu; `-r 0` tedy neznamená prosté zkopírování vstupu beze změn.

Nižší hodnota je zamýšlena jako slabší náhodná variace. Výsledek však závisí na modelu, zadání a vstupu. Nejde o procento změny obrázku ani o klasický parametr img2img ze Stable Diffusion.

Pro porovnání použijte stejný vstup, prompt a seed a měňte pouze sílu:

```sh
python cli_image.py -e ./src/foto.jpg -p ./prompts/uprava.txt -s 42 -r 0.6 -f sila_06_
python cli_image.py -e ./src/foto.jpg -p ./prompts/uprava.txt -s 42 -r 0.9 -f sila_09_
python cli_image.py -e ./src/foto.jpg -p ./prompts/uprava.txt -s 42 -r 1.0 -f sila_10_
```

## 10. Seed a opakovatelnost

Pokud je seed v JSONu `null` a neuvedete `-s`, pro každý výstup se vybere náhodné celé číslo v rozsahu 0 až `2^32 - 1`. Skutečná hodnota se vypíše do konzole.

Pevný seed můžete zadat v JSONu nebo na příkazové řádce:

```sh
python cli_image.py -p "Dřevěná chata v lese." -s 42 -f chata_
```

Pro více výstupů se používá `seed + index`: při `-N 3 -s 42` tedy 42, 43 a 44. V hromadné editaci `-a` se naopak pevný seed nemění: všechny vstupy použijí tutéž hodnotu.

Stejný seed pomáhá porovnávat nastavení, ale shodný výsledek napříč různými zařízeními, verzemi knihoven a datovými typy není zaručen. Skript seed neukládá do samostatného souboru s metadaty. CLI také nemá přepínač, který by pevný seed z JSONu přepsal na `null`; pro návrat k náhodným seedům změňte JSON.

## 11. Názvy, cesty a formáty výstupů

V režimech generování, editace jednoho obrázku a merge se názvy řídí počtem výstupů:

- Bez `-N` nebo s `-N 1`: `základ.formát`, bez pořadového čísla.
- S `-N 2` a více: `základ1.formát`, `základ2.formát` atd.; oddělovač se nepřidává automaticky.

| Základ názvu | Počet | Formát | Výstup |
| --- | --- | --- | --- |
| `out` | 1 | `png` | `out.png` |
| `out_` | 1 | `png` | `out_.png` |
| `out_` | 3 | `png` | `out_1.png` až `out_3.png` |
| `./dest/test` | 1 | `jpeg` | `dest/test.jpeg` |

Argumenty `-f` a `-n` jsou základy bez přípony. Například `-f obrazek.png` při jednom výstupu vytvoří `obrazek.png.png`.

Pokud uvedete `-f` i `--name`, vyhraje `--name`:

```sh
python cli_image.py -p "Zátiší s ovocem." -f prvni_ --name ./dest/ovoce_
```

Výstup bude `dest/ovoce_.png`, je-li formát PNG. Chybějící rodičovské adresáře výstupu se vytvářejí automaticky.

**Přepisování řídí `output.overwrite` (výchozí `true`).** Při `false` se kolize řeší přidáváním `-d` před příponu: `img.png`, `img-d.png`, `img-d-d.png`. Číslování při více výstupech začíná při každém spuštění znovu od 1. Pro jednotlivé experimenty proto použijte odlišný základ názvu nebo adresář.

JPEG se ukládá jako RGB s kvalitou 95 a optimalizací. PNG se ukládá s optimalizací a podporuje režimy RGB/RGBA. Vstupní obrázky se ale před předáním modelu vždy převádějí na RGB, takže průhlednost vstupního PNG se nezachovává jako alfa kanál pro editaci. Volba PNG sama o sobě nezaručuje průhledný výsledek.

## 12. Omezení a běžné chyby

| Situace | Vysvětlení / postup |
| --- | --- |
| Chybí `cli_image.json` | Spusťte příkaz ze správného pracovního adresáře a připravte konfiguraci. |
| Neplatný JSON | Opravte syntaxi; chyba uvádí řádek a sloupec. Kořenem musí být objekt. |
| Chybí `model` nebo `prompt_file` | Obě položky jsou povinné, i když prompt zadáváte přes `-p`. |
| Model neexistuje | Nastavte cestu k existujícímu místnímu adresáři modelu. |
| Prázdný prompt | Vyplňte soubor zadání nebo argument `-p`. |
| MPS/CUDA nejsou dostupné | Upravte `device` podle skutečně dostupného backendu. |
| `-e` bez argumentu | Přidejte konkrétní cestu k obrázku. |
| Současně `-e`, `-a` nebo `-m` | Tyto tři přepínače se vzájemně vylučují. Vyberte jeden režim. |
| Ve `src` nejsou vstupy | Zkontrolujte přípony, přímé umístění souborů a koncovku `_e`. |
| Více než 10 referencí při merge | Zmenšete sadu vstupů v `src`. |
| Nepodporovaný formát | Použijte PNG, JPG nebo JPEG. |
| Nedostatek paměti | Zkuste menší rozměry při generování/merge nebo méně referencí; skript nemá CLI přepínač pro offload. |

Skript nemá argumenty pro masku, negativní prompt, guidance scale, výstupní formát. Nepodporované argumenty odmítne parser. Neznámé položky v JSONu, například `sigma_start`, se mohou jednoduše ignorovat.

Před výpočtem se vypisuje režim, model, zařízení, datový typ, parametry a prompt. Model se načítá jednou za spuštění a opakovaně používá pro jeho výstupy. Chyby jednotlivých výpočtů se vypisují jako `ERROR`; zpracování dalších položek pokračuje a při neúspěšném výsledku skript končí kódem 1. Běh lze přerušit pomocí `Ctrl+C`.

## Verze 0.79: ochrana před přepsáním

V `cli_image.json` nastavte v sekci `output`:

```json
"output": {
  "name": "out_",
  "format": "png",
  "overwrite": "false"
}
```

Podporováno je také JSON `false` bez uvozovek. Při kolizi vznikají
`img.png`, `img-d.png`, `img-d-d.png` atd. Přípona `-d` se přidává před
příponu souboru a pouze dokud je název obsazený. Platí pro generování,
editaci i slučování, včetně názvů z `-n` a více obrázků přes `-N`.
Skutečná uložená cesta se vypisuje jako `Saved:`.
Hodnota `true` nebo `"true"` povolí přepisování. Pokud parametr chybí,
zůstává původní chování (přepisování). Neplatná hodnota vyvolá chybu.

### Zdrojový a cílový adresář (0.8)

Při `-a` se cesty načítají z `input.source` a `output.destination` v JSONu. Parametry `--src` a `--dest` mají přednost, každý samostatně. Pokud chybí i položky v JSONu, použije se `./src` a `./dest`.

Parametry parser přijímá i bez `-a`, v ostatních režimech však nemají vliv. `-e` používá přímo zadanou cestu a `-m` bez `--files` vybírá obrázky z `./src`. Výstupní názvy v těchto režimech zůstávají beze změny.


## 13. Model Turbo a další nastavení verze 0.91

```sh
python cli_image.py -M turbo -p "Ilustrace horské chaty." -n ./dest/chata_turbo
```

Přepínač `-M turbo` nahradí cestu z `model` sousedním adresářem `Qwen-Image-2.1-Turbo`. Například z `/models/Qwen-Image-2.1` odvodí `/models/Qwen-Image-2.1-Turbo`. Model musí existovat lokálně. Počet kroků se načte z `generation.num_inference_steps_turbo`, při vynechání je 8. Argument `-t` má přednost. Bez `-M turbo` platí `generation.num_inference_steps`, výchozí 30.

Pro hromadnou editaci lze změnit příponu názvu:

```sh
python cli_image.py -a --src ./src --dest ./dest -x j -s 42 -p "Jemné večerní světlo."
```

Z `foto.jpg` vznikne `foto_j.jpg`. Úvodní podtržítka v hodnotě `-x` se odstraní a skript vloží jedno vlastní. Pozor: výběr vstupů i při vlastním `-x` stále přeskakuje názvy končící `_e`; názvy `_j` se automaticky nepřeskakují.

## 14. Runner: automatizace pomocí flow souborů

Runner vykonává příkazy z textového souboru postupně. Umí proměnné, cykly, skládání promptů a seznamy referencí. Flow není Python ani shellový skript. Každý příkaz musí být na jednom řádku; nepoužívejte shellové roury, přesměrování ani `&&`. Prázdné řádky a řádky začínající `#` se ignorují. Komentáře pište na samostatné řádky. Soubory ukládejte v UTF-8.

### 14.1 Spuštění a kontrola bez výpočtu

Uložte flow například do `flow/porovnani.txt`:

```sh
python runner_image.py porovnani --dry-run
python runner_image.py porovnani
python runner_image.py ./flow/porovnani.txt
python runner_image.py --version
```

Příponu `.txt` lze vynechat. Runner nejprve hledá zadanou cestu vůči svému adresáři, potom stejné jméno ve `flow/`. Bez argumentu vybere první `flow/*.txt` podle abecedního pořadí; nezobrazuje výběrové menu.

`--dry-run` vypíše rozvinuté příkazy a všechny iterace, ale nespustí je ani nenačte model. Přesto vyhodnocuje proměnné, čte soubory pro `@join` a prochází adresáře pro `@prefix`. Neověřuje existenci obrázků předaných samotnému CLI.

Příkazy se spouštějí z adresáře runneru, i když flow leží v podadresáři. Příkazy začínající `python`, `python3` nebo `py` používají stejný interpret a prostředí jako runner.

### 14.2 Proměnné a názvy výstupů

```text
$input = "./src/foto.jpg"
$prompt = "Změň pozadí na horské jezero."
$seed = 42
$steps = 30

python cli_image.py -e "$input" -p "$prompt" -s $seed -t $steps -n ./dest/pokus_${seed}
```

Výsledkem při PNG a jednom výstupu je `dest/pokus_42.png`. Proměnné zapisujte jako `$seed` nebo `${seed}`. Složené závorky oddělí jméno od dalšího textu, například `${seed}_detail`. Jména rozlišují velikost písmen; proměnná musí být definovaná před použitím. Texty a cesty s mezerami v příkazech uzavírejte do uvozovek.

### 14.3 Cyklus @for: seznam a rozsah

```text
$input = "./src/foto.jpg"
$prompt = "Změň fotografii na akvarel."

@for T in 10,15,20,25,30
    python cli_image.py -e "$input" -p "$prompt" -s 42 -t $T -n ./dest/kroky_${T}
@endfor
```

Stejný seznam kroků lze napsat jako `@for T in 10..30 step 5`. Rozsahy jsou celočíselné a zahrnují koncovou hodnotu, pokud na ni krok vyjde. `1..3` znamená 1, 2, 3; `3..1` automaticky klesá. Explicitní sestupný rozsah je například `30..10 step -5`. Krok nesmí být nula a musí odpovídat směru rozsahu. Okolní závorky jsou volitelné: `@for S in (1..3)`.

Desetinné hodnoty uvádějte seznamem, například `@for R in 0.6,0.8,1.0`; desetinné rozsahy se nepodporují. Seznam se dělí podle čárek, bez zvláštního zpracování uvozovek. Delší texty s čárkami proto nejprve uložte do proměnných.

Každý `@for` musí mít vlastní `@endfor`. Odsazení je pro čitelnost; bloky vymezují tyto značky.

### 14.4 Vnořené cykly

```text
$input = "./src/foto.jpg"
$prompt = "Jemný akvarel, zachovej kompozici."

@for S in 41..43
    @for R in 0.6,0.8,1.0
        python cli_image.py -e "$input" -p "$prompt" -s $S -r $R -n ./dest/akvarel_s${S}_r${R}
    @endfor
@endfor
```

Vznikne devět výstupů. Název obsahuje obě měněné hodnoty, takže se jednotlivé kombinace nekříží. Každá iterace dostane kopii proměnných z vnějšího bloku. Přiřazení uvnitř iterace je dostupné jejím vnořeným blokům, ale nemění proměnné mimo iteraci ani další iteraci.

Hodnoty seznamu se dosazují při běhu. Lze tedy procházet celé připravené prompty:

```text
$base1 = "Akvarel, jemné barvy."
$base2 = "Olejomalba, výrazné tahy."

@for B in $base1, $base2
    python cli_image.py -b "$B" -p "Horská krajina." -n ./dest/krajina
@endfor
```

Obsah každé proměnné zůstává jednou hodnotou i při mezerách a čárkách. V tomto příkladu nastavte `output.overwrite` na `false`, aby se oba výsledky zachovaly. Proměnná v seznamu se nerozvine na číselný rozsah: zápis `$rozsah = "1..3"` a `@for S in $rozsah` vytvoří jedinou hodnotu `1..3`.

### 14.5 @prefix: všechny prompty s daným začátkem názvu

Příklad konfigurace:

```json
"prompt_file": ["./prom", "./prom_test"]
```

V těchto adresářích připravte například `d_saty.txt`, `d_bunda.txt` a `d_kabat.txt`:

```text
$input = "./src/osoba.jpg"

@for D in @prefix("d_")
    $dress = @join("/${D}")
    python cli_image.py -e "$input" -b "$dress" -p "Zachovej osobu, pózu a pozadí." -s 42 -n ./dest/${D}
@endfor
```

`D` obsahuje jméno bez `.txt`, například `d_bunda`, nikoli cestu ani obsah souboru. `@join("/${D}")` načte text odpovídajícího promptu. Pokud není třeba text skládat, lze předat zkratku přímo: `-b "/${D}"`.

Pravidla výběru:

- Prochází se přímo adresáře z `prompt_file`, bez podadresářů. Řetězcová konfigurace vybírá adresář vedle daného souboru. Bez konfigurace runner použije `./prom`.
- Vybírají se pouze soubory s přesnou příponou `.txt` a jménem začínajícím zadaným prefixem; velikost písmen se rozlišuje.
- Prefix i celé jméno bez přípony smějí obsahovat jen `A–Z`, `a–z`, číslice, `_` a `-`. Diakritika a mezery nejsou podporovány.
- Názvy se seřadí a odstraní se duplicity. Při stejném názvu ve více adresářích se obsah načítá z prvního nalezeného podle pořadí konfigurace.
- Pokud nic neodpovídá, runner skončí chybou. Prefix je v hlavičce pevný text; proměnné v `@prefix` se nedosazují.

Výběr `@prefix` probíhá při načítání celého flow, tedy i u bloků za `@exit`.

Při načítání runner vypíše například `@prefix("d_"): Loaded 3 matching prompt files.` Počet odpovídá unikátním vybraným názvům po odstranění duplicit. Před každou iterací vypíše záhlaví s aktuálním názvem a pořadím, například `[for D=d_bunda 1/3]`. Report i pořadí se zobrazují při běžném běhu i s `--dry-run`; u vnořených cyklů se pořadí vztahuje ke konkrétnímu cyklu `@prefix`.

### 14.6 @join: skládání promptů

```text
$intro = "Realistická fotografie."
$base = @join($intro, /d_saty, ./prom/detail.txt, "Měkké večerní světlo.")
python cli_image.py -b "$base" -p "Celá postava v zahradě." -n ./dest/zahrada
```

Jednotlivé části se oříznou na okrajích a spojí jedním odřádkováním (`\n`). Naproti tomu CLI odděluje základ `-b` od hlavního promptu `-p` prázdným řádkem (`\n\n`).

| Argument @join | Co vloží |
| --- | --- |
| `$intro` | Obsah proměnné, bez dalšího výkladu jako cesty. |
| `"Text s čárkou, zde."` | Doslovný text s dosazením proměnných. |
| `./prom/detail.txt` | Obsah UTF-8 souboru; relativně k runneru. |
| `/d_saty` nebo `"/${D}"` | Obsah promptu podle `prompt_file`. |

Uvozovky obvykle znamenají text: `"./prom/detail.txt"` vloží samotnou cestu. Výjimkou je přesná zkratka `/název`, která se načte i v uvozovkách. Prázdný text, chybějící soubor nebo prázdný soubor způsobí chybu.

### 14.7 @files: reference pro merge a návazné kroky

```text
$T = 30
@for S in 7..8
    python cli_image.py -p "Prázdná zahrada, realistická fotografie." -s $S -n ./dest/bg_${S}
    python cli_image.py -p "Dřevěná zahradní lavička." -s $S -n ./dest/lavicka_${S}
    $refs = @files("./dest/bg_${S}", "./dest/lavicka_${S}")
    python cli_image.py -m --files $refs -p "Umísti lavičku do zahrady z první reference." -s $S -t $T -n ./dest/celek_${S}
@endfor
```

Při PNG vzniknou například `bg_7.png`, `lavicka_7.png` a `celek_7.png`. `@files` sestaví seznam cest, nečte obsah obrázků. CLI doplní cestám bez přípony formát z `output.format`. Každá cesta se předá jako samostatný argument a zachová se pořadí i mezery v názvech. Seznam používejte jako samostatný argument `$refs`; nelze jej vložit do dalšího textu, například `prefix_${refs}`. `--files` vyžaduje režim `-m`, nejvýše deset existujících referencí PNG/JPG/JPEG.

Při `output.overwrite: false` může kolize změnit skutečně uložený název na `-d`. Runner tuto změnu automaticky nepřenese do dalších příkazů. Pro návazné kroky používejte nové názvy nebo čistý cílový adresář a kontrolujte výpis `Saved:`.

### 14.8 Ukončení, chyby a paměť

`@exit` na samostatném řádku zastaví celé flow, včetně vnořených cyklů. Není to přeskočení jedné iterace ani ukončení pouze nejbližšího cyklu. `--dry-run` tuto značku také respektuje. Runner nepodporuje `@break`, `@continue` ani podmínky.

Při nenulovém návratovém kódu příkazu runner skončí chybou a další příkazy nespustí. Chyby syntaxe, proměnných a souborů uvádějí související flow a řádek, pokud je tato informace dostupná.

Každý příkaz `python cli_image.py ...` spustí samostatný proces a znovu načte model. Runner mezi příkazy model nesdílí; cykly jsou sekvenční. Pro více variant se stejnými parametry je proto vhodné `-N`, které model načte jednou. Po běžném ukončení procesu jeho paměť uvolní operační systém. Při násilném ukončení pouze runneru může zůstat běžet potomek `cli_image.py`; runner nyní nemá vlastní obsluhu úklidu potomků.

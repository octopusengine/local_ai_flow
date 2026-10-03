# cli_image.py — český návod

`cli_image.py` je konzolový nástroj pro práci s obrázky pomocí `QwenImage21Pipeline` z knihovny Diffusers. Umí vytvořit obrázek z textového zadání, upravit jeden existující obrázek, stejným zadáním upravit více souborů nebo vytvořit společný výsledek z několika referencí. Tento návod popisuje implementaci skriptu ve verzi `v0.7`.

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

Příkazy v návodu spouštějte z kořenového adresáře projektu. Konfigurace se vždy hledá pod názvem `cli_image.json` v **aktuálním pracovním adresáři**, nikoli automaticky vedle skriptu. Stejně se vyhodnocují relativní cesty k modelu, zadání, vstupům a výstupům. Skript nemá přepínač pro jiný konfigurační soubor.

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
| `prompt_file` | Povinná | Cesta k textovému zadání v UTF-8; obsah se použije, pokud není zadáno `-p`. |
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

## 4. Přehled argumentů

| Argument | Význam |
| --- | --- |
| `-h`, `--help` | Zobrazí nápovědu. |
| `--version` | Zobrazí verzi skriptu. |
| `-N POČET` | Počet výstupů, minimálně 1; výchozí je 1. Má význam pro generování, editaci jednoho obrázku a merge. |
| `-p`, `--prompt TEXT_NEBO_SOUBOR` | Přímé zadání nebo cesta k textovému souboru. |
| `-f`, `--file ZÁKLAD` | Základ názvu výsledných souborů. |
| `--name ZÁKLAD` | Přepíše základ názvu; má přednost i před `-f`. |
| `-s`, `--seed ČÍSLO` | Přepíše seed z JSONu. |
| `-t`, `--steps POČET` | Přepíše počet kroků, minimálně 1. |
| `-r`, `--strength HODNOTA` | Síla v rozsahu 0 až 1 pro editaci a merge. |
| `-W`, `--width PIXELY` | Šířka pro generování a merge, minimálně 1. |
| `-H`, `--height PIXELY` | Výška pro generování a merge, minimálně 1. |
| `-e`, `--edit OBRÁZEK` | Editace konkrétního vstupního obrázku. Cesta je povinná. |
| `-a`, `--all` | Hromadná editace obrázků z `./src` do `./dest`. |
| `-m`, `--merge` | Vytvoření výsledku ze všech vhodných referencí v `./src`. |

Velikost písmen je důležitá: počet výstupů je `-N`, šířka `-W` a výška `-H`. `-h` zobrazí nápovědu.

Argumenty obvykle přepisují JSON. Výjimkou je validace: šířka, výška, kroky a `strength` v JSONu se kontrolují **před** aplikací přepínačů. Chybnou hodnotu v JSONu tedy nelze obejít platným argumentem. Také `output.format` a neprázdný název výstupu se kontrolují v hromadném režimu, i když se pro jeho výsledné názvy nepoužívají.

## 5. Režim generování z textu

Generování je výchozí režim, pokud nepoužijete `-e`, `-a` ani `-m`. Přítomnost `input.edit_file` v JSONu editaci nezapíná.

```sh
python cli_image.py -p "Ilustrace starého majáku u moře." -f majak_
```

Při formátu `png` vznikne `majak_1.png`.

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

Při `output.format: "png"` se výsledek uloží jako `uprava_1.png`. Vstup může být PNG, JPG nebo JPEG; výstupní formát se řídí JSONem a nemusí odpovídat vstupu.

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

Skript prochází přímo adresář `./src`, vybere PNG/JPG/JPEG a zpracuje každý soubor jednou. Podadresáře neprochází. Použije stejné zadání a nastavení pro všechny vstupy.

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
- Vstupy jsou seřazené podle cest. Pevný seed se zvyšuje o index souboru, počínaje nulou.

Pokud jedna úprava selže, skript pokračuje dalšími soubory. Na konci vypíše počty úspěchů a chyb; při alespoň jedné chybě vrátí návratový kód 1.

## 8. Spojení více referencí — merge

Režim `-m` předá pipeline seznam obrázků z `./src` a společné textové zadání. Jde o tvorbu výsledku s více referencemi; způsob propojení určujete promptem.

Například připravte tyto vstupy:

```text
src/
├── 01_osoba.png
└── 02_zahrada.jpg
```

```sh
python cli_image.py -m -p "Umísti osobu z prvního obrázku do zahrady z druhého obrázku. Sjednoť osvětlení." -W 1536 -H 1024 -f spojeni_
```

Při formátu PNG vznikne `spojeni_1.png`. Pořadí referencí odpovídá seřazenému seznamu cest; skript vypisuje přiřazení `<image1>`, `<image2>` atd. Číselné prefixy souborů usnadňují kontrolu pořadí.

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

Pro více výstupů se používá `seed + index`: při `-N 3 -s 42` tedy 42, 43 a 44. Totéž platí pro pořadí vstupních souborů v hromadné editaci. Změna seznamu souborů může změnit seed přiřazený konkrétnímu obrázku.

Stejný seed pomáhá porovnávat nastavení, ale shodný výsledek napříč různými zařízeními, verzemi knihoven a datovými typy není zaručen. Skript seed neukládá do samostatného souboru s metadaty. CLI také nemá přepínač, který by pevný seed z JSONu přepsal na `null`; pro návrat k náhodným seedům změňte JSON.

## 11. Názvy, cesty a formáty výstupů

V režimech generování, editace jednoho obrázku a merge se cesta sestavuje jako:

```text
základ_názvu + pořadové_číslo_od_1 + tečka + formát
```

| Základ názvu | Formát | První výstup |
| --- | --- | --- |
| `out_` | `png` | `out_1.png` |
| `obrazek` | `jpg` | `obrazek1.jpg` |
| `./dest/test_` | `jpeg` | `dest/test_1.jpeg` |

Argument `-f` tedy není kompletní cílový název souboru. Například `-f obrazek.png` vytvoří při formátu PNG název `obrazek.png1.png`. Zadávejte základ bez přípony.

Pokud uvedete `-f` i `--name`, vyhraje `--name`:

```sh
python cli_image.py -p "Zátiší s ovocem." -f prvni_ --name ./dest/ovoce_
```

Výstup bude `dest/ovoce_1.png`, je-li formát PNG. Chybějící rodičovské adresáře výstupu se vytvářejí automaticky.

**Existující cílové soubory se přepisují bez potvrzení.** Číslování při každém spuštění začíná znovu od 1. Pro jednotlivé experimenty proto použijte odlišný základ názvu nebo adresář.

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

Skript nemá argumenty pro masku, negativní prompt, guidance scale, vlastní cestu k `src`/`dest` ani výstupní formát. Nepodporované argumenty odmítne parser. Neznámé položky v JSONu, například `sigma_start`, se mohou jednoduše ignorovat.

Před výpočtem se vypisuje režim, model, zařízení, datový typ, parametry a prompt. Model se načítá jednou za spuštění a opakovaně používá pro jeho výstupy. Chyby jednotlivých výpočtů se vypisují jako `ERROR`; zpracování dalších položek pokračuje a při neúspěšném výsledku skript končí kódem 1. Běh lze přerušit pomocí `Ctrl+C`.

# cli_laya (verze 0.1.1)

Malý příkazový nástroj, který načte markdown soubor (např. support ticket) a položí nad ním typované otázky modelu **laya** (open-source model trénovaný metodou RLCD, Apache 2.0). Odpovědi vypíše a v dávkovém režimu uloží vedle zdrojových souborů jako JSON.

Model **negeneruje text**: na každou otázku vrátí volbu, číslo na škále nebo pravděpodobnost ano/ne, vše v jednom průchodu.

## Obsah složky

| soubor | k čemu slouží |
|---|---|
| `cli_laya.py` | vlastní program |
| `cli_laya.json` | nastavení (cesta k modelu, výchozí soubory, parametry laya) |
| `question.json` | otázky, které se modelu kladou |
| `ticket.md` | ukázkový vstup |
| `hello_laya.py` | nejjednodušší „hello world“ (jen ukázka, k běhu `cli_laya.py` není potřeba) |
| `data/` | složka pro dávkové zpracování (vytvoříte sami) |

## Instalace

Potřebujete Python (laya deklaruje 3.8+, ověřeno na 3.10 pod Windows) a asi 1 GB místa na disku pro model.

```powershell
python -m venv venv
venv\Scripts\activate
pip install laya
```

`pip install laya` přinese i závislosti (torch, transformers, huggingface_hub). Nic dalšího se neinstaluje.

### První spuštění

```powershell
python cli_laya.py
```

Pokud model ve složce z `model_dir` chybí, stáhne se automaticky z Hugging Face (multilingual checkpoint, zhruba 680 MB). Příště se už nic nestahuje a program funguje i offline.

### Poznámka k Windows a symlinkům

Standardní cache `huggingface_hub` používá symbolické odkazy, které některé disky (např. exFAT/FAT32) nepodporují, a stahování skončí chybou `WinError 1`. Program proto model stahuje přímo do `model_dir` pomocí `local_dir`, který symlinky nepoužívá. Model tak může ležet na libovolném disku.

## Použití

```
python cli_laya.py [vstup.md] [-b [DIR]] [-c CONFIG.json] [-q OTAZKY.json] [-u] [--model-dir DIR] [-V] [-v]
```

| přepínač | význam |
|---|---|
| `vstup.md` | vstupní soubor (výchozí `input` z konfigurace) |
| `-b`, `--batch [DIR]` | dávka: zpracuje všechna `*.md` ze složky (bez `DIR` se bere `batch_dir`, tj. `./data`) |
| `-c`, `--config FILE.json` | jiný konfigurační soubor |
| `-q`, `--question FILE.json` | jiný soubor s otázkami |
| `-u`, `--update` | zkontroluje na Hugging Face, zda není novější verze modelu |
| `--model-dir DIR` | jiná složka s modelem |
| `--model NAME` | checkpoint `multilingual`, `english` nebo `typed-decisions` pro toto spuštění; výchozí nastavení nemění |
| `--download-only` | připraví zvolený model a skončí bez inference; s `-u` zkontroluje/stáhne nejnovější revizi |
| `-d`, `--download MODEL` | stáhne/aktualizuje `english`, `multilingual` nebo `typed-decisions` a skončí; nepotřebuje vstup ani otázky a nemění výchozí checkpoint |
| `-v`, `--verbose` | ukecaný režim: ladicí zprávy o tom, co se právě děje (viz níže) |
| `-V`, `--version` | vypíše verzi programu a info o modelech (viz níže); s `-u` se dotáže i Hugging Face |

Přepínače z příkazové řádky mají přednost před konfigurací. Vstupní soubor a `--batch` nejdou kombinovat.

### Ukázky

Jeden soubor, vše podle konfigurace:

```powershell
python cli_laya.py
```

```
Soubor : ticket.md
Otázky : D:\data_codex\laya\question.json
Model  : multilingual (cpu)
department : billing (jistota 1.00)
urgency    : 1.80
churn_risk : 0.028
Čas celkem: 8.42 s (příprava a načtení modelu 7.90 s, odpověď 0.52 s)
```

(Čas v ukázce je ilustrativní. Odpovědi jsou z reálného běhu na ukázkovém ticketu.)

Jiný vstup a jiné otázky:

```powershell
python cli_laya.py dopis.md -q jine_otazky.json
```

Dávka ze složky `./data`:

```powershell
python cli_laya.py --batch
```

```
Dávka  : 3 souborů z D:\data_codex\laya\data
Otázky : D:\data_codex\laya\question.json
Model  : multilingual (cpu), načten za 7.9 s
[1/3] a.md
  department : billing (jistota 0.90)
  urgency    : 1.50
  churn_risk : 0.250
  čas: 0.52 s -> a.json
[2/3] b.md
...
Hotovo: 3 z 3 souborů. Odpovědi celkem 1.6 s, průměr 0.53 s/soubor; celý běh 9.5 s (příprava a načtení modelu 7.9 s)
```

Dávka z jiné složky:

```powershell
python cli_laya.py -b D:\tickety\2026-09
```

Zkontrolovat novou verzi modelu:

```powershell
python cli_laya.py --update
```

Stažení anglického modelu bez inference:

```powershell
python cli_laya.py --model english -u --download-only
python cli_laya.py -d english
python cli_laya.py project_laya/test3/evaluation.md -q project_laya/test3/question3.json --model english
```

`-u` aktualizuje pouze zvolený checkpoint. Bez `--model` platí checkpoint z konfigurace,
standardně `multilingual`. `-V -u` nadále pouze vypisuje informace, nestahuje model.
Anglické váhy jsou v kořeni `model_dir`, vícejazyčné v podsložce `multilingual`.

`-d english` je zkrácený příkaz pro stažení/aktualizaci anglického modelu bez inference.
Zkontroluje Hugging Face i při existujícím modelu; nezměněné soubory znovu nestahuje.
Podporuje `-c` a `--model-dir`. Nelze ho kombinovat se vstupem, `--batch`, `--out`,
`-V` ani s odlišným checkpointem v `--model`.

## Ukecaný režim (`-v`)

Načtení modelu trvá desítky sekund a bez výpisu to vypadá, jako by program stál. S `-v` se průběžně vypisuje, co se děje. Ladicí zprávy jdou na **stderr**, takže výsledky na stdout zůstávají čisté a jdou přesměrovat (`python cli_laya.py -b > vysledky.txt`) bez ladicího šumu. Každá zpráva má na začátku čas od spuštění.

```powershell
python cli_laya.py -v
```

```
[   0.00 s] cli_laya 0.1.1, Python 3.10.x, Windows-10-...
[   0.00 s] konfigurační soubor: D:\data_codex\laya\cli_laya.json
[   0.00 s]   model_dir = 'D:\\data_codex\\laya_models'
[   0.00 s]   checkpoint = 'multilingual'
...
[   0.01 s] otázky: question.json (počet 3: department:choice, urgency:score, churn_risk:noul)
[   0.01 s] vstup: ticket.md, slov 35, znaků 190, klíče ['from', 'subject', 'body']
[   0.01 s] model: hledám D:\data_codex\laya_models\multilingual\model.safetensors -> nalezen
[   0.01 s] model je uložen lokálně, síť se nekontroluje (bez --update)
[   0.01 s] načítám knihovny (torch, transformers, laya) ...
[   9.80 s] knihovny načteny za 9.79 s (torch 2.x, transformers 4.x, laya 0.3.4)
[   9.80 s] načítám model multilingual z D:\data_codex\laya_models\multilingual (zařízení cpu) ...
[  31.10 s] model načten za 21.30 s
[  31.10 s] parametry modelu: max_len=1024, head_max_len=256
[  31.11 s] posílám dotaz nad ticket.md (počet otázek: 3)
[  31.55 s] routing: {'model': 'multilingual', ...}
[  31.55 s] odpověď za 0.44 s
```

(Časy a verze v ukázce jsou ilustrativní.) Vypisuje se:

- prostředí (verze programu, Pythonu, systém, pracovní složka),
- efektivní konfigurace po sloučení souboru a přepínačů,
- načtené otázky a vstupní soubor (počet slov, znaků, klíče front matteru),
- kontrola modelu (nalezen / stahuje se, u `--update` i průběh `snapshot_download`),
- načtení knihoven a modelu zvlášť s časy, verze torch/transformers/laya, počet vláken torch a dostupnost CUDA,
- přepsané parametry (`max_len`, `head_max_len`) a hodnoty, se kterými model skutečně běží,
- routing z odpovědi laya,
- v dávce navíc u každého souboru vstup, routing a zapsaný JSON; při chybě celý traceback.

Rozdíl proti `-V`: velké `-V` vypíše verzi a informace o modelech a skončí, malé `-v` zpřesní výpisy běžného zpracování.

## Verze a informace o modelech

```powershell
python cli_laya.py -V          # jen lokální informace, funguje offline
python cli_laya.py -V -u       # navíc dotaz na Hugging Face (vyžaduje internet)
```

Výpis obsahuje verzi programu (`__version__` v `cli_laya.py`), verzi nainstalovaného balíčku `laya`, složku s modely a pro každý ze tří checkpointů:

- popis (encoder, počet parametrů, kontext, jazyky; podle dokumentace laya),
- zda je stažen, jeho velikost a datum stažení,
- zkrácenou revizi (commit) repa, ze které byl stažen (zapisuje ji `huggingface_hub` při stahování do `local_dir`),
- hodnoty `encoder`, `max_len` a `head_max_len` přímo z konfigurace staženého modelu.

S přepínačem `-u` program zjistí na Hugging Face poslední revizi repa a datum její změny a porovná ji s revizí lokální kopie. Revize se týká celého repa (všech tří checkpointů najednou), takže „repo má novější revizi" ještě neznamená, že se změnil právě váš checkpoint. Bez internetu program jen oznámí, že Hugging Face není dostupný.

Informace, které nejsou k dispozici (například revize u modelu stáhnutého jiným způsobem), se uvádějí jako „neznámá". Číslo verze samotného modelu laya neuvádí, proto se model identifikuje datem stažení a revizí.

## Formát vstupního markdownu

Volitelný front matter (řádky `klíč: hodnota` mezi `---`) a tělo. Vše se předá modelu jako slovník, tělo pod klíčem `body`.

```markdown
---
from: jan.novak@example.cz
subject: Dvojitá platba za fakturu č. 4411
---

Dobrý den,

za březen nám byla stržena platba dvakrát. Prosíme o vrácení
duplicitní částky ještě dnes, jinak budeme nuceni tarif zrušit.
```

Front matter je jednoduchý: každý řádek je `klíč: hodnota`, vnořené struktury a seznamy se nepodporují. Soubor bez front matteru je v pořádku, celý se použije jako tělo.

## Otázky (`question.json`)

JSON objekt, kde klíč je id otázky a hodnota její popis. Otázky můžete libovolně přidávat, ubírat a přejmenovávat, program se přizpůsobí.

```json
{
  "department": {
    "type": "choice",
    "instructions": "Which department should handle this request?",
    "criteria": {
      "billing": "invoices, payments, refunds",
      "technical": "bugs, outages, system errors",
      "sales": "pricing, new contracts",
      "other": "everything else"
    }
  },
  "urgency": {
    "type": "score",
    "instructions": "How urgent is this request?",
    "criteria": ["not urgent", "soon", "critical deadline or blocking issue"]
  },
  "churn_risk": {
    "type": "noul",
    "instructions": "Does the user threaten to cancel or leave?"
  }
}
```

| `type` | `criteria` | výstup |
|---|---|---|
| `choice` | objekt `{volba: popis}` | vybraná volba a jistota (0–1) |
| `score` | seznam úrovní od nejnižší po nejvyšší | číslo od 0 do (počet úrovní − 1), tedy u tří úrovní 0–2 |
| `noul` | není potřeba | pravděpodobnost „ano“ (0–1) |

`instructions` je povinné u všech typů. Program při chybě v souboru vypíše srozumitelnou hlášku (neplatný JSON, neznámý `type`, špatný tvar `criteria`).

Texty otázek a voleb jsou v angličtině, ve které je model trénovaný. Model umí i jiné jazyky vstupu, ale u čtení otázek anglická formulace vychází spolehlivěji.

## Nastavení (`cli_laya.json`)

```json
{
  "model_dir": "D:\\data_codex\\laya_models",
  "questions": "question.json",
  "input": "ticket.md",
  "batch_dir": "data",

  "checkpoint": "multilingual",
  "device": "cpu",
  "cpu_threads": null,

  "max_len": null,
  "head_max_len": null,

  "update": false
}
```

| klíč | význam |
|---|---|
| `model_dir` | složka s modelem |
| `questions` | soubor s otázkami |
| `input` | výchozí vstupní markdown |
| `batch_dir` | výchozí složka pro dávku |
| `checkpoint` | `multilingual`, `english` nebo `typed-decisions` |
| `device` | `cpu` (případně `cuda`) |
| `cpu_threads` | počet vláken torch na CPU, `null` = výchozí |
| `max_len`, `head_max_len` | délka kontextu a rozpočet tokenů pro popisy voleb, `null` = hodnoty modelu; přidejte, pokud máte v jedné `choice` otázce hodně voleb |
| `update` | `true` = pokaždé kontrolovat novou verzi modelu |

Pravidla:

- Relativní cesty v JSONu se berou **od složky, kde leží konfigurace**, ne od aktuální složky. Program tak jde spouštět odkudkoli.
- Klíče začínající `_` (např. `_comment`) se ignorují. Neznámý klíč je chyba (chrání před překlepy).
- Konfigurace se hledá vedle `cli_laya.py`. Chybí-li, použijí se hodnoty zabudované ve skriptu. Jiný soubor zadáte přes `-c`; chybí-li soubor zadaný přes `-c`, je to chyba.
- Priorita: příkazová řádka → konfigurace → zabudované hodnoty.

## Dávkový režim

`--batch` vezme všechna `*.md` ze složky (bez podsložek, v abecedním pořadí) a model načte jen jednou. Vedle každého `FILE.md` uloží `FILE.json`, existující se přepíše.

Obsah `FILE.json`:

```json
{
  "file": "a.md",
  "questions": "question.json",
  "model": "multilingual",
  "seconds": 0.52,
  "answers": {
    "department": { "choice": "billing", "confidence": 0.9, "...": "..." },
    "urgency": { "score": 1.5, "...": "..." },
    "churn_risk": { "noul": 0.25, "...": "..." }
  },
  "routing": { "model": "multilingual", "...": "..." }
}
```

`answers` obsahuje kompletní odpověď z laya (včetně pravděpodobností jednotlivých voleb), proto jsou tečky v ukázce jen zkrácení. Přesná struktura závisí na verzi laya.

Vadný soubor (nečitelný, chyba modelu) vypíše chybu a dávka pokračuje dál. Jeho JSON se nevytvoří.

## Návratové kódy

| kód | význam |
|---|---|
| `0` | vše proběhlo |
| `1` | chyba (chybí soubor/složka, neplatná konfigurace nebo otázky, nesprávná kombinace přepínačů) nebo aspoň jeden soubor v dávce selhal |

## Jak to funguje uvnitř

1. Načte se konfigurace a otázky, zkontrolují se.
2. Model se najde v `model_dir`. Chybí-li (nebo je zadáno `--update`), stáhne se pomocí `snapshot_download(..., local_dir=...)`.
3. Checkpoint se načte přímo z lokální složky (`Agent`) a předá routeru (`Router.attach`), který díky tomu nestahuje nic dalšího.
4. `router.predict(..., model=checkpoint)` zodpoví všechny otázky jedním průchodem. Zvolený checkpoint se vynucuje, takže router nevybírá sám podle jazyka.

Čas se měří od začátku `main()` po vrácení odpovědi a rozděluje se na přípravu a načtení modelu a na samotnou odpověď. Start interpretu Pythonu se nepočítá.

## Omezení a poctivé upozornění

- **Přesnost.** Podle dokumentace laya jsou základní checkpointy bez dotrénování zero-shot slabé, na jejich benchmarku blízko náhodě. Multilingual navíc nemá nakalibrované pravděpodobnosti. Na ukázkovém ticketu vyšlo správně oddělení `billing` a naléhavost 1.80 z 2, ale riziko odchodu 0.028, přestože ticket výslovně hrozí zrušením tarifu, a jistota 1.00 je přehnaná. Berte výstupy jako ukázku, ne jako spolehlivé rozhodování. Pro reálné použití by bylo potřeba model dotrénovat na vlastních datech (laya k tomu dodává notebook pro fine-tuning).
- **Malé množství voleb.** Popisy voleb sdílejí omezený rozpočet tokenů. Při desítkách voleb v jedné `choice` otázce přesnost prudce klesá; zvyšte `head_max_len`/`max_len` nebo volby rozdělte do dvou kroků.
- **Neověřené části.** Prakticky jsem otestoval jen `multilingual` na CPU. Checkpointy `english` a `typed-decisions` a `device: "cuda"` jsou v programu podporované, ale nevyzkoušené.
- **Teploty kalibrace** (`temperature`) se v konfiguraci nenastavují.
- **Výkon.** Podle dokumentace trvá odpověď na CPU zhruba 200–450 ms, načtení modelu jednotky sekund. Skutečná čísla uvidíte ve výpisu.

## Užitečné odkazy

- PyPI: <https://pypi.org/project/laya/>
- Model: <https://huggingface.co/convaiinnovations/laya>
- Zdrojový kód: <https://github.com/NandhaKishorM/laya>

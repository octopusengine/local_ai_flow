# Návrh řízení AI workflow pomocí `flow.txt`

> Stav k 2026-09-05: původní návrh níže zůstává zachován. Skutečná
> implementace je `runner.py`: spouští řádky `python3 cli_*.py ...`,
> podporuje textové i JSON flows, `--dry-run`, proměnné, `@if`
> (`file_exists` / `file_not_empty`), `@for` a dávky z `batch_list.txt`.
> James je nabízí v menu Flow. Syntaxe `artifact = akce ...`, `cli_flow.py`,
> `--resume`, `--status` a `flow_state.json` jsou zde návrh, nikoli dnešní API.
> Ukázky aktuálního formátu jsou v `../flows/`; příkazy se spouštějí z kořene projektu.

## Účel

Projekt již obsahuje samostatná CLI pro nahrání, přepis, OCR, překlad a
syntézu řeči. Jsou užitečná i jednotlivě, ale pro opakované vícekrokové
zpracování je vhodné mít jeden reprodukovatelný popis workflow.

Cílem je zavést malý Python runner, například `cli_flow.py`, který načte
textový soubor `flow.txt`, ověří jej a vykoná jednotlivé kroky ve správném
pořadí.

```text
záznam / MP3 / obrázek
        │
        ▼
   přepis nebo OCR
        │
        ├──────────────► textový výstup
        │                      │
        ▼                      ▼
      překlad             syntéza řeči
        │                      │
        └──────────────► MP3 výstup
```

Runner nenahrazuje existující CLI. Poskytuje nad nimi opakovatelnou vrstvu
orchestrace. Jednotlivé nástroje proto zůstanou použitelné i pro ruční práci
nebo rychlý test.

## Proč `flow.txt`

### Výhody oproti ručnímu spouštění

- Přesně popisuje, jak vznikl konkrétní výstup.
- Umožní stejný proces opakovat nad jinými vstupními soubory.
- Zpřehlední návaznost souborů a jazykových směrů.
- Zjednoduší ladění: runner ví, který krok selhal.
- Později umožní `--dry-run`, `--resume` a přehled artifactů.

### Proč ne pouze shellový skript

PowerShell nebo `.bat` je vhodný pro jednorázové pomocné úkony, ale pro tento
projekt by přinášel méně přehledné validace, citlivější práci s cestami a
horší předávání stavu mezi kroky. Python runner navíc funguje stejně ve
Windows i případně v jiném prostředí.

### Proč ne obecný Python soubor workflow

Python workflow je velmi pružný, ale dovoluje příliš mnoho. Pro běžný tok
zvuk → text → překlad → řeč je výhodnější malý deklarativní formát:

- žádné `eval` ani spouštění libovolného kódu;
- striktně povolené akce a parametry;
- snadné čtení i pro uživatele, který nechce programovat;
- snadné vytvoření nápovědy a validátoru.

## Pracovní adresář a artifacty

Všechny pracovní vstupy a výstupy zůstávají v kořeni podadresáře určeného v
`project.json`.

```json
{
  "subdir": "project_01"
}
```

Pokud workflow uvádí `record.mp3`, znamená to:

```text
./project_01/record.mp3
```

Runner nesmí automaticky zapisovat do `src/`, `export/` ani mimo zvolený
projektový podadresář. Cesty se vždy normalizují a ověří před spuštěním kroku.

Artifact je pojmenovaný výstup kroku. Může být znovu použit dalším krokem
pomocí `${název_artifactu}`.

```text
record_audio = record output=record.mp3
text_cz = whisper input=${record_audio} output=text_cz.txt
```

Po prvním kroku je `${record_audio}` nahrazeno cestou `record.mp3`.

## Navržený formát `flow.txt`

Každý aktivní řádek má podobu:

```text
artifact = akce parametr=hodnota parametr=hodnota
```

Komentáře začínají `#`. Prázdné řádky se ignorují.

```text
# Název artifactu = typ kroku + parametry
text_en = translate input=text_cz.txt direction=c2e output=text_en.txt
```

### Pravidla syntaxe

1. Název artifactu je povinný, například `text_cz` nebo `speech_en`.
2. Akce je jedno z povolených slov: `record`, `whisper`, `ocr`, `translate`,
   `speech`.
3. Parametry mají tvar `klíč=hodnota`.
4. Hodnota bez mezer nemusí být uvozena.
5. Hodnota s mezerami se uzavře do dvojitých uvozovek.
6. Odkaz na výstup předchozího kroku používá `${artifact}`.
7. Každý artifact může být vytvořen právě jednou.
8. Odkazovaný artifact musí být vytvořen dříve v souboru.

Příklad hodnoty obsahující mezeru:

```text
note = translate input="vstupní text.txt" direction=c2e output="anglický text.txt"
```

Pro první verzi lze bezpečně omezit názvy souborů bez mezer. Podporu uvozovek
je vhodné doplnit pomocí standardního Python modulu `shlex`.

## Akce a jejich parametry

### `record`

Použije `cli_record_mp3.py`.

```text
record_audio = record output=record.mp3 gain_db=4
```

| Parametr | Povinný | Význam |
|---|---:|---|
| `output` | ano | Název výsledného MP3 v kořeni projektu. |
| `gain_db` | ne | Dočasné zesílení v dB; přepisuje `lib/record.json`. |

Výsledkem je MP3. Nahrávání vyžaduje interakci uživatele a končí klávesou.

### `whisper`

Použije `cli_whisper_mp3.py` nebo později přímo interní funkci Whisperu.

```text
text_cz = whisper input=${record_audio} output=text_cz.txt language=cs model=base
```

| Parametr | Povinný | Význam |
|---|---:|---|
| `input` | ano | MP3 soubor nebo odkaz na artifact typu MP3. |
| `output` | ano | Název textového přepisu. |
| `language` | ne | Jazyk, například `cs`, `en`, nebo `auto`. |
| `model` | ne | Whisper model; výchozí hodnota z `lib/whisper.json`. |

Současné CLI umí přepsat zvolený MP3 soubor. Pro flow je třeba zajistit, aby
byl výstup `output` přesně respektován; to je vhodné jako první rozšíření
interní API Whisperu.

### `ocr`

Současný ekvivalent: `cli_ollama.py --type task_ocr.json --in FILE --out FILE`.

```text
text_en = ocr input=comix1.jpg output=text_en.txt
```

| Parametr | Povinný | Význam |
|---|---:|---|
| `input` | ano | Obrázek `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp` nebo `.gif`. |
| `output` | ano | Název čistého OCR textu. |
| `model` | ne | Volitelný OCR model. |

Interně je žádoucí oddělit metadata OCR do `log.txt` a do výstupu ukládat
jen rozpoznaný text. Workflow runner pak nebude muset metadata odstraňovat.

### `translate`

Současný ekvivalent: `cli_ollama.py --type task_translate.json --direction c2a --in FILE --out FILE` (angličtina → čeština: `e2c`).

```text
text_en = translate input=${text_cz} direction=c2e output=text_en.txt
```

| Parametr | Povinný | Význam |
|---|---:|---|
| `input` | ano | Zdrojový `.txt` soubor nebo artifact. |
| `direction` | ano | `c2e` nebo `e2c`. |
| `output` | ano | Název souboru s čistým překladem. |
| `model` | ne | Volitelný model pro překlad. |
| `temperature` | ne | Volitelná teplota modelu. |

Současné `cli_ollama.py` už umožňuje určit výstup překladu přes `--out`;
`translate.txt` je výchozí název, nikoli povinný výstup. Níže navržené
`output` a `c2e` patří k původnímu formátu, dnešní CLI používá `--out` a `c2a`.

### `speech`

Použije `cli_speech.py` s parametrem `--mp3`.

```text
speech_en = speech input=${text_en} output=speech_en.mp3 voice=en sound=off mp3=on
```

| Parametr | Povinný | Význam |
|---|---:|---|
| `input` | ano | Textový `.txt` soubor nebo artifact. |
| `output` | ano | Výsledný MP3 soubor. |
| `voice` | ne | `cz` nebo `en`; výchozí `cz`. |
| `sound` | ne | `on` / `off`; ovlivní přehrání. |
| `mp3` | ano | Název výsledného MP3; předává se jako `--mp3 název.mp3`. |

Současná konfigurace `cli_speech.json` obsahuje výchozí `sound`.
Parametr výstupu flow určuje vytvoření MP3 pro konkrétní krok.

## Kompletní ukázky

### A. Česká nahrávka → anglický namluvený výstup

Soubor `flow_record_to_en.txt`:

```text
# Mikrofon -> český přepis -> anglický překlad -> anglické MP3

record_audio = record output=record.mp3 gain_db=4

text_cz = whisper input=${record_audio} output=text_cz.txt language=cs

text_en = translate input=${text_cz} direction=c2e output=text_en.txt

speech_en = speech input=${text_en} output=speech_en.mp3 voice=en sound=off mp3=on
```

Očekávané artifacty:

```text
record.mp3
text_cz.txt
text_en.txt
speech_en.mp3
```

### B. Anglický obrázek → český hlasový výstup

Soubor `flow_image_to_cz.txt`:

```text
# OCR anglického obrázku -> český překlad -> české MP3

text_en = ocr input=comix1.jpg output=text_en.txt

text_cz = translate input=${text_en} direction=e2c output=text_cz.txt

speech_cz = speech input=${text_cz} output=speech_cz.mp3 voice=cz sound=on mp3=on
```

### C. Pouze přepis a překlad

```text
text_cz = whisper input=meeting.mp3 output=meeting_cs.txt language=cs

text_en = translate input=${text_cz} direction=c2e output=meeting_en.txt
```

### D. Překlad existujícího textu bez rozpoznávání

```text
text_en = translate input=test_cz.txt direction=c2e output=test_en.txt

speech_en = speech input=${text_en} output=test_en.mp3 voice=en sound=off mp3=on
```

## Doporučené rozhraní runneru

```powershell
# Kontrola syntaxe a návazností bez spuštění modelů
python .\cli_flow.py flow_record_to_en.txt --dry-run

# Provede celý tok
python .\cli_flow.py flow_record_to_en.txt

# Naváže od prvního chybějícího nebo neplatného artifactu
python .\cli_flow.py flow_record_to_en.txt --resume

# Ukáže detailní stav kroků a artifactů
python .\cli_flow.py flow_record_to_en.txt --status
```

### `--dry-run`

Vypíše například:

```text
[1] record -> record.mp3
[2] whisper record.mp3 -> text_cz.txt
[3] translate c2e text_cz.txt -> text_en.txt
[4] speech en text_en.txt -> speech_en.mp3
```

Nevytváří soubory, nevolá Ollamu, Whisper, Piper ani mikrofon.

### `--resume`

Runner určí, zda je artifact pro daný krok použitelný:

- soubor existuje;
- má očekávanou příponu;
- je přímo v kořeni projektového podadresáře;
- pro pokročilejší verzi také odpovídá konfiguraci a vstupům kroku.

První verze může bezpečně přeskočit existující soubor pouze po explicitní
volbě `--resume`. Bez ní se kroky provádějí znovu a výstupy se přepisují.

## Validace před spuštěním

Runner má před spuštěním celého toku ověřit:

1. Existenci a platnost `project.json`.
2. Platnost syntaxe všech řádků `flow.txt`.
3. Povolené názvy akcí a parametrů.
4. Duplicitní názvy artifactů.
5. Odkazy na dříve nevytvořené artifacty.
6. Povolené přípony vstupů a výstupů.
7. Cesty uvnitř kořene projektového podadresáře.
8. Dostupnost modelů, FFmpeg a případně běžící Ollamy před příslušným krokem.

Chyba by měla uvádět řádek, například:

```text
flow_record_to_en.txt:7: neznámý artifact ${text_de}
```

nebo:

```text
flow_record_to_en.txt:9: akce speech vyžaduje vstup .txt, nalezeno record.mp3
```

## Logování a stav workflow

Stávající CLI připojují výpis do `./project_01/log.txt`. Runner má používat
stejný formát a zapisovat začátek i výsledek každého kroku:

```text
2026-07-17 | 20:05 [ cli_flow.py]
Flow: flow_record_to_en.txt
Krok 2/4: whisper
Vstup: record.mp3
Výstup: text_cz.txt
---
```

Vedle textového logu je vhodné později vytvářet i strojově čitelný stav,
například `./project_01/flow_state.json`:

```json
{
  "flow": "flow_record_to_en.txt",
  "started_at": "2026-07-17T20:05:14",
  "steps": {
    "record_audio": {
      "action": "record",
      "status": "done",
      "output": "record.mp3"
    },
    "text_cz": {
      "action": "whisper",
      "status": "done",
      "output": "text_cz.txt"
    }
  }
}
```

`flow_state.json` nesmí obsahovat celé přepisy, OCR texty ani překlady;
obsahuje jen metadata, cesty, čas a stav.

## Fáze implementace

### Fáze 1 – runner přes stávající CLI

`cli_flow.py` spouští jednotlivé skripty pomocí `subprocess` a sleduje jejich
návratové kódy.

Výhody:

- nejmenší zásah do existujícího projektu;
- každé CLI si zachová vlastní `-help`, konfiguraci a logování;
- snadné ověření proti ručně spouštěným příkazům.

Nevýhoda: data se předávají přes soubory a ne jako Python objekty. To je ale
pro artifactový workflow záměr a výhoda z hlediska reprodukovatelnosti.

### Fáze 2 – stabilní interní API modulů

Z každého CLI se vytáhne funkce s jasnými vstupy a výstupy, například:

```python
run_record(output: Path, gain_db: float | None) -> Path
run_whisper(input_file: Path, output_file: Path, language: str | None) -> Path
run_ocr(input_file: Path, output_file: Path) -> Path
run_translate(input_file: Path, output_file: Path, direction: str) -> Path
run_speech(input_file: Path, output_file: Path, voice: str, sound: bool, mp3: bool) -> Path
```

CLI skripty budou tyto funkce dál používat; pouze převedou parametry z
příkazové řádky a konfigurace. Runner pak může volat funkce přímo.

### Fáze 3 – pokročilé řízení

- `--resume` podle state souboru a kontrolních součtů vstupů;
- volitelný paralelní běh nezávislých kroků;
- podmínky typu `when=exists(...)`;
- volitelné pojmenování běhu a samostatný adresář artifactů;
- vizualizace grafu workflow;
- export reportu o celém běhu.

Tyto možnosti nemají být součástí první verze. Nejprve má být syntaxe malá,
čitelná a spolehlivá.

## Doporučené další kroky

1. Schválit názvy akcí a syntax `artifact = action key=value`.
2. Rozšířit interní funkce o explicitní `input` a `output` cesty.
3. Zajistit čistý OCR text bez metadat v textovém artifactu.
4. Vytvořit `cli_flow.py` s parserem, `--dry-run` a validací.
5. Přidat ukázkové flow soubory do `./project_01/` nebo do samostatné složky
   `./flows/`.
6. Teprve poté přidat `--resume` a `flow_state.json`.

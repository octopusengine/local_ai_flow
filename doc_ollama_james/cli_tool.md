# cli_tool.py

Jednoduchý lokální Python nástroj použitelný jako krok v `runner.py` flow. Pracovní adresář si bere z `project.json` (`"subdir"`) stejně jako `cli_ollama.py`/`cli_db.py`. Vlastní chování ladí přes `cli_tool.json`.

## Konfigurace — `cli_tool.json`

```json
{
  "word": "agama",
  "output_filename": "tools_context.txt",
  "code_subdir": "sandbox",
  "code_report": "code_report.txt",
  "code_timeout": 30
}
```

| Klíč | Význam | Výchozí hodnota, pokud chybí |
|---|---|---|
| `word` | testovací slovo pro `--w` | — (bez klíče `--w` selže) |
| `output_filename` | název kontextového souboru v `SUBDIR` | `tools_context.txt` |
| `code_subdir` | podadresář v `SUBDIR` pro spouštěný kód | `sandbox` |
| `code_report` | název reportu z `--run-python` | `code_report.txt` |
| `code_timeout` | výchozí timeout skriptu (s) | `30` |
| `batch_in` | podadresář v `SUBDIR` se zdrojovými soubory | `src` |
| `batch_out` | podadresář v `SUBDIR` pro výsledky dávky | `dest` |

Chybějící nebo poškozený `cli_tool.json` nezastaví jednoduché akce (`--hw`, `--proj`, `--ping`...) — tiše se použijí výchozí hodnoty výše.

## Přehled parametrů

| Parametr | Co dělá |
|---|---|
| `-h`, `--help` | nápověda |
| `-V`, `--version` | verze nástroje |
| `--hw` | vypíše `hello world` |
| `--proj`, `--poject`, `--project` | vypíše aktuální projektový adresář (SUBDIR) |
| `--clr` | vyprázdní kontextový soubor |
| `--w` | vypíše testovací slovo z `cli_tool.json` |
| `--ping` | jeden ping na `8.8.8.8`, výsledek i do kontextu |
| `--url URL [--out FILE]` | stáhne URL; do kontextu jen 1000 znaků, `--out` uloží celou odpověď |
| `--text TEXT` | vypíše a zaloguje do kontextu jako `[tool_text]` |
| `--echo TEXT` | vypíše **jen** do terminálu, kontext se nemění |
| `--add NAME FILE` | obsah souboru zaloguje do kontextu jako `[NAME]` |
| `--date-time` | vypíše a zaloguje aktuální datum a čas |
| `--wc FILE` | spočítá řádky/slova/znaky souboru, zaloguje |
| `--show` | vypíše aktuální obsah kontextového souboru |
| `--size` | vypíše počet znaků/řádků kontextového souboru |
| `--trim N` | ořízne kontextový soubor na posledních N znaků |
| `--env VAR` | vypíše proměnnou prostředí, zaloguje |
| `--copy F` / `--copy F1 F2` | zkopíruje kontextový soubor (nebo F1) do F/F2 |
| `--run-python FILE [--timeout N]` | spustí FILE ze sandboxu, zapíše report + OK marker |
| `--code-extract FILE` | očistí `.py`/`.bat`/`.sh`/`.html` od markdown obalu |
| `--text-extract F1 F2` | očistí HTML/Markdown na čistý text, uloží jako F2 |
| `--batch` | vypíše soubory z `batch_in`, zapíše `batch_list.txt` pro `@for VAR in $batch_list` |
| `--batch-img` | zapíše jen obrázky `.png`, `.jpg`, `.jpeg` |
| `--batch-txt` | zapíše jen textové a zdrojové soubory |

Všechny akce jsou vzájemně se vylučující (jedna za spuštění) — konzistentní s `cli_ollama.py`/`cli_db.py`.

Příkazy spouštějte z kořene projektu. V James lze nástroj volat i přes
Chat → `/tool --PARAM`, například `/tool --date-time`.

## Detailní popis a ukázky

### Základní
```bash
python cli_tool.py --hw
# hello world

python cli_tool.py --proj
# C:\...\project_example
```

### Práce s kontextovým souborem (`tools_context.txt`)
```bash
python cli_tool.py --clr
python cli_tool.py --text "Pokusím se stáhnout kurz BTC"
# vypíše i zaloguje: [tool_text] Pokusím se stáhnout kurz BTC

python cli_tool.py --echo "--- sekce ---"
# jen do terminálu, do kontextu nic

python cli_tool.py --add "poznámky k tasku" notes.txt
# [poznámky k tasku] <obsah notes.txt>

python cli_tool.py --show      # vypíše celý aktuální kontext
python cli_tool.py --size      # chars=1234 lines=42
python cli_tool.py --trim 2000 # ořízne na posledních 2000 znaků
```

### Diagnostika / prostředí
```bash
python cli_tool.py --ping
# [ping] rtt min/avg/max/mdev = 12.3/12.3/12.3/0.0 ms

python cli_tool.py --wc data.txt
# [wc: data.txt] lines=42 words=310 chars=2048

python cli_tool.py --env PROJECT_NAME
# [env: PROJECT_NAME] hodnota
```

### Web
```bash
python cli_tool.py --url "https://api.coinpaprika.com/v1/tickers/btc-bitcoin"
# do kontextu jen prvních 1000 znaků: [url_response] ...

python cli_tool.py --url "https://agamapoint.cz/bitcoin" --out page.html
# uloží CELOU odpověď do SUBDIR/page.html (beze zkrácení)
```

HTTP(S) stahování používá `lib/wrapp_web.py`, timeout 10 s a limit
2 000 000 bajtů. `--out` ukládá celou přijatou odpověď pouze v tomto limitu.

### Kopírování a snapshoty
```bash
python cli_tool.py --copy backup_2026_08_22.txt
# zkopíruje aktuální tools_context.txt (nebo dle output_filename) do zadaného souboru

python cli_tool.py --copy generated.py sandbox/generated.py
# explicitní zdroj i cíl (typicky přesun do sandboxu)
```

### Spuštění a otestování AI vygenerovaného kódu
```bash
python cli_tool.py --run-python test.py
python cli_tool.py --run-python test.py --timeout 60
```
- Skript se hledá v `SUBDIR/<code_subdir>` (výchozí `sandbox`).
- stdout i stderr jdou do **jednoho** proudu (chronologicky, jako v terminálu).
- Report (`SUBDIR/<code_report>`) se při každém běhu **přepíše**.
- Timeout ukončí běh a report obsahuje, co skript stihl vypsat.
- **`code_ok.flag`** — čistě mechanický marker: vznikne jen když `return_code == 0` a skript neskončil timeoutem; jinak (i starý marker z dřívějška) se smaže. Určeno pro `@if file_exists("code_ok.flag")` v textovém flow.
- `cli_tool.py` samo vrací exit kód 0 i při neúspěchu testovaného skriptu — flow má pokračovat na krok, kde LLM report vyhodnotí, ne spadnout.

### Čištění AI výstupu
```bash
python cli_tool.py --code-extract generated.py
# odstraní markdown code-fence blok (tři zpětné apostrofy, volitelně s tagem jazyka)
# a okolní prózu, zůstane jen spustitelný kód
# beze změny, pokud žádný fenced blok nenajde


python cli_tool.py --text-extract page.html page.txt
# HTML tagy, script/style, komentáře, entity -> čistý text
python cli_tool.py --text-extract clanek.md clanek.txt
# Markdown syntaxe (#, **, *, `, [text](url), >, seznamy, ---) -> čistý text
```

### Bezpečnostní model
- Všechny cesty k souborům (`--add`, `--wc`, `--copy`, `--run-python`, `--code-extract`, `--text-extract`, `--out`) musí zůstat uvnitř projektového adresáře (`SUBDIR`) — pokus o `../` únik skončí jasnou chybou.
- `--run-python` navíc běží s `cwd` nastaveným na sandbox a s timeoutem — ochrana proti nekonečným smyčkám ve vygenerovaném kódu.

Adresář `sandbox` zde není izolace operačního systému: spuštěný Python
má oprávnění uživatele. Kontrola cest CLI neomezuje kód uvnitř skriptu.

### Dávkové zpracování (`--batch` + `@for VAR in $batch_list`)

```bash
python cli_tool.py --batch
```
- Vypíše (jednou za sebou) všechny soubory (jakéhokoli typu, jen top-level, ne rekurzivně) v `SUBDIR/<batch_in>` (výchozí `src`).
- Zajistí, že `SUBDIR/<batch_out>` (výchozí `dest`) existuje.
- Vždy zapíše seznam názvů (jeden na řádek) do **pevně daného** `SUBDIR/batch_list.txt` — i prázdná dávka vytvoří prázdný soubor. To je kontrakt s `runner.py`, `cli_tool.json` ho nekonfiguruje.
- `--batch-img` vybere jen `.png`, `.jpg` a `.jpeg`; je určený pro dávky obrázků.
- `--batch-txt` vybere jen `.txt`, `.md`, `.py`, `.html` a další běžné textové či zdrojové přípony (`.json`, `.yaml`, `.csv`, `.js`, `.ts`, `.css`, `.sh`, `.bat`, `.ps1`, `.sql`, `.toml`, `.xml`, `.log`, `.rst`).

`runner.py` načte `@for VAR in $batch_list` až za běhu flow. Proto může `--batch` i následné zpracování být v jednom souboru a v uvedeném pořadí:

```
# flow_batch_test.txt
$batch_in = "src"
$batch_out = "dest"

python3 cli_ollama.py --project project_example
python3 cli_tool.py --batch-txt

@for VAR in $batch_list
    python3 cli_tool.py --clr
    python3 cli_tool.py --add "zdrojový soubor" $batch_in/$VAR
    python3 cli_ollama.py --context tools_context.txt --input "Shrň obsah." --out batch_result.txt
    python3 cli_tool.py --copy batch_result.txt $batch_out/$VAR.txt
@endfor
```

Seznam se čte z `SUBDIR/batch_list.txt`, proto musí být před smyčkou příslušný příkaz `cli_tool.py --batch`, `--batch-img` nebo `--batch-txt`.

**Proč `$batch_out/$VAR.txt`, ne přepsání přípony:** tenhle jazyk záměrně nemá manipulaci s řetězci (žádné "ořízni příponu"). Připojení `.txt` k celému původnímu názvu je jediný bezpečný způsob bez kolizí — `photo.png` a `photo.md` skončí jako `photo.png.txt`/`photo.md.txt`, ne oba jako `photo.txt` přepisující se navzájem.

**Známé omezení:** `--add` čte soubor jako text — na binární typy (`.png` apod.) spadne. Smíšené dávky (text + obrázky) by potřebovaly větvení podle přípony souboru, které `@if` zatím neumí (jen `file_exists`/`file_not_empty`).

### Ukázkový flow krok (generuj → vyčisti → spusť → vyhodnoť)
```
python3 cli_ollama.py --input "..." --out generated.py
python3 cli_tool.py --code-extract generated.py
python3 cli_tool.py --copy generated.py sandbox/generated.py
python3 cli_tool.py --run-python generated.py

@if file_exists("code_ok.flag")
    python3 cli_ollama.py --context code_report.txt --input "Potvrď, že výstup dává smysl." --out review.txt
@else
    python3 cli_ollama.py --context code_report.txt --input "Vysvětli chybu a navrhni opravu." --out review.txt
@end
```

---

## TODO — náměty do budoucna

- [ ] `--json URL --path a.b.c` — stáhne API a rovnou vytáhne konkrétní hodnotu z JSON (místo 1000 znaků syrové odpovědi v kontextu)
- [ ] `--head FILE N` / `--tail FILE N` — do kontextu jen prvních/posledních N řádků souboru (typicky log), místo celého `--add`
- [ ] `--calc "výraz"` — bezpečný lokální kalkulátor pro přesná čísla do kontextu
- [ ] `--diff F1 F2` — stručný rozdíl mezi dvěma soubory (např. mezi dvěma verzemi vygenerovaného kódu)
- [ ] `--uuid` / `--rand N` — vygeneruje ID nebo náhodné číslo do kontextu
- [ ] `file_equals("FILE", "hodnota")` podmínka v `runner.py` — pro `@if` nad LLM odpovědí typu true/false (viz diskuse o `$code_ok`)
- [ ] Historie běhů `--run-python` — volitelně ukládat i starší reporty (timestamped), ne jen poslední přepsaný
- [ ] `--run-python` pro `.sh`/`.bat` (ne jen `.py`) — spouštění přes shell/cmd se stejným reportem a OK markerem
- [ ] `--url` s vlastními hlavičkami / POST tělem (dnes jen GET s pevnou `User-Agent`)
- [ ] `--code-extract`: rozpoznávat jazyk fence bloku (tag `python` vs `bash`) a podle přípony FILE brát jen odpovídající blok
- [ ] `--text-extract`: lepší podpora tabulek (`| a | b |`) a vnořených seznamů v Markdownu
- [ ] `--env VAR=default` — možnost výchozí hodnoty, když proměnná není nastavená
- [ ] `--check-config` — ověří `cli_tool.json` (validní JSON, rozumné typy klíčů) a vypíše přehled aktivní konfigurace
- [ ] Volitelný limit velikosti sandboxu / automatické mazání starých vygenerovaných souborů
- [ ] `@if` podmínka podle přípony souboru (např. `file_extension("$VAR", "png")`) — umožnilo by v jedné `@for $batch_list` smyčce větvit mezi textovým a obrazovým zpracováním
- [ ] `--batch --recursive` — volitelně procházet i podadresáře `batch_in`
- [ ] `cli_tool.json` klíč pro název `batch_list.txt` (dnes napevno, kvůli volné vazbě mezi `cli_tool.py` a `runner.py`)

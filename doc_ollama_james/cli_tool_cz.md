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
| `--batch` | zapíše soubory z `batch_in` do `batch_list.txt` pro runner |
| `--batch-img` | vybere jen obrázky `.png`, `.jpg`, `.jpeg` |
| `--batch-txt` | vybere jen textové a zdrojové soubory |

Všechny akce jsou vzájemně se vylučující (jedna za spuštění) — konzistentní s `cli_ollama.py`/`cli_db.py`.

Příkazy spouštějte z kořene projektu. V James lze nástroj volat i přes
Chat → `/tool --PARAM`, například `/tool --date-time`.
Dávky jsou nerekurzivní; seznam čte `@for VAR in $batch_list` až za běhu.
Příklady najdete v `../flows/flow_batch_txt.txt` a v `cli_tool.md`.

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

# James 0.2.1 — přehled úprav

Soubory dotčené touto sadou úprav: `james.py`, `cli_ollama.py`, `cli_db.py`, `lib/wrapp_db.py`.

---

## 1. Chat: přepínání modelu příkazem `/mod`

**Soubor:** `james.py`

- Nová funkce `extract_chat_mod_command()` rozpozná zprávu začínající `/mod`:
  - `/mod NEW` — jen přepne aktivní model chatu, nic dalšího se neodešle.
  - `/mod NEW zbytek zprávy` — přepne model **a** zbytek textu za názvem modelu rovnou pošle jako běžnou chat zprávu s novým modelem (řeší případ, kdy uživatel napíše model a otázku na jeden řádek).
  - Samotné `/mod` bez názvu modelu → chybová hláška, nic se nemění.
- `run_chat()` nově drží proměnnou `active_model`, inicializovanou na `config["chat_model"]` z `james.json`. `/mod` ji přepíše a hodnota se drží dál po celou chat session (přežije i `/clr`, který maže jen kontext konverzace, ne model).
- `run_flow()` se volá s `model_override=active_model` místo pevného `config["chat_model"]`, takže se do `runner.py` → `cli_ollama.py` posílá `--model NEW` stejným mechanismem, jakým se dnes posílá `--sc`.
- Nápověda chatu (`render_chat_commands()`) a `show_help()` doplněny o `/mod NEW`.

**`cli_ollama.py`** — beze změny; parametr `--model` tam už existoval a plně fungoval, jen chyběl chatový příkaz v `james.py`, který by ho využil.

---

## 2. Ukládání doby trvání tasku do databáze (`key1`)

**Cíl:** ukládat dobu trvání každého tasku (`Duration`, dřív jen v konzoli/logu) do stejného databázového záznamu, kde se už ukládá JSON o tokenech (`key2`).

**`lib/wrapp_db.py`**
- `record_task_output()` má nový volitelný parametr `key1: str | None = None`, který se ukládá do existujícího sloupce `key1` (dřív tam bylo natvrdo `None`). Žádná migrace databáze nebyla potřeba, sloupec už v schématu existoval.

**`cli_ollama.py`**
- Přidán `import time`.
- Kolem volání `app.run_task()` / `run_ocr_task()` / `run_describe_task()` se měří `time.monotonic()`.
- Výsledná doba se formátuje stejně jako v `runner.py` (`f"{task_duration:.1f}"`, např. `"42.4"`) a posílá se jako `key1` do `record_task_output()`, vedle `key2` s JSON o tokenech.

Poznámka: měří se čas jednoho tasku uvnitř `cli_ollama.py`, ne celého flow z `runner.py` — protože zápis do DB probíhá v `cli_ollama.py` ještě předtím, než `runner.py` zná celkovou dobu flow. U typického použití (james.py posílá jednokrokové flow) se hodnota prakticky shoduje s hláškou `Flow completed successfully… [Duration: 42.4 s]`.

---

## 3. Souhrnný report databáze doplněn o `duration`

**`lib/wrapp_db.py`**
- `summarize_task_rows()` nově sčítá `key1` (string typu `"42.4"`) přes všechny záznamy, bezpečně přeskakuje `None`/neplatné hodnoty, a vrací `duration_seconds` zaokrouhlené na 1 desetinné místo.

**`cli_db.py`**
- `--sum` výstup doplněn o poslední řádek `duration: {X.X} s`.

**`james.py`** — beze změny; `render_database_menu()` čte výstup `cli_db.py --sum` po řádcích a jen ho vypisuje, takže nový řádek se v hlavičce menu DATABASE objeví automaticky:

```
DATABASE
python .\cli_db.py --sum
Total records: 289
Projects: 4
eval_count: 15059
prompt_eval_count: 59189
response_chunks: 14490
duration: 1234.5 s
```

---

## 4. Navigace v detailu databázového záznamu: prev/next se šipkami

**`james.py`**

- `read_key()` doplněn o detekci pravé šipky (`right`) — na Windows (`msvcrt`, kód `M`) i na Linuxu (`\x1b[C` / `\x1bOC`) — vedle už existujících `up` / `down` / `left`.
- `render_database_record()` (detail jednoho záznamu s procházením seznamu) má upravený footer na dva samostatné bloky:

  ```
  -----------------------------------------------------------------
         (p)rev ←   (n)ext →
  -----------------------------------------------------------------
         (b)ack
  ```

  - `p` i `←` vyvolávají stejnou akci jako dřív jen `p` (posun v seznamu).
  - `n` i `→` vyvolávají stejnou akci jako dřív jen `n`.
  - `back` je nyní **jen** `b`, bez zmínky o šipce — levá šipka už znamená „prev“, takže by matoucí zmínka o `← left arrow` u back kolidovala.
- Ostatní menu (`render_back_footer()`, `wait_for_back()`, hlavní menu, seznam záznamů v `browse_database_records()` atd.) zůstávají beze změny — `back or ← left arrow` platí i nadále všude, kde levá šipka skutečně znamená návrat zpět.

---

## Shrnutí dotčených souborů

| Soubor | Změna |
|---|---|
| `james.py` | `/mod` v chatu, prev/next šipky v detailu záznamu |
| `cli_ollama.py` | měření a ukládání `key1` (duration) |
| `lib/wrapp_db.py` | `record_task_output(key1=...)`, `summarize_task_rows()` počítá `duration_seconds` |
| `cli_db.py` | `--sum` vypisuje řádek `duration:` |

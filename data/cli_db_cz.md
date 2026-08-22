# `cli_db.py` — databáze dokončených tasků

`cli_db.py` spravuje sdílenou lokální SQLite databázi dokončených tasků. Běžná
databáze je `data/tasks.db`; `cli_ollama.py` do ní při nastavení `"db": true`
automaticky ukládá úspěšně dokončené odpovědi.

Databáze je společná pro všechny pracovní projekty. Aktivní adresář z
`project.json` se používá pouze pro exportované soubory `.txt` a `.json`.

## Základní použití

```powershell
# Vypíše záznamy ze sdílené databáze data/tasks.db.
python cli_db.py --list
python cli_db.py -l

# Zobrazí celý záznam.
python cli_db.py --show 10

# Vytvoří standardní databázi podle schématu.
python cli_db.py --create tasks.db tasks.json
```

Schéma záznamů je v `data/tasks.json`. Obsahuje mimo jiné `uid`, `datetime`,
`project`, `selector`, `task`, `model`, `parameters`, `prompt`, `instruction`,
`answer`, `stars` a pomocná pole `active`, `key1`, `key2`, `key3`.

## Výběr databáze

Bez parametru pracuje CLI s `data/tasks.db`. Přepínač `--db` vybere jinou
pracovní databázi; prostý název se hledá v `data/`.

```powershell
python cli_db.py --db holly_pivo1.db --list
python cli_db.py --db holly_pivo1.db --show 10
python cli_db.py --db holly_pivo1.db --setstar 4 --id 10
```

U většiny akcí lze jako pracovní databázi použít také závěrečný poziční
argument. U `--list` má však závěrečný `DATABASE` jiný význam: je to název nové
filtrované databáze. Pro zdroj seznamu proto v tomto případě používejte `--db`.

## Seznam a filtry

`--list` vypisuje kompaktní tabulku. Filtry lze libovolně kombinovat; všechny
jsou vyhodnoceny současně.

```powershell
python cli_db.py --list --project project_test
python cli_db.py --list --sele mcp_obt
python cli_db.py --list --star 3
python cli_db.py --list --model deepseek
python cli_db.py --db holly_pivo1.db --list --model deepseek
```

- `--project NAME` vyžaduje přesnou shodu v poli `project`.
- `--sele NAME` nebo `--selector NAME` vyžaduje přesnou shodu v poli `selector`.
- `--star 0..5` vyžaduje přesnou hodnotu `stars`.
- `--model TEXT` vyhledává `TEXT` jako část názvu modelu bez rozlišování
  velikosti písmen. Například `deepseek` najde `deepseek-ocr:3b`.

### Uložení filtrovaného výběru

Jestliže za `--list` uvedete název `.db`, vytvoří se nová databáze v `data/`
obsahující pouze vybrané řádky. Sdílená zdrojová databáze se nemění a ID
vybraných záznamů se zachovají. Cílový soubor nesmí už existovat.

```powershell
python cli_db.py --list --model deepseek filter_deepseek.db
# čte data/tasks.db, vytvoří data/filter_deepseek.db

python cli_db.py --db holly_pivo1.db --list --star 5 holly_favorites.db
# čte data/holly_pivo1.db, vytvoří data/holly_favorites.db
```

Bez závěrečného `.db` se nic nekopíruje — seznam se jen vypíše.


### Klonování "ohvězdičkovaných" záznamů

```powershell
python ./cli_db.py --clone-stars ./data/test_stars1.db
Cloned 5 starred record(s) from data\tasks.db to data\test_stars1.db.
python ./cli_db.py --db test_stars1.db -l 

> list / table
```

### Sloupce výpisu

Sloupce tabulky definuje `data/tasks_base.json`:

```json
{
  "version": 1,
  "columns": [
    {"field": "uid", "name": "id", "width": 5},
    {"field": "model", "name": "model", "width": 20},
    {"field": "answer", "name": "answer", "width": 20}
  ]
}
```

- `field` je název sloupce v databázi,
- `name` je název zobrazený v záhlaví,
- `width` je pevná šířka ve znacích,
- pořadí položek určuje pořadí sloupců.

Text delší než `width` se zkrátí na `width - 2` znaků a doplní se `..`.

## Export jednoho záznamu

Exporty čtou z vybrané databáze (`data/tasks.db` nebo `--db DATABASE`) a vždy
zapisují přímo do aktivního pracovního adresáře určeného `project.json`.
Podadresáře ani absolutní cesty pro výstup nejsou povolené.

### Jen odpověď

`-e` a `-exp` uloží pouze pole `answer`.

```powershell
python cli_db.py -e 10
# <aktivní projekt>/export.txt

python cli_db.py -exp 10 moje.txt
# <aktivní projekt>/moje.txt
```

### Celý záznam v JSON

`--export` uloží celý řádek databáze včetně ID, času, parametrů, promptu,
instrukce, odpovědi a pomocných polí.

```powershell
python cli_db.py --export 10
# <aktivní projekt>/export.json

python cli_db.py --export 10 moje.json
# <aktivní projekt>/moje.json
```

Pro kompatibilitu lze ID předat také přes `--id ID` a název výstupu přes
`--out FILE`, například `python cli_db.py -e --id 10 --out moje.txt`.

## Úpravy záznamů

```powershell
# Přidá minimální testovací záznam; text se uloží jako answer.
python cli_db.py --add
python cli_db.py -a "test answer"

# Změní odpověď.
python cli_db.py --edit 10 "nová odpověď"

# Nastaví hodnocení od 0 do 5.
python cli_db.py --setstar 4 --id 10
python cli_db.py --set-star 4 --id 10

# Trvale smaže záznam.
python cli_db.py --delete 10
python cli_db.py -d 10
```

`--show ID` v interaktivním terminálu umožňuje procházet záznamy šipkami vlevo
a vpravo; `d` a následné `y` smaže právě zobrazený záznam, `q` ukončí prohlížení.

## Slučování databází

`--merge-db SOURCE.db` připojí všechny záznamy ze zdrojové databáze do vybrané
pracovní databáze. Cílem je výchozí `data/tasks.db`, nebo databáze zvolená přes
`--db`. Zdroj i cíl mají mít stejné schéma; importovaným záznamům se přidělí nová
ID, aby nedošlo ke kolizi s existujícími řádky.

```powershell
# Připojí data/db2.db do data/tasks.db.
python cli_db.py --merge-db db2.db

# Připojí data/db2.db do data/holly_pivo1.db.
python cli_db.py --db holly_pivo1.db --merge-db db2.db
```

Zdroj a cíl musí být rozdílné soubory.

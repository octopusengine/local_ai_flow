# Task database and `cli_db.py`

`data/tasks.json` defines the strict schema for the local SQLite task database.
The default shared database is `data/tasks.db`. With `"db": true` in the active
`project.json`, every successful `cli_ollama.py` task stores its final answer in
that database.

```json
{
  "db": true,
  "selector": "experiment-a"
}
```

The database is shared across projects. The active project from `project.json`
is used only for exported `.txt` and `.json` files. The database is created
automatically on the first recorded task, or explicitly with:

```powershell
python cli_db.py --create tasks.db tasks.json
```

## Record schema

The schema has version `1` and a single `tasks` table. Column names, order, and
types are a strict compatibility contract.

| Column | Type | Meaning |
| --- | --- | --- |
| `uid` | INTEGER | Auto-incremented record ID. |
| `datetime` | TEXT | Local ISO-8601 completion timestamp. |
| `project` | TEXT | Active project directory from `project.json`. |
| `selector` | TEXT | Optional project-level grouping label. |
| `task` | TEXT | Task configuration used for the run. |
| `model` | TEXT | Ollama model that produced the answer. |
| `parameters` | TEXT | JSON text containing effective generation parameters. |
| `prompt` | TEXT | Final prompt sent to the model. |
| `instruction` | TEXT, nullable | Optional task instruction. |
| `answer` | TEXT | Final answer; thinking and diagnostics are excluded. |
| `stars` | INTEGER, nullable | User rating from `0` to `5`. |
| `active` | INTEGER | Active flag, initially `1`. |
| `key1`, `key2`, `key3` | TEXT, nullable | Editable metadata. For new `cli_ollama.py` records, `key2` contains optional Ollama usage JSON: exact `prompt_eval_count` and `eval_count` when returned by the server, plus `response_chunks` for streamed responses (a coarse fallback, not a token count). |

Existing databases without the `selector` column are migrated when opened.

## Selecting the working database

Without an option, `cli_db.py` uses `data/tasks.db`. Use `--db` to work with a
different database; a bare filename is resolved in `data/`.

```powershell
python cli_db.py --db holly_pivo1.db --list
python cli_db.py --db holly_pivo1.db --show 10
python cli_db.py --db holly_pivo1.db --setstar 4 --id 10
```

For actions other than `--list`, the optional final `DATABASE` argument can
also select the working database. With `--list`, that final argument creates a
filtered output database; use `--db` to select the list source.

## Structure, grouping, and summary

```powershell
# Current SQLite field names and types, one field per line.
python cli_db.py --stru

# Record counts grouped by any tasks-table field, largest groups first.
python cli_db.py --group project

# Records, distinct projects, and sums of the optional key2 usage JSON.
python cli_db.py --sum
```

`--sum` reports `eval_count`, `prompt_eval_count`, and `response_chunks` only
when a record's `key2` contains valid JSON usage data. Older records and other
free-form `key2` values are ignored for those three totals.

## Listing and filtering

```powershell
python cli_db.py --list
python cli_db.py -l
python cli_db.py --list --project project_example
python cli_db.py --list --selector experiment-a
python cli_db.py --list --sele experiment-a
python cli_db.py --list --star 5
python cli_db.py --list --model deepseek
```

Filters can be combined and all must match:

- `--project NAME` matches `project` exactly.
- `--selector NAME` or `--sele NAME` matches `selector` exactly.
- `--star 0..5` matches `stars` exactly.
- `--model TEXT` matches model names containing `TEXT`, case-insensitively.
  For example, `deepseek` matches `deepseek-ocr:3b`.

Rows are ordered newest first. The compact table layout is configured in
`data/tasks_base.json`.

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

Each item selects a database `field`, gives its displayed header `name`, and
sets its fixed character `width`. Their order controls the table order. Values
longer than `width` are shortened to `width - 2` characters followed by `..`.

### Creating a filtered database

Put a target name after a `--list` command to create a new database containing
exactly the selected rows. The source database is unchanged and source IDs are
preserved. The target must not already exist.

```powershell
# Read data/tasks.db and create data/filter_deepseek.db.
python cli_db.py --list --model deepseek filter_deepseek.db

# Read data/holly_pivo1.db and create data/holly_favorites.db.
python cli_db.py --db holly_pivo1.db --list --star 5 holly_favorites.db
```

Without the final database name, `--list` only prints rows.

## Viewing and modifying records

```powershell
# Show one complete record.
python cli_db.py --show 12

# Add a minimal dummy record; optional text becomes its answer.
python cli_db.py --add
python cli_db.py -a "test answer"

# Replace one answer.
python cli_db.py --edit 12 "edited answer text"

# Set a rating from 0 to 5.
python cli_db.py --setstar 4 --id 12
python cli_db.py --set-star 4 --id 12

# Permanently delete a record.
python cli_db.py --delete 12
python cli_db.py -d 12
python cli_db.py --dele 12
```

`--add` takes the active project's `subdir` and `selector` from `project.json`.
In an interactive terminal, `--show ID` remains open: left/right arrows browse
existing records, `d` then `y` deletes the displayed record, and `q` exits. In
non-interactive use it prints the requested record once and exits.

## Exporting one record

Exports read from the selected working database and always write directly into
the active project directory from `project.json`. Output filenames must be plain
names; subdirectories and absolute paths are rejected.

### Export only the answer

`-e` and `-exp` write the record's `answer` field.

```powershell
python cli_db.py -e 10
# <active project>/export.txt

python cli_db.py -exp 10 my_answer.txt
# <active project>/my_answer.txt
```

### Export the full record as JSON

`--export` writes the complete database row, including ID, timestamp,
parameters, prompt, instruction, answer, and metadata fields.

```powershell
python cli_db.py --export 10
# <active project>/export.json

python cli_db.py --export 10 my_record.json
# <active project>/my_record.json
```

For compatibility, use `--id ID` instead of the direct ID and `--out FILE`
instead of the direct output filename:

```powershell
python cli_db.py -e --id 10 --out my_answer.txt
```

## Merging databases

`--merge-db SOURCE.db` appends all rows from the source database to the selected
working database. The default destination is `data/tasks.db`; use `--db` to
choose another destination. Bare source names resolve in `data/`.

```powershell
# Append data/db2.db to data/tasks.db.
python cli_db.py --merge-db db2.db

# Append data/db2.db to data/holly_pivo1.db.
python cli_db.py --db holly_pivo1.db --merge-db db2.db
```

The source and destination must have the same `tasks` schema and must be
different files. Existing destination IDs stay unchanged; imported rows receive
new IDs to avoid collisions.

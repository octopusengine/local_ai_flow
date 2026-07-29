# Task database and `cli_db`

`data/tasks.json` is the versioned schema for the local SQLite database
`data/tasks.db`. The database stores the final answers of successfully completed
`cli_ollama.py` tasks when the active `project.json` contains:

```json
{
  "db": true,
  "selector": "experiment-a"
}
```

The database is created automatically on the first recorded task. The selector
is an optional project-level label used to group or filter records. Change it
with `python cli_ollama.py --selector NAME` (the compatibility alias
`--setector` also works).

## `tasks.json` schema

The schema uses version `1` and declares one table named `tasks`. It is a strict
contract: the column names, order, types, and required settings must match the
file exactly. Do not add, remove, rename, or reorder columns unless the database
code is changed accordingly.

| Column | Type | Meaning |
| --- | --- | --- |
| `uid` | INTEGER | Auto-incremented primary key and record ID. |
| `datetime` | TEXT | Local ISO-8601 timestamp of the completed task. |
| `project` | TEXT | Active project directory from `project.json`. |
| `selector` | TEXT | Project-level grouping label from `project.json`; it may be empty. |
| `task` | TEXT | Path/name of the task configuration used for the run. |
| `model` | TEXT | Ollama model used for the response. |
| `parameters` | TEXT | JSON object containing the effective generation parameters. |
| `prompt` | TEXT | Final prompt sent to the model. |
| `instruction` | TEXT, nullable | Optional task instruction. |
| `answer` | TEXT | Final model answer. Thinking and diagnostic output are not stored. |
| `stars` | INTEGER, nullable | User rating from `0` to `5`. |
| `active` | INTEGER | Active flag, initially `1`. |
| `key1` | TEXT, nullable | Reserved editable metadata field. |
| `key2` | TEXT, nullable | Reserved editable metadata field. |
| `key3` | TEXT, nullable | Reserved editable metadata field. |

The schema also creates indexes for `project`, `selector`, and the
`active`/`datetime` pair. Existing databases without the `selector` column are
migrated automatically when opened by the application.

## `cli_db.py` commands

Run all commands from the repository root:

```powershell
python cli_db.py --list
```

The default database is `data/tasks.db`. A bare database name selects a file in
that same directory, so `python cli_db.py db2.db --list` reads `data/db2.db`.

### Create or initialize a database

```powershell
python cli_db.py --create data/tasks.db data/tasks.json
```

Bare `tasks.db` and `tasks.json` names also resolve to the `data` directory.
Creating an already valid database only validates its schema; it does not erase
records.

### Add a test record

```powershell
python cli_db.py --add
python cli_db.py -a "test answer"
```

This writes a minimal `dummy test` record using the active project's `subdir`
and `selector` values from `project.json`. The optional text is stored directly
in the record's `answer` field.

### List and filter records

```powershell
python cli_db.py --list
python cli_db.py -l
python cli_db.py --list --project project_example
python cli_db.py --list --selector experiment-a
python cli_db.py --list --sele experiment-a
python cli_db.py --list --star 5
```

`--project`, `--selector`/`--sele`, and `--star` are exact filters and can be
combined. The list is ordered from newest to oldest and shows compact previews
of the ID, project, selector, model, prompt, and answer.

### Show and browse complete records

```powershell
python cli_db.py --show 12
```

In an interactive terminal, the full record remains open. Use these keys without
pressing Enter:

| Key | Action |
| --- | --- |
| Left arrow | Show the previous existing ID. |
| Right arrow | Show the next existing ID. |
| `d` or `D` | Ask to delete the currently displayed record. |
| `y` | Confirm the pending deletion. |
| `n` | Cancel the pending deletion. |
| `q` | Exit browsing, or cancel a pending deletion. |

Navigation wraps at both ends and skips IDs that do not exist. After a confirmed
deletion, browsing continues at the next available record. In non-interactive
output (for example a pipe or script), `--show` prints the requested record once
and exits without waiting for keys.

### Rate a record

```powershell
python cli_db.py --setstar 4 --id 12
python cli_db.py --set-star 4 --id 12
```

The rating must be a whole number from `0` to `5`.

### Delete a record directly

```powershell
python cli_db.py --delete 12
python cli_db.py -d 12
python cli_db.py --dele 12
```

These commands permanently delete the specified record immediately. Use
`--show ID` and the interactive `d` confirmation when you want to inspect a
record before removing it.

### Merge another database

```powershell
python cli_db.py --merge db2.db
python cli_db.py -m db2.db
```

The records from `data/db2.db` are appended to the default database. The
existing IDs remain unchanged; each imported record gets a fresh ID. The merge
is rejected unless both databases have the same `tasks` column layout.

### Export one answer

```powershell
python cli_db.py --export 123
python cli_db.py -e 123 --out single_answer_123.txt
python cli_db.py db2.db -e --ID 123 --out single_answer_123.txt
```

Without `--out`, the answer is written verbatim to `answer.txt` in the current
working directory. `--ID` is accepted as an alias for `--id` in the second
export form.

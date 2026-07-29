"""Shared SQLite storage for completed ``cli_ollama.py`` task outputs."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping


__version__ = "0.23.12"


IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
ALLOWED_COLUMN_TYPES = {"TEXT", "INTEGER"}
REQUIRED_COLUMNS = (
    "uid",
    "datetime",
    "project",
    "selector",
    "task",
    "model",
    "parameters",
    "prompt",
    "instruction",
    "answer",
    "stars",
    "active",
    "key1",
    "key2",
    "key3",
)
LEGACY_COLUMNS_WITHOUT_SELECTOR = tuple(name for name in REQUIRED_COLUMNS if name != "selector")
DEFAULT_TASKS_DATABASE_PATH = Path("data") / "tasks.db"
DEFAULT_TASKS_SCHEMA_PATH = Path("data") / "tasks.json"


class TaskDatabaseError(ValueError):
    """Report a database or schema problem in a command-line friendly form."""


def _quoted_identifier(value: str) -> str:
    """Quote one schema identifier after validating its conservative syntax."""

    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        raise TaskDatabaseError(f"Invalid database identifier: {value!r}")
    return f'"{value}"'


def _read_schema(schema_path: Path) -> dict[str, object]:
    """Load and validate the small declarative SQLite schema."""

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise TaskDatabaseError(f"Cannot read database schema {schema_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise TaskDatabaseError(f"Database schema is not valid JSON: {schema_path}: {error}") from error
    if not isinstance(schema, dict):
        raise TaskDatabaseError("Database schema must be a JSON object.")
    if schema.get("version") != 1:
        raise TaskDatabaseError("Database schema requires version 1.")
    if schema.get("table") != "tasks":
        raise TaskDatabaseError('Database schema table must be "tasks".')

    columns = schema.get("columns")
    if not isinstance(columns, list) or not columns:
        raise TaskDatabaseError('Database schema requires a non-empty "columns" array.')
    names: list[str] = []
    primary_keys = 0
    for column in columns:
        if not isinstance(column, dict):
            raise TaskDatabaseError("Each database column must be an object.")
        name = column.get("name")
        column_type = column.get("type")
        _quoted_identifier(name)  # type: ignore[arg-type]
        if not isinstance(column_type, str) or column_type not in ALLOWED_COLUMN_TYPES:
            raise TaskDatabaseError(f"Unsupported type for column {name!r}.")
        if not isinstance(column.get("nullable", True), bool):
            raise TaskDatabaseError(f"Column {name!r} has an invalid nullable value.")
        if "primary_key" in column and not isinstance(column["primary_key"], bool):
            raise TaskDatabaseError(f"Column {name!r} has an invalid primary_key value.")
        if "auto_increment" in column and not isinstance(column["auto_increment"], bool):
            raise TaskDatabaseError(f"Column {name!r} has an invalid auto_increment value.")
        if column.get("primary_key"):
            primary_keys += 1
        if column.get("auto_increment") and (
            name != "uid" or column_type != "INTEGER" or column.get("primary_key") is not True
        ):
            raise TaskDatabaseError("Only the INTEGER PRIMARY KEY uid column may auto-increment.")
        if "default" in column and column["default"] not in (None, 0, 1):
            raise TaskDatabaseError(f"Column {name!r} has an unsupported default value.")
        names.append(name)  # type: ignore[arg-type]
    if tuple(names) != REQUIRED_COLUMNS:
        raise TaskDatabaseError(
            "Database schema columns must match the tasks record contract exactly."
        )
    if primary_keys != 1 or columns[0].get("primary_key") is not True:
        raise TaskDatabaseError("The uid column must be the only primary key.")
    if columns[0].get("auto_increment") is not True:
        raise TaskDatabaseError("The uid column must auto-increment.")

    indexes = schema.get("indexes", [])
    if not isinstance(indexes, list):
        raise TaskDatabaseError('Database schema "indexes" must be an array.')
    for index in indexes:
        if not isinstance(index, dict):
            raise TaskDatabaseError("Each database index must be an object.")
        _quoted_identifier(index.get("name"))  # type: ignore[arg-type]
        index_columns = index.get("columns")
        if not isinstance(index_columns, list) or not index_columns:
            raise TaskDatabaseError("Each database index requires columns.")
        for name in index_columns:
            if name not in names:
                raise TaskDatabaseError(f"Index uses an unknown column: {name!r}")
    return schema


def _create_or_validate_schema(connection: sqlite3.Connection, schema: dict[str, object]) -> None:
    """Create the configured table and indexes, or verify the existing table."""

    columns = schema["columns"]
    assert isinstance(columns, list)
    column_definitions: list[str] = []
    for column in columns:
        assert isinstance(column, dict)
        definition = f"{_quoted_identifier(column['name'])} {column['type']}"
        if column.get("primary_key"):
            definition += " PRIMARY KEY"
        if column.get("auto_increment"):
            definition += " AUTOINCREMENT"
        if column.get("nullable") is False:
            definition += " NOT NULL"
        if "default" in column:
            default_value = column["default"]
            definition += " DEFAULT NULL" if default_value is None else f" DEFAULT {default_value}"
        column_definitions.append(definition)

    table_name = _quoted_identifier(schema["table"])  # type: ignore[arg-type]
    connection.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_definitions)})")
    existing_columns = tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table_name})"))
    if existing_columns != REQUIRED_COLUMNS:
        raise TaskDatabaseError("Existing database schema does not match the tasks record contract.")
    indexes = schema["indexes"]
    assert isinstance(indexes, list)
    for index in indexes:
        assert isinstance(index, dict)
        index_name = _quoted_identifier(index["name"])
        index_columns = index["columns"]
        assert isinstance(index_columns, list)
        rendered_columns = ", ".join(_quoted_identifier(name) for name in index_columns)
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({rendered_columns})"
        )


def create_database(database_path: Path, schema_path: Path) -> None:
    """Create or validate a SQLite task database from ``tasks.json``.

    Version 1 initially used UUID text IDs. Existing records are migrated once
    to SQLite-generated integer IDs in insertion order.
    """

    schema = _read_schema(schema_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(database_path) as connection:
            existing_columns = list(connection.execute('PRAGMA table_info("tasks")'))
            existing_names = tuple(row[1] for row in existing_columns)
            legacy_schema = existing_names == LEGACY_COLUMNS_WITHOUT_SELECTOR
            legacy_text_ids = legacy_schema and bool(existing_columns) and str(existing_columns[0][2]).upper() == "TEXT"
            if legacy_schema:
                old_rows = list(connection.execute("SELECT * FROM tasks ORDER BY rowid"))
                connection.execute("DROP TABLE tasks")
                _create_or_validate_schema(connection, schema)
                insert_columns = REQUIRED_COLUMNS[1:] if legacy_text_ids else REQUIRED_COLUMNS
                rendered_columns = ", ".join(_quoted_identifier(name) for name in insert_columns)
                placeholders = ", ".join("?" for _ in insert_columns)
                connection.executemany(
                    f"INSERT INTO tasks ({rendered_columns}) VALUES ({placeholders})",
                    [
                        tuple(
                            "" if name == "selector" else row[LEGACY_COLUMNS_WITHOUT_SELECTOR.index(name)]
                            for name in insert_columns
                        )
                        for row in old_rows
                    ],
                )
            else:
                _create_or_validate_schema(connection, schema)
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot create database {database_path}: {error}") from error


def read_db_enabled(project_config: Mapping[str, object]) -> bool:
    """Read the optional project-level switch that enables task recording."""

    enabled = project_config.get("db", False)
    if not isinstance(enabled, bool):
        raise TaskDatabaseError("'db' must be true or false in project.json.")
    return enabled


def read_db_selector(project_config: Mapping[str, object]) -> str:
    """Read the optional project-level label used to group recorded tasks."""

    selector = project_config.get("selector", "")
    if not isinstance(selector, str):
        raise TaskDatabaseError("'selector' must be text in project.json.")
    return selector


def record_task_output(
    database_path: Path,
    schema_path: Path,
    *,
    project: str,
    selector: str,
    task: str,
    model: str,
    parameters: Mapping[str, object],
    prompt: str,
    instruction: str | None,
    answer: str,
) -> int:
    """Persist one successfully completed model response and return its numeric ID."""

    required_text = {
        "project": project,
        "selector": selector,
        "task": task,
        "model": model,
        "prompt": prompt,
        "answer": answer,
    }
    for name, value in required_text.items():
        if not isinstance(value, str):
            raise TaskDatabaseError(f"Task record {name} must be text.")
    if instruction is not None and not isinstance(instruction, str):
        raise TaskDatabaseError("Task record instruction must be text or null.")

    create_database(database_path, schema_path)
    values = {
        "datetime": datetime.now().astimezone().isoformat(timespec="seconds"),
        "project": project,
        "selector": selector,
        "task": task,
        "model": model,
        "parameters": json.dumps(dict(parameters), ensure_ascii=False, sort_keys=True),
        "prompt": prompt,
        "instruction": instruction,
        "answer": answer,
        "stars": None,
        "active": 1,
        "key1": None,
        "key2": None,
        "key3": None,
    }
    table_name = _quoted_identifier("tasks")
    insert_columns = REQUIRED_COLUMNS[1:]
    rendered_columns = ", ".join(_quoted_identifier(name) for name in insert_columns)
    placeholders = ", ".join("?" for _ in insert_columns)
    try:
        with sqlite3.connect(database_path) as connection:
            cursor = connection.execute(
                f"INSERT INTO {table_name} ({rendered_columns}) VALUES ({placeholders})",
                tuple(values[name] for name in insert_columns),
            )
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot record completed task in {database_path}: {error}") from error
    if cursor.lastrowid is None:
        raise TaskDatabaseError("Database did not return an ID for the completed task.")
    return int(cursor.lastrowid)


def add_dummy_task(
    database_path: Path,
    schema_path: Path,
    project: str,
    selector: str,
    answer: str = "",
) -> int:
    """Add a minimal test record while keeping required schema fields neutral."""

    return record_task_output(
        database_path,
        schema_path,
        project=project,
        selector=selector,
        task="dummy test",
        model="",
        parameters={},
        prompt="",
        instruction=None,
        answer=answer,
    )


def merge_task_databases(destination_path: Path, source_path: Path, schema_path: Path) -> int:
    """Append every task from ``source_path`` to ``destination_path`` with new IDs.

    The destination is created or validated against the configured schema first.
    The source must have precisely the same SQLite column layout.  Omitting
    ``uid`` from the insert lets SQLite generate fresh IDs without changing any
    original IDs already present in the destination database.
    """

    if destination_path.resolve() == source_path.resolve():
        raise TaskDatabaseError("The source and destination databases must be different files.")
    if not source_path.is_file():
        raise TaskDatabaseError(f"Task database does not exist: {source_path}")

    create_database(destination_path, schema_path)
    insert_columns = REQUIRED_COLUMNS[1:]
    rendered_columns = ", ".join(_quoted_identifier(name) for name in insert_columns)
    source_columns = ", ".join(f"source.tasks.{_quoted_identifier(name)}" for name in insert_columns)
    try:
        connection = sqlite3.connect(destination_path)
        try:
            with connection:
                destination_layout = tuple(
                    tuple(row[1:6]) for row in connection.execute('PRAGMA table_info("tasks")')
                )
                connection.execute("ATTACH DATABASE ? AS source", (str(source_path),))
                source_layout = tuple(
                    tuple(row[1:6]) for row in connection.execute("PRAGMA source.table_info('tasks')")
                )
                if source_layout != destination_layout:
                    raise TaskDatabaseError("Source database schema does not match the destination tasks schema.")
                cursor = connection.execute(
                    f"INSERT INTO tasks ({rendered_columns}) "
                    f"SELECT {source_columns} FROM source.tasks ORDER BY source.tasks.uid"
                )
                return cursor.rowcount if cursor.rowcount >= 0 else connection.execute("SELECT changes()").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot merge task database {source_path}: {error}") from error


def delete_task(database_path: Path, uid: int) -> bool:
    """Physically delete one task record by its positive numeric ID."""

    if isinstance(uid, bool) or not isinstance(uid, int) or uid < 1:
        raise TaskDatabaseError("The task ID must be a positive whole number.")
    if not database_path.is_file():
        raise TaskDatabaseError(f"Task database does not exist: {database_path}")
    try:
        with sqlite3.connect(database_path) as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE uid = ?", (uid,))
            return cursor.rowcount == 1
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot delete task record from {database_path}: {error}") from error


def set_task_stars(database_path: Path, uid: int, stars: int) -> bool:
    """Set a zero-to-five star rating for one task record."""

    if isinstance(uid, bool) or not isinstance(uid, int) or uid < 1:
        raise TaskDatabaseError("The task ID must be a positive whole number.")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 0 <= stars <= 5:
        raise TaskDatabaseError("Stars must be a whole number from 0 to 5.")
    if not database_path.is_file():
        raise TaskDatabaseError(f"Task database does not exist: {database_path}")
    try:
        with sqlite3.connect(database_path) as connection:
            cursor = connection.execute("UPDATE tasks SET stars = ? WHERE uid = ?", (stars, uid))
            return cursor.rowcount == 1
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot set task stars in {database_path}: {error}") from error


def set_task_answer(database_path: Path, uid: int, answer: str) -> bool:
    """Replace the answer text for one task record."""

    if isinstance(uid, bool) or not isinstance(uid, int) or uid < 1:
        raise TaskDatabaseError("The task ID must be a positive whole number.")
    if not isinstance(answer, str):
        raise TaskDatabaseError("The task answer must be text.")
    if not database_path.is_file():
        raise TaskDatabaseError(f"Task database does not exist: {database_path}")
    try:
        with sqlite3.connect(database_path) as connection:
            cursor = connection.execute("UPDATE tasks SET answer = ? WHERE uid = ?", (answer, uid))
            return cursor.rowcount == 1
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot update task answer in {database_path}: {error}") from error


def list_task_rows(
    database_path: Path,
    project: str | None = None,
    selector: str | None = None,
    stars: int | None = None,
) -> list[sqlite3.Row]:
    """Return task records, newest first, with optional exact filters."""

    if project is not None and (not isinstance(project, str) or not project.strip()):
        raise TaskDatabaseError("The project filter must be non-empty text.")
    if selector is not None and not isinstance(selector, str):
        raise TaskDatabaseError("The selector filter must be text.")
    if stars is not None and (isinstance(stars, bool) or not isinstance(stars, int) or not 0 <= stars <= 5):
        raise TaskDatabaseError("The stars filter must be a whole number from 0 to 5.")
    if not database_path.is_file():
        raise TaskDatabaseError(f"Task database does not exist: {database_path}")
    try:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            query = "SELECT * FROM tasks"
            conditions: list[str] = []
            values: list[str] = []
            if project is not None:
                conditions.append("project = ?")
                values.append(project)
            if selector is not None:
                conditions.append("selector = ?")
                values.append(selector)
            if stars is not None:
                conditions.append("stars = ?")
                values.append(str(stars))
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY datetime DESC, rowid DESC"
            return list(connection.execute(query, tuple(values)))
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot list task records from {database_path}: {error}") from error


def get_task_row(database_path: Path, uid: int) -> sqlite3.Row | None:
    """Return one complete task record by its positive numeric ID."""

    if isinstance(uid, bool) or not isinstance(uid, int) or uid < 1:
        raise TaskDatabaseError("The task ID must be a positive whole number.")
    if not database_path.is_file():
        raise TaskDatabaseError(f"Task database does not exist: {database_path}")
    try:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute("SELECT * FROM tasks WHERE uid = ?", (uid,)).fetchone()
    except sqlite3.Error as error:
        raise TaskDatabaseError(f"Cannot read task record from {database_path}: {error}") from error


def short_text(value: object, width: int = 20) -> str:
    """Collapse whitespace and return a compact, fixed-width-friendly preview."""

    if not isinstance(value, str):
        return ""
    if width < 2:
        raise ValueError("Preview width must be at least 2.")
    normalized = " ".join(value.removeprefix("\ufeff").split())
    return normalized if len(normalized) <= width else f"{normalized[:width - 1]}…"


def format_task_rows(
    rows: Iterable[sqlite3.Row], text_width: int = 20, selector_width: int = 10, id_width: int = 5
) -> list[str]:
    """Render compact ID/project/selector/model/prompt/answer rows for ``cli_db.py --list``."""

    if id_width < 1:
        raise ValueError("ID preview width must be at least 1.")
    header = " | ".join(
        ["id".ljust(id_width)]
        + ["project".ljust(text_width), "selector".ljust(selector_width)]
        + [name.ljust(text_width) for name in ("model", "prompt", "answer")]
    )
    lines = [header]
    for row in rows:
        lines.append(
            " | ".join(
                [short_text(str(row["uid"]), id_width).ljust(id_width)]
                + [short_text(row["project"], text_width).ljust(text_width)]
                + [short_text(row["selector"], selector_width).ljust(selector_width)]
                + [short_text(row[name], text_width).ljust(text_width) for name in ("model", "prompt", "answer")]
            )
        )
    return lines

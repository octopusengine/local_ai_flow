"""Create and inspect the local database of completed Ollama task outputs."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import os
from pathlib import Path
import sys

from lib.wrapp_db import (
    DEFAULT_TASKS_DATABASE_PATH,
    DEFAULT_TASKS_SCHEMA_PATH,
    TaskDatabaseError,
    add_dummy_task,
    create_database,
    delete_task,
    format_task_rows,
    get_task_row,
    list_task_rows,
    merge_task_databases,
    set_task_answer,
    set_task_stars,
)
from lib.wrapp_log import load_project_config
from lib.wrapp_terminal import Terminal, ansi_enabled


PROJECT_ROOT = Path(__file__).resolve().parent


def render_task_record(row: object) -> None:
    """Print one complete task record with the interactive navigation hint."""

    terminal = Terminal()
    for field_name in row.keys():  # type: ignore[union-attr]
        field_value = "NULL" if row[field_name] is None else str(row[field_name])  # type: ignore[index]
        label = terminal.color("y", f"{field_name}:")
        value = terminal.color("g", field_value) if field_name == "answer" else field_value
        print(f"{label} {value}")
    print()
    terminal.y("← previous ID | → next ID | d delete | q quit")


def cycle_task_id(task_ids: list[int], current_uid: int, direction: int) -> int:
    """Return the previous or next existing ID, wrapping at either end."""

    if not task_ids:
        raise TaskDatabaseError("No task records are available for navigation.")
    if direction not in {-1, 1}:
        raise ValueError("Navigation direction must be -1 or 1.")
    try:
        current_index = task_ids.index(current_uid)
    except ValueError as error:
        raise TaskDatabaseError(f"Task record is no longer available: {current_uid}") from error
    return task_ids[(current_index + direction) % len(task_ids)]


def read_terminal_key() -> str:
    """Wait for a keypress, mapping arrow keys without requiring Enter."""

    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in {"\x00", "\xe0"}:
            key = msvcrt.getwch()
            return {"K": "left", "M": "right"}.get(key, "")
        return key.casefold()

    import termios
    import tty

    stdin = sys.stdin
    descriptor = stdin.fileno()
    original_settings = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        key = stdin.read(1)
        if key == "\x1b":
            key += stdin.read(2)
            return {"\x1b[D": "left", "\x1b[C": "right"}.get(key, "")
        return key.casefold()
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, original_settings)


def clear_record_screen() -> None:
    """Clear the interactive record view when ANSI is available."""

    if ansi_enabled(sys.stdout):
        print("\033[2J\033[H", end="", flush=True)
    else:
        print("\n" * 3, end="")


def confirm_task_delete(task_id: int, read_key: Callable[[], str] | None = None) -> bool:
    """Ask whether the current record should be deleted and return the answer."""

    Terminal().r(f"Delete task record {task_id}? (y/n)")
    key_reader = read_key or read_terminal_key
    while True:
        key = key_reader()
        if key == "y":
            return True
        if key in {"n", "q"}:
            return False


def browse_task_records(database_path: Path, start_uid: int) -> None:
    """Show records interactively until the user presses q."""

    task_ids = sorted(int(row["uid"]) for row in list_task_rows(database_path))
    current_uid = start_uid
    while True:
        row = get_task_row(database_path, current_uid)
        if row is None:
            raise TaskDatabaseError(f"Task record is no longer available: {current_uid}")
        clear_record_screen()
        render_task_record(row)
        key = read_terminal_key()
        if key == "q":
            return
        if key == "left":
            current_uid = cycle_task_id(task_ids, current_uid, -1)
        elif key == "right":
            current_uid = cycle_task_id(task_ids, current_uid, 1)
        elif key == "d" and confirm_task_delete(current_uid):
            current_index = task_ids.index(current_uid)
            if not delete_task(database_path, current_uid):
                raise TaskDatabaseError(f"Task record is no longer available: {current_uid}")
            task_ids.pop(current_index)
            if not task_ids:
                print("No task records remain.")
                return
            current_uid = task_ids[current_index % len(task_ids)]


def positive_task_id(value: str) -> int:
    """Parse one positive numeric task ID for the delete action."""

    try:
        task_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("ID must be a positive whole number.") from error
    if task_id < 1:
        raise argparse.ArgumentTypeError("ID must be a positive whole number.")
    return task_id


def star_count(value: str) -> int:
    """Parse a conventional zero-to-five star rating."""

    try:
        stars = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Stars must be a whole number from 0 to 5.") from error
    if not 0 <= stars <= 5:
        raise argparse.ArgumentTypeError("Stars must be a whole number from 0 to 5.")
    return stars


def resolve_create_path(value: str) -> Path:
    """Resolve a creation path, accepting the standard bare names in ``data``."""

    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.parent == Path(".") and candidate.name in {"tasks.db", "tasks.json"}:
        return PROJECT_ROOT / "data" / candidate.name
    return PROJECT_ROOT / candidate


def resolve_database_path(value: str | None) -> Path:
    """Resolve the selected task database, defaulting to ``data/tasks.db``.

    A bare file name is intentionally looked up next to the default database,
    making ``--merge db2.db`` refer to ``data/db2.db``.
    """

    if value is None:
        return PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.parent == Path("."):
        return PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH.parent / candidate
    return PROJECT_ROOT / candidate


def read_active_project_context() -> tuple[str, str]:
    """Read project and selector labels without creating project folders."""

    config = load_project_config(PROJECT_ROOT)
    configured_project = config.get("subdir")
    if not isinstance(configured_project, str) or not configured_project.strip():
        raise TaskDatabaseError("'subdir' must be non-empty text in project.json.")
    candidate = Path(configured_project)
    if candidate.is_absolute():
        raise TaskDatabaseError("'subdir' must be a relative path in project.json.")
    resolved_project = (PROJECT_ROOT / candidate).resolve()
    try:
        project_name = str(resolved_project.relative_to(PROJECT_ROOT.resolve()))
    except ValueError as error:
        raise TaskDatabaseError("'subdir' must point inside the repository.") from error
    selector = config.get("selector", "")
    if not isinstance(selector, str):
        raise TaskDatabaseError("'selector' must be text in project.json.")
    return project_name, selector


def get_active_project_directory() -> Path:
    """Resolve the active project directory configured in ``project.json``."""

    config = load_project_config(PROJECT_ROOT)
    configured_project = config.get("subdir")
    if not isinstance(configured_project, str) or not configured_project.strip():
        raise TaskDatabaseError("'subdir' must be non-empty text in project.json.")
    candidate = Path(configured_project)
    if candidate.is_absolute():
        raise TaskDatabaseError("'subdir' must be a relative path in project.json.")
    resolved_project = (PROJECT_ROOT / candidate).resolve()
    try:
        resolved_project.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise TaskDatabaseError("'subdir' must point inside the repository.") from error
    return resolved_project


def resolve_export_path(output: str | None) -> Path:
    """Use the active project for the default export, or an explicit output path."""

    if output is not None:
        return Path(output)
    return get_active_project_directory() / "answer.txt"


def parse_arguments() -> argparse.Namespace:
    """Parse database selection and one explicit database action."""

    parser = argparse.ArgumentParser(description="Create, inspect, or test local completed Ollama tasks.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--create",
        nargs=2,
        metavar=("DATABASE", "SCHEMA"),
        help="create DATABASE from SCHEMA JSON",
    )
    actions.add_argument("--list", "-l", action="store_true", help="list recorded tasks")
    actions.add_argument(
        "--add",
        "-a",
        nargs="?",
        const="",
        help="add a dummy test record, optionally with ANSWER text",
        metavar="ANSWER",
    )
    actions.add_argument(
        "--show",
        dest="show_uid",
        type=positive_task_id,
        metavar="ID",
        help="show one complete record by numeric ID",
    )
    actions.add_argument(
        "--delete",
        "-d",
        "--dele",
        dest="delete_uid",
        type=positive_task_id,
        metavar="ID",
        help="physically delete one record by numeric ID",
    )
    actions.add_argument(
        "--merge",
        "-m",
        dest="merge_database",
        metavar="DATABASE",
        help="append records from DATABASE, assigning them new IDs",
    )
    actions.add_argument(
        "--export",
        "-e",
        dest="export_uid",
        nargs="?",
        const=0,
        type=positive_task_id,
        metavar="ID",
        help="write one record's answer to the active project's answer.txt or --out FILE",
    )
    actions.add_argument(
        "--edit",
        nargs=2,
        metavar=("ID", "ANSWER"),
        help="replace one record's answer text",
    )
    actions.add_argument(
        "--setstar",
        "--set-star",
        dest="stars",
        type=star_count,
        metavar="STARS",
        help="set a zero-to-five star rating; requires --id ID",
    )
    parser.add_argument("--project", help="only list the exact project name")
    parser.add_argument("--sele", "--selector", dest="selector", help="only list the exact selector")
    parser.add_argument("--star", type=star_count, help="only list the exact zero-to-five star rating")
    parser.add_argument(
        "--id",
        "--ID",
        dest="task_id",
        type=positive_task_id,
        metavar="ID",
        help="task ID for --setstar or --export",
    )
    parser.add_argument("--out", dest="output", metavar="FILE", help="output file for --export")
    parser.add_argument(
        "database",
        nargs="?",
        metavar="DATABASE",
        help="task database; bare names are resolved in data/",
    )
    arguments = parser.parse_args()
    if arguments.edit is not None:
        try:
            arguments.edit_uid = positive_task_id(arguments.edit[0])
        except argparse.ArgumentTypeError as error:
            parser.error(str(error))
        arguments.edit_answer = arguments.edit[1]
    if arguments.create and arguments.database:
        parser.error("DATABASE cannot be used with --create")
    if arguments.stars is not None and arguments.task_id is None:
        parser.error("--setstar requires --id ID")
    if arguments.export_uid == 0:
        if arguments.task_id is None:
            parser.error("--export requires ID or --id ID")
        arguments.export_uid = arguments.task_id
    elif arguments.export_uid is not None and arguments.task_id is not None:
        parser.error("provide the export ID only once")
    if arguments.task_id is not None and arguments.stars is None and arguments.export_uid is None:
        parser.error("--id is available only with --setstar or --export")
    if arguments.star is not None and not arguments.list:
        parser.error("--star is available only with --list")
    if arguments.output is not None and arguments.export_uid is None:
        parser.error("--out is available only with --export")
    return arguments


def main() -> int:
    """Run the selected database action."""

    arguments = parse_arguments()
    try:
        if arguments.create:
            database_name, schema_name = arguments.create
            database_path = resolve_create_path(database_name)
            schema_path = resolve_create_path(schema_name)
            create_database(database_path, schema_path)
            print(f"Database ready: {database_path.relative_to(PROJECT_ROOT)}")
            return 0

        database_path = resolve_database_path(arguments.database)
        if arguments.merge_database:
            source_path = resolve_database_path(arguments.merge_database)
            imported = merge_task_databases(
                database_path,
                source_path,
                PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
            )
            print(f"Merged {imported} task record(s) from {source_path}.")
            return 0

        if arguments.add is not None:
            project_name, selector = read_active_project_context()
            uid = add_dummy_task(
                database_path,
                PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
                project_name,
                selector,
                arguments.add,
            )
            print(f"Dummy task added: {uid}")
            return 0

        if arguments.edit is not None:
            if set_task_answer(database_path, arguments.edit_uid, arguments.edit_answer):
                print(f"Task {arguments.edit_uid} answer updated.")
                return 0
            print(f"No task record found: {arguments.edit_uid}")
            return 1

        if arguments.export_uid is not None:
            row = get_task_row(database_path, arguments.export_uid)
            if row is None:
                print(f"No task record found: {arguments.export_uid}")
                return 1
            answer = row["answer"]
            if not isinstance(answer, str):
                raise TaskDatabaseError(f"Task record {arguments.export_uid} has a non-text answer.")
            output_path = resolve_export_path(arguments.output)
            output_path.write_text(answer, encoding="utf-8")
            print(f"Answer exported: {output_path}")
            return 0

        if arguments.delete_uid is not None:
            if delete_task(database_path, arguments.delete_uid):
                print(f"Task deleted: {arguments.delete_uid}")
                return 0
            print(f"No task record found: {arguments.delete_uid}")
            return 1

        if arguments.show_uid is not None:
            row = get_task_row(database_path, arguments.show_uid)
            if row is None:
                print(f"No task record found: {arguments.show_uid}")
                return 1
            if sys.stdin.isatty() and sys.stdout.isatty():
                browse_task_records(database_path, arguments.show_uid)
            else:
                render_task_record(row)
            return 0

        if arguments.stars is not None:
            assert arguments.task_id is not None
            if set_task_stars(database_path, arguments.task_id, arguments.stars):
                print(f"Task {arguments.task_id} stars set to {arguments.stars}.")
                return 0
            print(f"No task record found: {arguments.task_id}")
            return 1

        rows = list_task_rows(database_path, arguments.project, arguments.selector, arguments.star)
        for index, line in enumerate(format_task_rows(rows)):
            if index == 0:
                Terminal().y(line)
            else:
                print(line)
        if not rows:
            print("No matching task records.")
        return 0
    except (OSError, TaskDatabaseError) as error:
        print(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

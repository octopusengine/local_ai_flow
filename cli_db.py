"""Create and inspect the local database of completed Ollama task outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

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
    set_task_stars,
)
from lib.wrapp_log import load_project_config
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent


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


def parse_arguments() -> argparse.Namespace:
    """Parse the explicit create command or the compact task list command."""

    parser = argparse.ArgumentParser(description="Create, inspect, or test local completed Ollama tasks.")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--create",
        nargs=2,
        metavar=("DATABASE", "SCHEMA"),
        help="create DATABASE from SCHEMA JSON",
    )
    actions.add_argument("--list", action="store_true", help="list recorded tasks")
    actions.add_argument("--add", action="store_true", help="add a minimal dummy test record")
    actions.add_argument(
        "--show",
        dest="show_uid",
        type=positive_task_id,
        metavar="ID",
        help="show one complete record by numeric ID",
    )
    actions.add_argument(
        "--delete",
        "--dele",
        dest="delete_uid",
        type=positive_task_id,
        metavar="ID",
        help="physically delete one record by numeric ID",
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
    parser.add_argument("--id", dest="task_id", type=positive_task_id, metavar="ID", help="task ID for --setstar")
    arguments = parser.parse_args()
    if arguments.stars is not None and arguments.task_id is None:
        parser.error("--setstar requires --id ID")
    if arguments.task_id is not None and arguments.stars is None:
        parser.error("--id is available only with --setstar")
    if arguments.star is not None and not arguments.list:
        parser.error("--star is available only with --list")
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

        database_path = PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH
        if arguments.add:
            project_name, selector = read_active_project_context()
            uid = add_dummy_task(
                database_path,
                PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
                project_name,
                selector,
            )
            print(f"Dummy task added: {uid}")
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
            terminal = Terminal()
            for field_name in row.keys():
                field_value = "NULL" if row[field_name] is None else str(row[field_name])
                label = terminal.color("y", f"{field_name}:")
                value = terminal.color("g", field_value) if field_name == "answer" else field_value
                print(f"{label} {value}")
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

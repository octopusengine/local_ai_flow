"""Create and inspect the local database of completed Ollama task outputs."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import html
import json
import os
from pathlib import Path
import re
import sys


from lib.wrapp_db import (
    DEFAULT_TASKS_DATABASE_PATH,
    DEFAULT_TASKS_SCHEMA_PATH,
    REQUIRED_COLUMNS,
    TaskDatabaseError,
    add_dummy_task,
    create_database,
    delete_task,
    export_task_rows,
    format_task_rows,
    get_task_table_structure,
    get_last_task_id,
    get_task_row,
    group_task_rows,
    list_task_rows,
    merge_task_databases,
    set_task_answer,
    set_task_stars,
    summarize_task_rows,
)
from lib.wrapp_log import load_project_config
from lib.wrapp_terminal import Terminal, ansi_enabled


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
TASKS_BASE_CONFIG_PATH = DATA_DIR / "tasks_base.json"
HTML_BLOCK_TAG_PATTERN = re.compile(r"</?(?:address|article|aside|blockquote|br|div|h[1-6]|li|ol|p|pre|section|ul)\b[^>]*>", re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r"<[^>]*>")
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
MARKDOWN_EMPHASIS_PATTERN = re.compile(r"(?<!\w)[*_](?=\S)(.+?)(?<=\S)[*_](?!\w)")
MARKDOWN_HEADING_PATTERN = re.compile(r"^(\s{0,3})#{1,6}\s+")
MARKDOWN_QUOTE_PATTERN = re.compile(r"^(\s{0,3})>\s?")
MARKDOWN_LIST_PATTERN = re.compile(r"^(\s*)(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s*)?")


def load_list_columns(config_path: Path | None = None) -> list[dict[str, object]]:
    """Load the configurable columns and widths for the compact task list."""

    config_path = config_path or TASKS_BASE_CONFIG_PATH
    try:
        configuration = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise TaskDatabaseError(f"Cannot read task list configuration {config_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise TaskDatabaseError(f"Task list configuration is not valid JSON: {config_path}: {error}") from error
    if not isinstance(configuration, dict) or configuration.get("version") != 1:
        raise TaskDatabaseError("Task list configuration requires version 1.")
    columns = configuration.get("columns")
    if not isinstance(columns, list) or not columns:
        raise TaskDatabaseError("Task list configuration requires a non-empty columns array.")

    configured_columns: list[dict[str, object]] = []
    fields: set[str] = set()
    for column in columns:
        if not isinstance(column, dict):
            raise TaskDatabaseError("Each task list column must be an object.")
        field = column.get("field")
        name = column.get("name")
        width = column.get("width")
        if not isinstance(field, str) or field not in REQUIRED_COLUMNS:
            raise TaskDatabaseError(f"Task list column has an unknown field: {field!r}")
        if field in fields:
            raise TaskDatabaseError(f"Task list column is duplicated: {field!r}")
        if not isinstance(name, str) or not name.strip():
            raise TaskDatabaseError("Each task list column name must be non-empty text.")
        if isinstance(width, bool) or not isinstance(width, int) or width < 3:
            raise TaskDatabaseError("Each task list column width must be a whole number of at least 3.")
        fields.add(field)
        configured_columns.append({"field": field, "name": name, "width": width})
    return configured_columns


def render_task_record(row: object) -> None:
    """Print one complete task record, repeating its ID after long content."""

    terminal = Terminal()
    for field_name in row.keys():  # type: ignore[union-attr]
        field_value = "NULL" if row[field_name] is None else str(row[field_name])  # type: ignore[index]
        label = terminal.color("y", f"{field_name}:")
        value = terminal.color("g", field_value) if field_name == "answer" else field_value
        print(f"{label} {value}")
    print()
    print(f"ID: {row['uid']}")  # type: ignore[index]
    terminal.y("← previous ID | → next ID | d delete | q quit")


def clear_answer_text(text: str) -> str:
    """Return answer text with common Markdown and HTML presentation removed."""

    plain_text = html.unescape(text)
    plain_text = HTML_BLOCK_TAG_PATTERN.sub("\n", plain_text)
    plain_text = HTML_TAG_PATTERN.sub("", plain_text)
    plain_text = MARKDOWN_LINK_PATTERN.sub(r"\1", plain_text)
    plain_text = plain_text.replace("```", "").replace("**", "").replace("__", "")
    plain_text = plain_text.replace("~~", "").replace("`", "")
    plain_text = MARKDOWN_EMPHASIS_PATTERN.sub(r"\1", plain_text)
    lines = []
    for line in plain_text.splitlines():
        line = MARKDOWN_HEADING_PATTERN.sub(r"\1", line)
        line = MARKDOWN_QUOTE_PATTERN.sub(r"\1", line)
        lines.append(MARKDOWN_LIST_PATTERN.sub(r"\1", line))
    return "\n".join(lines).strip()


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
    """Resolve a creation path, accepting the standard bare database and schema names."""

    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.parent == Path(".") and candidate.name == "tasks.db":
        return PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH
    if candidate.parent == Path(".") and candidate.name == "tasks.json":
        return PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH
    return PROJECT_ROOT / candidate


def resolve_database_path(value: str | None) -> Path:
    """Resolve the selected task database, defaulting to ``data/tasks.db``.

    A bare file name is intentionally looked up next to the default database,
    making ``--merge-db db2.db`` refer to ``data/db2.db``.
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


def resolve_export_path(output: str | None, default_filename: str) -> Path:
    """Resolve an export filename directly inside the active project directory."""

    filename = output or default_filename
    candidate = Path(filename)
    if candidate.name != filename or filename in {"", ".", ".."}:
        raise TaskDatabaseError("The export filename must be directly inside the active project directory.")
    return get_active_project_directory() / candidate


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
        "--stru",
        "--structure",
        dest="structure",
        action="store_true",
        help="show the current tasks table field names and SQLite types",
    )
    actions.add_argument(
        "--group",
        dest="group_field",
        metavar="FIELD",
        help="show record counts grouped by a tasks table field, or by monthly (RRMM)",
    )
    actions.add_argument(
        "--sum",
        dest="summary",
        action="store_true",
        help="show coarse record, project, and Ollama token totals",
    )
    actions.add_argument(
        "--last",
        dest="last",
        action="store_true",
        help="write the highest current task ID to standard output",
    )
    actions.add_argument(
        "--add",
        "-a",
        nargs="?",
        const="",
        help="add a dummy test record, optionally with ANSWER text",
        metavar="ANSWER",
    )
    actions.add_argument(
        "--add-id",
        nargs=2,
        metavar=("ID", "ANSWER"),
        help="add a dummy test record at an unused positive ID with ANSWER text",
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
        nargs="?",
        const=0,
        type=positive_task_id,
        metavar="ID",
        help="delete ID, or with --selector preview and confirm deletion of matching records",
    )
    actions.add_argument(
        "--merge-db",
        dest="merge_database",
        metavar="DATABASE",
        help="append records from DATABASE, assigning them new IDs",
    )
    actions.add_argument(
        "--clone-stars",
        dest="clone_stars",
        metavar="NAME.db",
        help="create NAME.db containing every record with stars > 0",
    )
    actions.add_argument(
        "--clone",
        dest="clone",
        metavar="NAME.db",
        help="with --selector SELECTOR, create NAME.db containing matching records",
    )
    actions.add_argument(
        "-e",
        "-exp",
        dest="answer_export",
        nargs="*",
        metavar="ID [RESULT.txt]",
        help="write one record's answer to optional RESULT.txt (default: export.txt)",
    )
    actions.add_argument(
        "-E",
        dest="answer_print_uid",
        type=positive_task_id,
        metavar="ID",
        help="write one record's answer only to standard output",
    )
    actions.add_argument(
        "--export",
        dest="record_export",
        nargs="*",
        metavar="ID [RESULT.json]",
        help="write one complete record as JSON to optional RESULT.json (default: export.json)",
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
    parser.add_argument("--sele", "--selector", dest="selector", help="filter records to the exact selector")
    parser.add_argument("--star", type=star_count, help="only list the exact zero-to-five star rating")
    parser.add_argument("--model", help="only list models containing this text (case-insensitive)")
    parser.add_argument("--db", dest="source_database", metavar="DATABASE", help="use DATABASE from data/ instead of tasks.db")
    parser.add_argument(
        "--id",
        "--ID",
        dest="task_id",
        type=positive_task_id,
        metavar="ID",
        help="task ID for --setstar, -e/-exp, or --export",
    )
    parser.add_argument("--out", dest="output", metavar="FILE", help="legacy output file for -e/-exp or --export")
    parser.add_argument(
        "--clear",
        dest="clear_answer",
        action="store_true",
        help="remove common Markdown and HTML formatting from -E output",
    )
    parser.add_argument(
        "--newline",
        dest="answer_print_newline",
        action="store_true",
        help="append one trailing newline to -E output for terminal display",
    )
    parser.add_argument(
        "database",
        nargs="?",
        metavar="DATABASE",
        help="task database; with --list, create this filtered database in data/",
    )
    arguments = parser.parse_args()
    if arguments.edit is not None:
        try:
            arguments.edit_uid = positive_task_id(arguments.edit[0])
        except argparse.ArgumentTypeError as error:
            parser.error(str(error))
        arguments.edit_answer = arguments.edit[1]
    arguments.add_id_uid = None
    arguments.add_id_answer = None
    if arguments.add_id is not None:
        try:
            arguments.add_id_uid = positive_task_id(arguments.add_id[0])
        except argparse.ArgumentTypeError as error:
            parser.error(str(error))
        arguments.add_id_answer = arguments.add_id[1]
    if arguments.create and arguments.database:
        parser.error("DATABASE cannot be used with --create")
    if arguments.create and arguments.source_database:
        parser.error("--db cannot be used with --create")
    if arguments.clone_stars and arguments.database:
        parser.error("DATABASE cannot be used with --clone-stars")
    if arguments.clone and arguments.database:
        parser.error("DATABASE cannot be used with --clone")
    if arguments.clone and (not isinstance(arguments.selector, str) or not arguments.selector.strip()):
        parser.error("--clone requires --selector SELECTOR")
    if arguments.delete_uid == 0 and (not isinstance(arguments.selector, str) or not arguments.selector.strip()):
        parser.error("--delete without ID requires --selector SELECTOR")
    if not arguments.list and arguments.database and arguments.source_database:
        parser.error("provide the working database only once")
    if arguments.stars is not None and arguments.task_id is None:
        parser.error("--setstar requires --id ID")
    arguments.answer_export_uid = None
    arguments.answer_export_filename = None
    arguments.export_uid = None
    arguments.export_filename = None
    for values, uid_name, filename_name, option_name, default_filename in (
        (arguments.answer_export, "answer_export_uid", "answer_export_filename", "-e/-exp", "export.txt"),
        (arguments.record_export, "export_uid", "export_filename", "--export", "export.json"),
    ):
        if values is None:
            continue
        if len(values) > 2:
            parser.error(f"{option_name} requires ID and accepts an optional output filename")
        if not values:
            if arguments.task_id is None:
                parser.error(f"{option_name} requires ID or --id ID")
            uid = arguments.task_id
        else:
            try:
                uid = positive_task_id(values[0])
            except argparse.ArgumentTypeError as error:
                parser.error(str(error))
            if arguments.task_id is not None:
                parser.error("provide the export ID only once")
        if len(values) == 2 and arguments.output is not None:
            parser.error("provide the output filename only once")
        setattr(arguments, uid_name, uid)
        setattr(arguments, filename_name, values[1] if len(values) == 2 else arguments.output or default_filename)
    if arguments.task_id is not None and arguments.stars is None and arguments.answer_export_uid is None and arguments.export_uid is None:
        parser.error("--id is available only with --setstar, -e/-exp, or --export")
    if arguments.star is not None and not arguments.list:
        parser.error("--star is available only with --list")
    if arguments.model is not None and not arguments.list:
        parser.error("--model is available only with --list")
    if arguments.output is not None and arguments.answer_export_uid is None and arguments.export_uid is None:
        parser.error("--out is available only with -e/-exp or --export")
    if arguments.clear_answer and arguments.answer_print_uid is None:
        parser.error("--clear is available only with -E ID")
    if arguments.answer_print_newline and arguments.answer_print_uid is None:
        parser.error("--newline is available only with -E ID")
    arguments.list_output_database = arguments.database if arguments.list else None
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

        selected_database = arguments.source_database or (None if arguments.list_output_database else arguments.database)
        database_path = resolve_database_path(selected_database)
        if arguments.merge_database:
            source_path = resolve_database_path(arguments.merge_database)
            imported = merge_task_databases(
                database_path,
                source_path,
                PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
            )
            print(f"Merged {imported} task record(s) from {source_path}.")
            return 0

        if arguments.clone_stars:
            destination_path = resolve_create_path(arguments.clone_stars)
            rows = list_task_rows(database_path)
            starred_rows = [row for row in rows if row["stars"] is not None and row["stars"] > 0]
            exported = export_task_rows(destination_path, PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH, starred_rows)
            print(
                f"Cloned {exported} starred record(s) from {database_path.relative_to(PROJECT_ROOT)} "
                f"to {destination_path.relative_to(PROJECT_ROOT)}."
            )
            return 0

        if arguments.clone:
            destination_path = resolve_create_path(arguments.clone)
            rows = list_task_rows(database_path, selector=arguments.selector)
            exported = export_task_rows(destination_path, PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH, rows)
            print(
                f"Cloned {exported} record(s) with selector {arguments.selector!r} "
                f"from {database_path.relative_to(PROJECT_ROOT)} "
                f"to {destination_path.relative_to(PROJECT_ROOT)}."
            )
            return 0

        if arguments.structure:
            for field_name, field_type in get_task_table_structure(database_path):
                print(f"{field_name}: {field_type}")
            return 0

        if arguments.group_field is not None:
            groups = group_task_rows(database_path, arguments.group_field)
            print(f"{'count':>7}  {arguments.group_field}")
            for row in groups:
                value = "NULL" if row["field_value"] is None else str(row["field_value"])
                print(f"{int(row['record_count']):>7}  {value}")
            return 0

        if arguments.summary:
            summary = summarize_task_rows(database_path)
            print(f"Total records: {summary['record_count']}")
            print(f"Projects: {summary['project_count']}")
            print(f"eval_count: {summary['eval_count']}")
            print(f"prompt_eval_count: {summary['prompt_eval_count']}")
            print(f"response_chunks: {summary['response_chunks']}")
            print(f"duration: {summary['duration_seconds']:.1f} s")
            return 0

        if arguments.last:
            last_uid = get_last_task_id(database_path)
            if last_uid is None:
                print("No task records found.")
                return 1
            print(last_uid)
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

        if arguments.add_id is not None:
            project_name, selector = read_active_project_context()
            uid = add_dummy_task(
                database_path,
                PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
                project_name,
                selector,
                arguments.add_id_answer,
                uid=arguments.add_id_uid,
            )
            print(f"Dummy task added at requested ID: {uid}")
            return 0

        if arguments.edit is not None:
            if set_task_answer(database_path, arguments.edit_uid, arguments.edit_answer):
                print(f"Task {arguments.edit_uid} answer updated.")
                return 0
            print(f"No task record found: {arguments.edit_uid}")
            return 1

        if arguments.answer_export_uid is not None:
            row = get_task_row(database_path, arguments.answer_export_uid)
            if row is None:
                print(f"No task record found: {arguments.answer_export_uid}")
                return 1
            answer = row["answer"]
            if not isinstance(answer, str):
                raise TaskDatabaseError(f"Task record {arguments.answer_export_uid} has a non-text answer.")
            output_path = resolve_export_path(arguments.answer_export_filename, "export.txt")
            output_path.write_text(answer, encoding="utf-8")
            print(f"Answer exported: {output_path}")
            return 0

        if arguments.answer_print_uid is not None:
            row = get_task_row(database_path, arguments.answer_print_uid)
            if row is None:
                print(f"No task record found: {arguments.answer_print_uid}")
                return 1
            answer = row["answer"]
            if not isinstance(answer, str):
                raise TaskDatabaseError(f"Task record {arguments.answer_print_uid} has a non-text answer.")
            if arguments.clear_answer:
                answer = clear_answer_text(answer)
            sys.stdout.write(answer)
            if arguments.answer_print_newline and not answer.endswith("\n"):
                sys.stdout.write("\n")
            return 0

        if arguments.export_uid is not None:
            row = get_task_row(database_path, arguments.export_uid)
            if row is None:
                print(f"No task record found: {arguments.export_uid}")
                return 1
            output_path = resolve_export_path(arguments.export_filename, "export.json")
            output_path.write_text(json.dumps(dict(row), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Task record exported: {output_path}")
            return 0

        if arguments.delete_uid == 0:
            rows = list_task_rows(database_path, selector=arguments.selector)
            for index, line in enumerate(format_task_rows(rows, load_list_columns())):
                if index == 0:
                    Terminal().y(line)
                else:
                    print(line)
            if not rows:
                print(f"No task records found for selector {arguments.selector!r}.")
                return 0
            confirmation = input(
                f"Delete these {len(rows)} record(s) with selector {arguments.selector!r}? Type yes to confirm: "
            )
            if confirmation.strip().casefold() != "yes":
                print("Deletion cancelled; no records were deleted.")
                return 0
            deleted = sum(delete_task(database_path, int(row["uid"])) for row in rows)
            print(f"Deleted {deleted} record(s) with selector {arguments.selector!r}.")
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

        rows = list_task_rows(database_path, arguments.project, arguments.selector, arguments.star, arguments.model)
        if arguments.list_output_database:
            output_database_path = resolve_database_path(arguments.list_output_database)
            exported = export_task_rows(output_database_path, PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH, rows)
            print(f"Filtered task database created: {output_database_path} ({exported} record(s)).")
        for index, line in enumerate(format_task_rows(rows, load_list_columns())):
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

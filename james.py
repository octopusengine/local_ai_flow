"""Small cross-platform terminal menu for the local Ollama tools.

Run with ``python james.py``.  The menu reacts to single key presses, so
neither Windows nor Linux needs a shell-specific launcher.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from lib.wrapp_db import delete_task, list_task_rows, set_task_stars, short_text
from lib.wrapp_terminal import Terminal, ansi_enabled, hide_cursor, show_cursor


PROJECT_ROOT = Path(__file__).resolve().parent
JAMES_CONFIG_PATH = PROJECT_ROOT / "james.json"
SC_COMMAND_CATALOG_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc.json"
JAMES_VERSION = "0.2.1"
DATABASE_SCRIPT_PATH = PROJECT_ROOT / "cli_db.py"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "runner.py"
SPEECH_SCRIPT_PATH = PROJECT_ROOT / "cli_speech.py"
MENU_INDENT = " " * 7
CHAT_FLOW_NAME_TEMPLATE = "flow_chat_{language}.json"
CHAT_CONTEXT_FILENAME = "chat_context.txt"
CHAT_REPLY_FILENAME = "chat_reply.txt"
CHAT_INPUT_FILENAME = "chat_input.txt"
CHAT_INITIAL_CONTEXT = "- context:\n  No previous conversation.\n"
SUPPORTED_LANGUAGES = ("cz", "en", "es")
JAMES_ART = (
    "    ...       ...      ..       .      ...        ...    ",
    "  ████|#=-  █████=-   ██|-     █|=-- █████=--   ██████|_ (@)",
    "    ██|=-- ██    █|-- ███     ██|==--    ██|-- ██  █     ",
    "    ██|-   ███████|-  ██ ██  █ █|=-- | ███#=--- ██████|=-- ",
    "██  ██| *  ██    █| . ██   █|  █|--      ██|-- .   █  █|---",
    " █████--   ██    █|   ██       █|-   █████- .   ██████- . ",
)


def load_james_config() -> dict[str, Any]:
    """Load and validate the small menu configuration."""

    try:
        data = json.loads(JAMES_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Configuration is missing: {JAMES_CONFIG_PATH.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {JAMES_CONFIG_PATH.name}: {error}") from error

    if not isinstance(data, dict) or data.get("json_version") != "1":
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires an object with 'json_version': '1'.")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'name'.")
    width = data.get("width")
    if isinstance(width, bool) or not isinstance(width, int) or width < 10:
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires an integer 'width' of at least 10.")
    max_list_rows = data.get("max_list_rows")
    if isinstance(max_list_rows, bool) or not isinstance(max_list_rows, int) or max_list_rows < 1:
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires 'max_list_rows' as an integer of at least 1.")
    if data.get("language") not in SUPPORTED_LANGUAGES:
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires 'language': cz, en, or es.")
    if not isinstance(data.get("chat_model"), str) or not data["chat_model"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'chat_model'.")
    context_turns = data.get("chat_context_turns")
    if isinstance(context_turns, bool) or not isinstance(context_turns, int) or context_turns < 1:
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires 'chat_context_turns' as an integer of at least 1.")
    if not isinstance(data.get("main_db"), str) or not data["main_db"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'main_db'.")
    for key in ("best_flows", "best_mcp_flows"):
        flow_list = data.get(key)
        if not isinstance(flow_list, list) or not 1 <= len(flow_list) <= 9:
            raise ValueError(f"{JAMES_CONFIG_PATH.name} requires one to nine '{key}' entries.")
        for flow in flow_list:
            if not isinstance(flow, str) or not flow.strip() or Path(flow).name != flow:
                raise ValueError(f"Each '{key}' entry must be a non-empty flow filename.")
    if not isinstance(data.get("project_config"), str) or not data["project_config"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'project_config'.")
    return data


def save_james_config(config: dict[str, Any]) -> None:
    """Save James's own small configuration without changing its layout style."""

    JAMES_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main_database_path(config: dict[str, Any]) -> str:
    """Return the configured database path after keeping it inside this project."""

    candidate = Path(str(config["main_db"]))
    if candidate.is_absolute():
        raise ValueError("'main_db' must be relative to the project root.")
    resolved = (PROJECT_ROOT / candidate).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("'main_db' must stay inside the project root.") from error
    return candidate.as_posix()


def main_database_file(config: dict[str, Any]) -> Path:
    """Resolve the configured database into an absolute local path."""

    return (PROJECT_ROOT / main_database_path(config)).resolve()


def project_config_path(config: dict[str, Any]) -> Path:
    """Resolve the configured project file while keeping it in this project."""

    candidate = Path(str(config["project_config"]))
    if candidate.is_absolute() or candidate.parent != Path("."):
        raise ValueError("'project_config' must name a file in the project root.")
    return PROJECT_ROOT / candidate


def load_project_config(config: dict[str, Any]) -> dict[str, Any]:
    """Read the project configuration that is shared by the CLI tools."""

    path = project_config_path(config)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Project configuration is missing: {path.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path.name}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return data


def save_project_config(config: dict[str, Any], project_data: dict[str, Any]) -> None:
    """Save the shared project configuration in a readable form."""

    path = project_config_path(config)
    path.write_text(json.dumps(project_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_key() -> str:
    """Read one key without Enter on Windows and Linux."""

    try:
        hide_cursor()
        if os.name == "nt":
            import msvcrt

            key = msvcrt.getwch()
            if key in {"\x00", "\xe0"}:
                special_key = msvcrt.getwch()
                return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(special_key, "")
            return key.casefold()

        import select
        import termios
        import tty

        if not sys.stdin.isatty():
            raise RuntimeError("James requires an interactive terminal.")
        descriptor = sys.stdin.fileno()
        original_settings = termios.tcgetattr(descriptor)
        try:
            tty.setraw(descriptor)
            first_byte = os.read(descriptor, 1)
            if first_byte != b"\x1b":
                return first_byte.decode("utf-8", errors="ignore").casefold()

            sequence = first_byte
            while len(sequence) < 6:
                readable, _unused_write, _unused_error = select.select([descriptor], [], [], 0.05)
                if not readable:
                    break
                sequence += os.read(descriptor, 1)
                if sequence in {b"\x1b[A", b"\x1bOA"}:
                    return "up"
                if sequence in {b"\x1b[B", b"\x1bOB"}:
                    return "down"
                if sequence in {b"\x1b[D", b"\x1bOD"}:
                    return "left"
                if sequence in {b"\x1b[C", b"\x1bOC"}:
                    return "right"
            return "\x1b" if sequence == b"\x1b" else ""
        finally:
            termios.tcsetattr(descriptor, termios.TCSADRAIN, original_settings)
    finally:
        show_cursor()


def clear_screen() -> None:
    """Clear the menu when terminal control codes are available."""

    if ansi_enabled(sys.stdout):
        print("\033[2J\033[H", end="", flush=True)
    else:
        print("\n" * 2, end="")


def pause(message: str = "Press any key to return to the menu.") -> None:
    """Show a short message and wait for one key."""

    Terminal().y(message)
    read_key()


def render_back_footer(width: int) -> None:
    """Draw the standard submenu return line below its bottom separator."""

    terminal = Terminal()
    print("-" * width)
    print(f"{MENU_INDENT}{terminal.style('b', fg='yellow', bold=True)}ack or ← left arrow")


def wait_for_back(width: int) -> None:
    """Wait until the user returns from a detail screen with Back or Left."""

    render_back_footer(width)
    while read_key() not in {"b", "left"}:
        pass


def render_menu_label(label: str, key: str, width: int | None = None) -> str:
    """Format a menu label, highlighting its shortcut when it is in the name."""

    terminal = Terminal()
    index = label.casefold().find(key.casefold())
    padded_label = label if width is None else label.ljust(width)
    if index < 0:
        return padded_label
    return f"{padded_label[:index]}{terminal.style(label[index], fg='yellow', bold=True)}{padded_label[index + 1:]}"


def render_item(label: str, key: str) -> str:
    """Format one indented menu item."""

    return f"{MENU_INDENT}{render_menu_label(label, key)}"


def render_main_menu(config: dict[str, Any]) -> None:
    """Draw the first level of the menu."""

    terminal = Terminal()
    clear_screen()
    try:
        project_name = str(load_project_config(config).get("subdir", "not set"))
    except ValueError:
        project_name = "not set"
    separator = "-" * int(config["width"])
    art_width = max(len(line.rstrip()) for line in JAMES_ART)
    for line in JAMES_ART:
        rendered_line = line.rstrip().ljust(art_width)
        print(terminal.style(rendered_line.center(int(config["width"])), fg="green", bold=True))
    print(separator)
    print(f"{config['name']} - ver. {JAMES_VERSION}")
    print(f"actual project: {terminal.color('yellow', project_name)}")
    print(separator)
    print()
    main_menu_rows = (
        (("project", "p"), ("camera", "c")),
        (("flow", "f"), ("voice", "v")),
        (("database", "d"), ("chat", "t")),
        (("setup", "s"), ("cowork", "w")),
        (("help", "h"), ("mcp", "m")),
    )
    for left, right in main_menu_rows:
        line = render_menu_label(*left, width=14)
        if right is not None:
            line += render_menu_label(*right)
        print(f"{MENU_INDENT}{line}")
    print()
    print(separator)
    print(f"{MENU_INDENT}{terminal.style('q', fg='yellow', bold=True)} = quit")


def render_project_menu(config: dict[str, Any]) -> None:
    """Draw the second level for the active project configuration."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    clear_screen()
    print(separator)
    print(terminal.style("PROJECT", fg="bright_white", bold=True))
    try:
        project_data = load_project_config(config)
        directory = project_data.get("subdir", "not set")
        print(f"{terminal.color('bright_black', 'directory:')} {directory}")
    except ValueError as error:
        terminal.r(f"Cannot load configuration: {error}")
    print(separator)
    print()
    print(render_item("show", "s"))
    print(render_item("dir_name", "d"))
    print()
    render_back_footer(int(config["width"]))


def show_project_config(config: dict[str, Any]) -> None:
    """Display the complete shared project JSON."""

    clear_screen()
    path = project_config_path(config)
    width = int(config["width"])
    print("-" * width)
    print(Terminal().style(path.name, fg="bright_white", bold=True))
    print("-" * width)
    print()
    print(json.dumps(load_project_config(config), ensure_ascii=False, indent=2))
    wait_for_back(width)


def validate_directory_name(value: str) -> str:
    """Validate a relative directory name without creating it yet."""

    name = value.strip()
    if not name:
        raise ValueError("Directory name cannot be empty.")
    candidate = Path(name)
    if candidate.is_absolute():
        raise ValueError("Directory must be relative to the project root.")
    resolved = (PROJECT_ROOT / candidate).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("Directory must stay inside the project root.") from error
    return candidate.as_posix()


def change_directory_name(config: dict[str, Any]) -> None:
    """Ask for and persist the ``subdir`` setting used by the CLI tools."""

    clear_screen()
    project_data = load_project_config(config)
    current = project_data.get("subdir", "")
    terminal = Terminal()
    separator = "-" * int(config["width"])
    print(separator)
    print(terminal.style("PROJECT · dir_name", fg="bright_white", bold=True))
    print(separator)
    print(f"Current value: {terminal.color('cyan', current)}")
    print("Enter a relative directory name; empty input cancels the change.")
    value = input("New dir_name: ").strip()
    if not value:
        return
    project_data["subdir"] = validate_directory_name(value)
    save_project_config(config, project_data)
    terminal.g(f"Saved to {project_config_path(config).name}: subdir = {project_data['subdir']}")
    wait_for_back(int(config["width"]))


def project_menu(config: dict[str, Any]) -> None:
    """Handle the project submenu until the user returns to the main menu."""

    while True:
        render_project_menu(config)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "s":
            try:
                show_project_config(config)
            except ValueError as error:
                Terminal().r(f"Error: {error}")
                pause()


def render_setup_menu(config: dict[str, Any]) -> None:
    """Draw the small setup section."""

    terminal = Terminal()
    width = int(config["width"])
    clear_screen()
    print("-" * width)
    print(terminal.style("SETUP", fg="bright_white", bold=True))
    print(f"language: {terminal.color('yellow', config['language'])}")
    print("-" * width)
    print()
    print(render_item("language", "l"))
    print()
    render_back_footer(width)


def render_language_picker(config: dict[str, Any], selected_index: int) -> None:
    """Draw the language selector used from Setup."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("cz · Czech", "en · English", "es · Spanish")
    clear_screen()
    print("-" * width)
    print(terminal.style("SETUP · LANGUAGE", fg="bright_white", bold=True))
    print(f"Current: {terminal.color('yellow', config['language'])}")
    print("-" * width)
    print()
    for index, label in enumerate(labels):
        prefix = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{prefix}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter save")
    render_back_footer(width)


def language_menu(config: dict[str, Any]) -> None:
    """Select and persist the default language."""

    selected_index = SUPPORTED_LANGUAGES.index(str(config["language"]))
    while True:
        render_language_picker(config, selected_index)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(SUPPORTED_LANGUAGES) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            config["language"] = SUPPORTED_LANGUAGES[selected_index]
            save_james_config(config)
            Terminal().g(f"Language saved: {config['language']}")
            pause()
            return


def setup_menu(config: dict[str, Any]) -> None:
    """Handle James setup options."""

    while True:
        render_setup_menu(config)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "l":
            language_menu(config)
        elif key == "d":
            try:
                change_directory_name(config)
            except ValueError as error:
                Terminal().r(f"Error: {error}")
                pause()


def run_tool(script_name: str) -> None:
    """Run one existing CLI tool with the current Python interpreter."""

    script_path = PROJECT_ROOT / script_name
    if not script_path.is_file():
        raise ValueError(f"Tool not found: {script_name}")
    clear_screen()
    Terminal().c(f"Starting {script_name}…")
    result = subprocess.run([sys.executable, str(script_path)], cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        Terminal().r(f"Tool exited with code {result.returncode}.")
    else:
        Terminal().g("Done.")
    pause()


def show_mock(config: dict[str, Any], label: str) -> None:
    """Give unfinished menu sections a useful, non-destructive placeholder."""

    clear_screen()
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style(label.upper(), fg="bright_white", bold=True))
    print("-" * width)
    print()
    terminal.y("This section is a placeholder; its content will be added later.")
    wait_for_back(width)


def database_command(config: dict[str, Any], arguments: list[str]) -> list[str]:
    """Build one cli_db.py invocation against the configured main database."""

    if not DATABASE_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {DATABASE_SCRIPT_PATH.name}")
    return [sys.executable, str(DATABASE_SCRIPT_PATH), *arguments, "--db", main_database_path(config)]


def read_database_summary(config: dict[str, Any]) -> list[str]:
    """Run the database summary quietly so it can become the menu header."""

    result = subprocess.run(
        database_command(config, ["--sum"]),
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout if result.returncode == 0 else result.stderr or result.stdout).strip()
    if not output:
        output = f"Database summary failed (exit code {result.returncode})."
    return output.splitlines()


def render_database_menu(config: dict[str, Any]) -> None:
    """Draw the database menu with the live cli_db.py summary."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    clear_screen()
    print(separator)
    print(terminal.style("DATABASE", fg="bright_white", bold=True))
    print(terminal.color("bright_black", "python .\\cli_db.py --sum"))
    for line in read_database_summary(config):
        print(line)
    print(separator)
    print(render_item("list", "l"))
    print(render_item("group", "g"))
    print(render_item("show ID", "s"))
    print(render_item("delete ID", "d"))
    print(render_item("rating 3", "r"))
    print(render_item("filter", "f"))
    render_back_footer(int(config["width"]))


def read_task_id(action: str) -> int | None:
    """Ask for a positive database record ID, or return None on blank input."""

    while True:
        value = input(f"Task ID to {action} (empty = cancel): ").strip()
        if not value:
            return None
        try:
            task_id = int(value)
        except ValueError:
            Terminal().r("Task ID must be a positive whole number.")
            continue
        if task_id < 1:
            Terminal().r("Task ID must be a positive whole number.")
            continue
        return task_id


def run_database_action(config: dict[str, Any], arguments: list[str]) -> None:
    """Run one database command visibly, then return to the database menu."""

    clear_screen()
    result = subprocess.run(database_command(config, arguments), cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        Terminal().r(f"Database command exited with code {result.returncode}.")
    else:
        Terminal().g("Done.")
    pause()


def render_database_group_picker(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled choice of database grouping."""

    terminal = Terminal()
    width = int(config["width"])
    separator = "-" * width
    labels = ("project", "selector", "monthly")
    clear_screen()
    print(separator)
    print(terminal.style("GROUP", fg="bright_white", bold=True))
    print(separator)
    print()
    for index, label in enumerate(labels):
        prefix = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{prefix}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def database_group_menu(config: dict[str, Any]) -> None:
    """Choose how the task records are grouped before running the report."""

    group_fields = ("project", "selector", "monthly")
    selected_index = 0
    while True:
        render_database_group_picker(config, selected_index)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(group_fields) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            run_database_action(config, ["--group", group_fields[selected_index]])
            return


def render_database_record(rows: list[Any], selected_index: int, width: int) -> int:
    """Show complete records and allow previous/next navigation in the current list."""

    terminal = Terminal()
    while True:
        row = rows[selected_index]
        separator = "-" * width
        clear_screen()
        print(separator)
        print(terminal.style(f"DATABASE RECORD #{row['uid']}", fg="bright_white", bold=True))
        print(f"Record {selected_index + 1} of {len(rows)}")
        print(separator)
        for field_name in row.keys():
            value = "NULL" if row[field_name] is None else str(row[field_name])
            print(f"{terminal.color('yellow', f'{field_name}:')} {value}")
        print(f"{terminal.color('yellow', 'UID:')} {row['uid']}")
        print(separator)
        print(
            f"{MENU_INDENT}{terminal.style('p', fg='yellow', bold=True)}rev ←  | "
            f"{terminal.style('n', fg='yellow', bold=True)}ext →"
        )
        print(separator)
        print(f"{MENU_INDENT}{terminal.style('b', fg='yellow', bold=True)}ack")
        key = read_key()
        if key == "b":
            return selected_index
        if key in {"n", "right"}:
            selected_index = max(0, selected_index - 1)
        elif key in {"p", "left"}:
            selected_index = min(len(rows) - 1, selected_index + 1)


def speak_database_answer(row: Any, language: str) -> None:
    """Speak the selected answer in one supported language without a text file."""

    if not SPEECH_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {SPEECH_SCRIPT_PATH.name}")
    language_options = {"cz": "--cz", "en": "--en", "es": "--es"}
    if language not in language_options:
        raise ValueError(f"Unsupported speech language: {language}")
    answer = row["answer"]
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("The selected record has no text answer to speak.")
    clear_screen()
    Terminal().c(f"Speaking {language} answer for task ID {row['uid']}…")
    result = subprocess.run(
        [sys.executable, str(SPEECH_SCRIPT_PATH), language_options[language], "-"],
        cwd=PROJECT_ROOT,
        check=False,
        input=answer,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print()
    if result.returncode:
        Terminal().r(f"Speech command exited with code {result.returncode}.")
    else:
        Terminal().g("Done.")
    pause()


def read_star_rating() -> int | None:
    """Ask for a zero-to-five rating, or return None on blank input."""

    while True:
        value = input("New rating 0-5 (empty = cancel): ").strip()
        if not value:
            return None
        try:
            rating = int(value)
        except ValueError:
            Terminal().r("Rating must be a whole number from 0 to 5.")
            continue
        if not 0 <= rating <= 5:
            Terminal().r("Rating must be a whole number from 0 to 5.")
            continue
        return rating


def browser_window_start(selected_index: int, row_count: int, max_list_rows: int) -> int:
    """Keep the selected database row near the centre of the visible window."""

    maximum_start = max(0, row_count - max_list_rows)
    return min(max(0, selected_index - max_list_rows // 2), maximum_start)


def render_database_browser(
    rows: list[Any], selected_index: int, width: int, max_list_rows: int, filter_label: str | None = None
) -> None:
    """Draw a compact, keyboard-navigable page of task records."""

    terminal = Terminal()
    separator = "-" * width
    clear_screen()
    print(separator)
    print(terminal.style("DATABASE LIST", fg="bright_white", bold=True))
    print(f"Record {selected_index + 1} of {len(rows)}")
    if filter_label is not None:
        print(f"Filter: {terminal.color('yellow', filter_label)}")
    print(separator)
    print("  ID    PROJECT      TASK            ANSWER                ★")
    start = browser_window_start(selected_index, len(rows), max_list_rows)
    end = min(start + max_list_rows, len(rows))
    for index in range(start, end):
        row = rows[index]
        marker = ">" if index == selected_index else " "
        line = (
            f"{marker} {int(row['uid']):>4}  "
            f"{short_text(row['project'], 11):<11} "
            f"{short_text(row['task'], 15):<15} "
            f"{short_text(row['answer'], 21):<21} "
            f"{row['stars']}"
        )
        print(terminal.style(line, fg="yellow", bold=True) if index == selected_index else line)
    print(
        f"{MENU_INDENT}↑/↓ move   Enter/s show   "
        f"{terminal.style('c', fg='yellow', bold=True)} Czech   "
        f"{terminal.style('a', fg='yellow', bold=True)} English   "
        f"{terminal.style('e', fg='yellow', bold=True)} Spanish"
    )
    print(
        f"{MENU_INDENT}{terminal.style('r', fg='yellow', bold=True)} rating   "
        f"{terminal.style('d', fg='yellow', bold=True)} delete"
    )
    render_back_footer(width)


def browse_database_records(
    config: dict[str, Any], filter_field: str | None = None, filter_value: str | int | None = None
) -> None:
    """Browse main-database rows and apply actions to the selected record."""

    database_path = main_database_file(config)
    filters = {filter_field: filter_value} if filter_field is not None and filter_value is not None else {}
    rows = list_task_rows(database_path, **filters)
    if not rows:
        clear_screen()
        Terminal().y("No task records found.")
        pause()
        return

    selected_index = 0
    max_list_rows = int(config["max_list_rows"])
    filter_label = f"{filter_field}: {filter_value if filter_value != '' else '(empty)'}" if filters else None
    while rows:
        selected_index = min(selected_index, len(rows) - 1)
        render_database_browser(rows, selected_index, int(config["width"]), max_list_rows, filter_label)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
            continue
        if key == "down":
            selected_index = min(len(rows) - 1, selected_index + 1)
            continue

        selected_row = rows[selected_index]
        if key in {"s", "\r", "\n"}:
            selected_index = render_database_record(rows, selected_index, int(config["width"]))
        elif key in {"c", "a", "e"}:
            speak_database_answer(selected_row, {"c": "cz", "a": "en", "e": "es"}[key])
        elif key == "r":
            rating = read_star_rating()
            if rating is not None:
                if set_task_stars(database_path, int(selected_row["uid"]), rating):
                    Terminal().g(f"Task ID {selected_row['uid']} rating set to {rating}.")
                    rows = list_task_rows(database_path, **filters)
                else:
                    Terminal().r("Task record no longer exists.")
                pause()
        elif key == "d":
            task_id = int(selected_row["uid"])
            confirmation = input(f"Delete selected task ID {task_id}? Type yes to confirm: ").strip().casefold()
            if confirmation == "yes":
                if delete_task(database_path, task_id):
                    Terminal().g(f"Task ID {task_id} deleted.")
                    rows = list_task_rows(database_path, **filters)
                else:
                    Terminal().r("Task record no longer exists.")
                pause()
            else:
                Terminal().y("Delete cancelled.")
                pause()


def filter_values(config: dict[str, Any], field_name: str) -> list[str]:
    """Return the available database values for one supported filter field."""

    if field_name not in {"project", "selector", "task", "model", "stars"}:
        raise ValueError(f"Unsupported database filter: {field_name}")
    values = {
        str(row[field_name]) if row[field_name] is not None else ""
        for row in list_task_rows(main_database_file(config))
    }
    if field_name in {"project", "task", "model", "stars"}:
        values.discard("")
    if field_name == "stars":
        return sorted(values, key=int)
    return sorted(values, key=str.casefold)


def render_filter_value_picker(
    field_name: str, values: list[str], selected_index: int, width: int, max_list_rows: int
) -> None:
    """Draw one scrollable list of available filter values."""

    terminal = Terminal()
    separator = "-" * width
    clear_screen()
    print(separator)
    print(terminal.style(f"FILTER · {field_name.upper()}", fg="bright_white", bold=True))
    print(f"Value {selected_index + 1} of {len(values)}")
    print(separator)
    start = browser_window_start(selected_index, len(values), max_list_rows)
    end = min(start + max_list_rows, len(values))
    for index in range(start, end):
        value = values[index] or "(empty)"
        line = f"{index + 1}. {value}"
        print(
            f"{MENU_INDENT}> {terminal.style(line, fg='yellow', bold=True)}"
            if index == selected_index
            else f"{MENU_INDENT}  {line}"
        )
    print(f"{MENU_INDENT}↑/↓ move   Enter apply")
    render_back_footer(width)


def pick_filter_value(config: dict[str, Any], field_name: str) -> str | None:
    """Select one discovered value for a database filter field."""

    values = filter_values(config, field_name)
    if not values:
        Terminal().y(f"No {field_name} values found.")
        pause()
        return None
    selected_index = 0
    while True:
        render_filter_value_picker(
            field_name, values, selected_index, int(config["width"]), int(config["max_list_rows"])
        )
        key = read_key()
        if key in {"b", "left"}:
            return None
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(values) - 1, selected_index + 1)
        elif key in {"\r", "\n", "s"}:
            return values[selected_index]


def render_database_filter_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled first level of database filtering."""

    terminal = Terminal()
    width = int(config["width"])
    separator = "-" * width
    labels = ("project", "selector", "task", "model", "stars")
    clear_screen()
    print(separator)
    print(terminal.style("FILTER", fg="bright_white", bold=True))
    print(separator)
    print()
    for index, label in enumerate(labels):
        prefix = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{prefix}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def database_filter_menu(config: dict[str, Any]) -> None:
    """Choose a filter field and jump into the filtered database browser."""

    fields = ("project", "selector", "task", "model", "stars")
    selected_index = 0
    while True:
        render_database_filter_menu(config, selected_index)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(fields) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            field_name = fields[selected_index]
            value = pick_filter_value(config, field_name)
            if value is not None:
                browse_database_records(
                    config, field_name, int(value) if field_name == "stars" else value
                )
                return


def database_menu(config: dict[str, Any]) -> None:
    """Handle database inspection and record management actions."""

    while True:
        render_database_menu(config)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key == "l":
            browse_database_records(config)
        elif key == "g":
            database_group_menu(config)
        elif key == "s":
            task_id = read_task_id("show")
            if task_id is not None:
                run_database_action(config, ["--show", str(task_id)])
        elif key == "d":
            task_id = read_task_id("delete")
            if task_id is not None:
                confirmation = input(f"Delete task ID {task_id}? Type yes to confirm: ").strip().casefold()
                if confirmation == "yes":
                    run_database_action(config, ["--delete", str(task_id)])
                else:
                    Terminal().y("Delete cancelled.")
                    pause()
        elif key == "r":
            run_database_action(config, ["--list", "--star", "3"])
        elif key == "f":
            database_filter_menu(config)


def render_flow_menu(config: dict[str, Any], flow_key: str = "best_flows", title: str = "FLOW") -> None:
    """Draw one configured collection of flow shortcuts."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    clear_screen()
    print(separator)
    print(terminal.style(title, fg="bright_white", bold=True))
    print(separator)
    for index, flow_name in enumerate(config[flow_key], start=1):
        print(f"{MENU_INDENT}{terminal.style(index, fg='yellow', bold=True)}. {flow_name}")
    render_back_footer(int(config["width"]))


def run_flow(
    flow_name: str,
    pause_after: bool = True,
    report_result: bool = True,
    clear_before: bool = True,
    model_override: str | None = None,
    sc_commands: list[str] | None = None,
) -> int:
    """Run one configured text flow through runner.py and return its exit code."""

    if not RUNNER_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {RUNNER_SCRIPT_PATH.name}")
    if clear_before:
        clear_screen()
    command = [sys.executable, str(RUNNER_SCRIPT_PATH)]
    if model_override is not None:
        command.extend(("--model", model_override))
    for sc_command in sc_commands or []:
        command.extend(("--sc", sc_command))
    command.append(flow_name)
    model_label = f" (model: {model_override})" if model_override is not None else ""
    Terminal().c(f"Starting runner.py {flow_name}{model_label}…")
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    print()
    if report_result:
        if result.returncode:
            Terminal().r(f"Flow exited with code {result.returncode}.")
        else:
            Terminal().g("Done.")
    if pause_after:
        pause()
    return result.returncode


def active_project_directory(config: dict[str, Any]) -> Path:
    """Resolve the active project directory selected in project.json."""

    project_data = load_project_config(config)
    configured_directory = project_data.get("subdir")
    if not isinstance(configured_directory, str):
        raise ValueError("'subdir' must be non-empty text in project.json.")
    project_directory = (PROJECT_ROOT / validate_directory_name(configured_directory)).resolve()
    project_directory.mkdir(parents=True, exist_ok=True)
    return project_directory


def ensure_chat_context_file(config: dict[str, Any]) -> Path:
    """Ensure the chat context is non-empty before the first model request."""

    project_directory = active_project_directory(config)
    context_path = project_directory / CHAT_CONTEXT_FILENAME
    if not context_path.is_file() or not context_path.read_text(encoding="utf-8-sig").strip():
        context_path.write_text(CHAT_INITIAL_CONTEXT, encoding="utf-8")
    return context_path


def write_chat_input(config: dict[str, Any], message: str) -> Path:
    """Persist the current chat message for the structured chat flow."""

    if not message.strip():
        raise ValueError("Chat message cannot be empty.")
    input_path = active_project_directory(config) / CHAT_INPUT_FILENAME
    input_path.write_text(message.strip() + "\n", encoding="utf-8")
    return input_path


def format_chat_turn(user_message: str, assistant_reply: str) -> str:
    """Format one exchange as stable, human-readable context bullets."""

    def indent(value: str) -> str:
        return "\n".join(f"  {line}" for line in value.strip().splitlines())

    return f"- user:\n{indent(user_message)}\n- assistant:\n{indent(assistant_reply)}"


def append_chat_turn(config: dict[str, Any], user_message: str) -> None:
    """Append the current exchange and retain only the newest context turns."""

    project_directory = active_project_directory(config)
    context_path = project_directory / CHAT_CONTEXT_FILENAME
    reply_path = project_directory / CHAT_REPLY_FILENAME
    try:
        assistant_reply = reply_path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError as error:
        raise ValueError(f"Chat reply is missing: {CHAT_REPLY_FILENAME}") from error
    if not assistant_reply:
        raise ValueError("Chat reply is empty; context was not updated.")

    existing_context = context_path.read_text(encoding="utf-8-sig").strip()
    if existing_context.startswith("- user:\n"):
        turns = [
            "- user:\n" + turn
            for turn in existing_context.removeprefix("- user:\n").split("\n- user:\n")
        ]
    else:
        turns = []
    turns.append(format_chat_turn(user_message, assistant_reply))
    context_path.write_text("\n".join(turns[-int(config["chat_context_turns"]):]) + "\n", encoding="utf-8")


def clear_chat_context(config: dict[str, Any]) -> None:
    """Discard active exchanges while keeping a valid first-turn context."""

    context_path = active_project_directory(config) / CHAT_CONTEXT_FILENAME
    context_path.write_text(CHAT_INITIAL_CONTEXT, encoding="utf-8")


def render_chat_commands() -> None:
    """Show the two chat-only commands before the conversation begins."""

    terminal = Terminal()
    print(
        f"{terminal.style('/bye', fg='yellow', bold=True)} return to menu   "
        f"{terminal.style('/clr', fg='yellow', bold=True)} start a new conversation   "
        f"{terminal.style('/mod NEW', fg='yellow', bold=True)} switch the chat model"
    )
    print()


def extract_chat_mod_command(message: str) -> tuple[str, str] | None:
    """Split a leading /mod NEW command from the rest of the message, if present.

    Returns (new_model, remaining_message) where remaining_message may be
    empty when /mod was sent on its own. Returns None when the message does
    not start with /mod at all.
    """

    mod_match = re.match(r"^\s*/mod(?:\s+(\S+)(?:\s+(.*))?)?\s*$", message, re.IGNORECASE | re.DOTALL)
    if mod_match is None:
        return None
    new_model = mod_match.group(1)
    if not new_model:
        raise ValueError("Use /mod NEW to switch to model NEW.")
    remaining_message = (mod_match.group(2) or "").strip()
    return new_model, remaining_message


def extract_chat_modifier(message: str) -> tuple[str, list[str]]:
    """Take one leading catalog modifier out of a chat message, if present."""

    command_match = re.match(r"^\s*/([A-Za-z0-9_-]+)(?:\s+|$)", message)
    if command_match is None:
        return message.strip(), []
    requested_name = command_match.group(1).casefold()
    try:
        catalog = json.loads(SC_COMMAND_CATALOG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load slash-command catalog: {error}") from error
    groups = catalog.get("groups") if isinstance(catalog, dict) else None
    if not isinstance(groups, list):
        raise ValueError("Slash-command catalog requires a command-group list.")
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("commands"), list):
            continue
        for command in group["commands"]:
            if not isinstance(command, dict):
                continue
            name = command.get("sc")
            aliases = command.get("aliases", [])
            names = [name, *aliases] if isinstance(aliases, list) else [name]
            if requested_name not in {
                item.removeprefix("/").casefold() for item in names if isinstance(item, str)
            }:
                continue
            if command.get("kind") != "modifier":
                raise ValueError(f"/{requested_name} is not a chat modifier yet.")
            prompt = message[command_match.end() :].strip()
            if not prompt:
                raise ValueError(f"/{requested_name} needs a message after it.")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"/{requested_name} is invalid in the command catalog.")
            return prompt, [name]
    return message.strip(), []


def set_chat_selector() -> bool:
    """Set the shared Ollama selector once when a chat session begins."""

    script_path = PROJECT_ROOT / "cli_ollama.py"
    if not script_path.is_file():
        raise ValueError(f"Tool not found: {script_path.name}")
    result = subprocess.run([sys.executable, str(script_path), "--selector", "chat"], cwd=PROJECT_ROOT, check=False)
    if result.returncode:
        Terminal().r(f"Could not set chat selector (exit code {result.returncode}).")
        return False
    return True


def chat_flow_name(config: dict[str, Any]) -> str:
    """Choose the chat flow matching the configured language."""

    language = str(config["language"])
    return CHAT_FLOW_NAME_TEMPLATE.format(language=language)


def run_chat(config: dict[str, Any]) -> None:
    """Let James mediate repeated one-turn chat rounds before invoking the flow."""

    if not set_chat_selector():
        pause()
        return
    ensure_chat_context_file(config)
    active_model = str(config["chat_model"])
    clear_screen()
    render_chat_commands()
    while True:
        try:
            message = input(">? ")
        except EOFError:
            return
        if message.strip() == "/bye":
            return
        if message.strip() == "/clr":
            clear_chat_context(config)
            clear_screen()
            render_chat_commands()
            Terminal().g("Chat context cleared.")
            continue
        try:
            mod_result = extract_chat_mod_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if mod_result is not None:
            active_model, remaining_message = mod_result
            Terminal().g(f"Chat model set to {active_model}.")
            if not remaining_message:
                continue
            message = remaining_message
        if not message.strip():
            Terminal().y("Enter a message or /bye.")
            continue
        try:
            prompt, sc_commands = extract_chat_modifier(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        write_chat_input(config, prompt)
        exit_code = run_flow(
            chat_flow_name(config),
            pause_after=False,
            report_result=False,
            clear_before=False,
            model_override=active_model,
            sc_commands=sc_commands,
        )
        if exit_code:
            pause()
            return
        append_chat_turn(config, prompt)


def flow_menu(config: dict[str, Any], flow_key: str = "best_flows", title: str = "FLOW") -> None:
    """Run a selected configured flow collection, or return to the main menu."""

    while True:
        render_flow_menu(config, flow_key, title)
        key = read_key()
        if key in {"b", "left"}:
            return
        if key.isdigit():
            flow_index = int(key) - 1
            flows = config[flow_key]
            if 0 <= flow_index < len(flows):
                run_flow(str(flows[flow_index]))


def show_help(config: dict[str, Any]) -> None:
    """Describe the first version of the keyboard interface."""

    clear_screen()
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style("HELP", fg="bright_white", bold=True))
    print("-" * width)
    print()
    print(f"James version: {terminal.color('yellow', JAMES_VERSION)}")
    print(f"JSON version: {terminal.color('yellow', config['json_version'])}")
    print()
    print("Choose an item with one highlighted key; Enter is not required.")
    print("Project opens a second level: show displays project.json and dir_name changes subdir.")
    print("Camera and voice run the existing tools in this project.")
    print("MCP opens its own configured MCP-flow list.")
    print("Local James chat commands: /bye returns to the menu; /clr starts a new context;")
    print("/mod NEW switches the chat model for the rest of the session.")
    print("Local commands are handled by James and are not sent to the model.")
    wait_for_back(width)


def main() -> int:
    """Run James until the user exits the main menu."""

    try:
        config = load_james_config()
        while True:
            render_main_menu(config)
            key = read_key()
            if key == "q":
                clear_screen()
                return 0
            if key == "p":
                project_menu(config)
            elif key == "c":
                run_tool("cli_camera.py")
            elif key == "v":
                run_tool("cli_record_mp3.py")
            elif key == "h":
                show_help(config)
            elif key == "d":
                database_menu(config)
            elif key == "f":
                flow_menu(config)
            elif key == "m":
                flow_menu(config, "best_mcp_flows", "MCP")
            elif key == "t":
                run_chat(config)
            elif key == "s":
                setup_menu(config)
            elif key == "w":
                show_mock(config, "cowork")
    except (KeyboardInterrupt, RuntimeError, ValueError, OSError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Small cross-platform terminal menu for the local Ollama tools.

Run with ``python james.py``.  The menu reacts to single key presses, so
neither Windows nor Linux needs a shell-specific launcher.
"""

from __future__ import annotations

import json
import os
import socket
from datetime import date, timedelta
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from lib.wrapp_db import delete_task, list_task_rows, set_task_stars, short_text
from lib.wrapp_terminal import Terminal, ansi_enabled, hide_cursor, show_cursor
from lib.wrapp_vector import VectorError, load_config as load_vector_config, new_database_profile


PROJECT_ROOT = Path(__file__).resolve().parent
JAMES_DIRECTORY = PROJECT_ROOT / "james"
JAMES_CONFIG_PATH = JAMES_DIRECTORY / "james.json"
JAMES_ABOUT_PATH = JAMES_DIRECTORY / "about.md"
JAMES_HELP_PATH = JAMES_DIRECTORY / "james_help.md"
SC_COMMAND_CATALOG_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc.json"
SC_COMMANDS_CZ_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc_cz.md"
SC_COMMANDS_DEFAULT_PATH = PROJECT_ROOT / "assistant" / "commands" / "README.md"
JAMES_VERSION = "0.2.2"
DATABASE_SCRIPT_PATH = PROJECT_ROOT / "cli_db.py"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "runner.py"
SPEECH_SCRIPT_PATH = PROJECT_ROOT / "cli_speech.py"
VECTOR_SCRIPT_PATH = PROJECT_ROOT / "cli_vector.py"
OLLAMA_CONFIG_PATH = PROJECT_ROOT / "lib" / "ollama.json"
MCP_CONFIG_PATH = PROJECT_ROOT / "mcp" / "mcp_config.json"
MCP_SCRIPT_PATH = PROJECT_ROOT / "cli_mcp.py"
MCP_SERVER_PATH = PROJECT_ROOT / "mcp" / "wrapp_mcp_server.py"
VECTOR_CONFIG_PATH = PROJECT_ROOT / "cli_vector.json"
VECTOR_DATABASES_PATH = PROJECT_ROOT / "rag_wiki" / "databases.json"
MENU_INDENT = " " * 7
CHAT_FLOW_NAME_TEMPLATE = "flow_chat_{language}.json"
CHAT_CONTEXT_FILENAME = "chat_context.txt"
CHAT_REPLY_FILENAME = "chat_reply.txt"
CHAT_INPUT_FILENAME = "chat_input.txt"
CHAT_INITIAL_CONTEXT = "- context:\n  No previous conversation.\n"
SUPPORTED_LANGUAGES = ("cz", "en", "es")
FLOW_CATEGORY_KEYS = (
    "flows_test",
    "flows_single",
    "flows_code",
    "flows_batch",
    "flows_media",
    "flows_mcp",
    "flows_rag_wiki",
)
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
    for key in FLOW_CATEGORY_KEYS:
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


def active_project_name(config: dict[str, Any]) -> str:
    """Return the selected project name without letting a bad config hide a page."""

    try:
        return str(load_project_config(config).get("subdir", "not set"))
    except (KeyError, ValueError):
        return "not set"


def render_page_header(config: dict[str, Any], *location: str) -> None:
    """Render James' compact common header at the top of every James page."""

    terminal = Terminal()
    location_text = " | ".join(item for item in location if item)
    print(
        f"{config.get('name', 'James')} - v{JAMES_VERSION} | "
        f"project: {terminal.color('yellow', active_project_name(config))} | {location_text}"
    )


def pause(message: str = "Press any key to return to the menu.") -> None:
    """Show a short message and wait for one key."""

    Terminal().y(message)
    read_key()


def render_back_footer(width: int) -> None:
    """Draw the standard submenu return line below its bottom separator."""

    terminal = Terminal()
    print("-" * width)
    print(
        f"{MENU_INDENT}{terminal.style('b', fg='yellow', bold=True)}ack or "
        f"{terminal.style('Space', fg='yellow', bold=True)}"
    )


def wait_for_back(width: int) -> None:
    """Wait until the user returns from a detail screen with Back or Space."""

    render_back_footer(width)
    while read_key() not in {"b", " "}:
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
    render_page_header(config, "menu")
    separator = "-" * int(config["width"])
    art_width = max(len(line.rstrip()) for line in JAMES_ART)
    for line in JAMES_ART:
        rendered_line = line.rstrip().ljust(art_width)
        print(terminal.style(rendered_line.center(int(config["width"])), fg="green", bold=True))
    print(separator)
    print()
    main_menu_rows = (
        (("chat", "c"), ("MCP", "m"), ("about", "a")),
        (("flow", "f"), ("RAG", "r"), ("setup", "s")),
        (("database", "d"), ("cowork", "w"), ("help", "h")),
    )
    for row in main_menu_rows:
        line = "".join(render_menu_label(*item, width=13) for item in row)
        print(f"{MENU_INDENT}{line}")
    print()
    print(separator)
    print(f"{MENU_INDENT}{terminal.style('q', fg='yellow', bold=True)} = quit")


def render_project_menu(config: dict[str, Any]) -> None:
    """Draw the second level for the active project configuration."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    clear_screen()
    render_page_header(config, "setup", "project")
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
    render_page_header(config, "setup", "project", "show")
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
    render_page_header(config, "setup", "project", "dir_name")
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
        if key in {"b", " "}:
            return
        if key == "s":
            try:
                show_project_config(config)
            except ValueError as error:
                Terminal().r(f"Error: {error}")
                pause()
        elif key == "d":
            try:
                change_directory_name(config)
            except ValueError as error:
                Terminal().r(f"Error: {error}")
                pause()


def render_setup_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled Setup section."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("james", "project", "language", "ollama", "slash commands")
    clear_screen()
    render_page_header(config, "setup")
    print("-" * width)
    print(terminal.style("SETUP", fg="bright_white", bold=True))
    print(f"language: {terminal.color('yellow', config['language'])}")
    print("-" * width)
    print()
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def render_language_picker(config: dict[str, Any], selected_index: int) -> None:
    """Draw the language selector used from Setup."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("cz · Czech", "en · English", "es · Spanish")
    clear_screen()
    render_page_header(config, "setup", "language")
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
        if key in {"b", " "}:
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

    selected_index = 0
    while True:
        render_setup_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(4, selected_index + 1)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            show_james_config(config)
        elif selected_index == 1:
            try:
                project_menu(config)
            except ValueError as error:
                Terminal().r(f"Error: {error}")
                pause()
        elif selected_index == 2:
            language_menu(config)
        elif selected_index == 3:
            show_text_document(config, OLLAMA_CONFIG_PATH, "OLLAMA")
        else:
            show_text_document(config, slash_commands_document_path(config), "SLASH COMMANDS")


def slash_commands_document_path(config: dict[str, Any]) -> Path:
    """Choose the Czech command reference only for the Czech James language."""

    return SC_COMMANDS_CZ_PATH if config["language"] == "cz" else SC_COMMANDS_DEFAULT_PATH


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
    render_page_header(config, label)
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style(label.upper(), fg="bright_white", bold=True))
    print("-" * width)
    print()
    terminal.y("This section is a placeholder; its content will be added later.")
    wait_for_back(width)


def show_todo(config: dict[str, Any], title: str, message: str) -> None:
    """Show a named placeholder with its next planned capability."""

    clear_screen()
    render_page_header(config, title.lower())
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style(title, fg="bright_white", bold=True))
    print("-" * width)
    print()
    terminal.y(f"TODO: {message}")
    wait_for_back(width)


def render_rag_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled RAG action and configuration menu."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("ingest", "cli_vector.json", "rag_wiki/databases.json")
    clear_screen()
    render_page_header(config, "rag")
    print("-" * width)
    print(terminal.style("RAG", fg="bright_white", bold=True))
    print("-" * width)
    print()
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def ingest_new_wiki(config: dict[str, Any]) -> None:
    """Ask for a source-group name and create its local, chunk-only wiki DB."""

    if not VECTOR_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {VECTOR_SCRIPT_PATH.name}")
    clear_screen()
    render_page_header(config, "rag", "ingest")
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style("RAG · INGEST NEW WIKI", fg="bright_white", bold=True))
    print("-" * width)
    print()
    print("Enter the source-group name, for example: bitcoin")
    print("The command reads rag_wiki/src/NAME and creates rag_wiki/data/wiki_NAME.db.")
    print("It then registers NAME in rag_wiki/databases.json and makes it the active wiki.")
    name = input("Wiki name: ").strip()
    if not name:
        return
    try:
        vector_config, profiles = load_vector_config(VECTOR_CONFIG_PATH, PROJECT_ROOT)
        requested_profile = new_database_profile(vector_config, PROJECT_ROOT, name)
    except VectorError as error:
        terminal.r(f"Cannot read wiki configuration: {error}")
        pause()
        return

    command = [sys.executable, str(VECTOR_SCRIPT_PATH), "ingest-wiki", requested_profile.name]
    existing_profile = profiles.get(requested_profile.name)
    if existing_profile is not None:
        state = "exists" if existing_profile.path.is_file() else "is missing and will be created"
        print(f"Profile '{existing_profile.name}' is registered; database {state}: {existing_profile.path.name}")
        choice = input("[a] update changed sources / [p] overwrite and reindex all / Enter cancel: ").strip().casefold()
        if choice == "p":
            command.append("--reindex")
        elif choice != "a":
            terminal.y("Ingest cancelled.")
            pause()
            return

    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        terminal.r(f"Ingest failed (exit code {result.returncode}).")
    else:
        terminal.g("Wiki ingest completed and selected as main_db.")
    pause()


def rag_menu(config: dict[str, Any]) -> None:
    """Choose RAG actions using arrows and Enter, never letter shortcuts."""

    selected_index = 0
    while True:
        render_rag_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(2, selected_index + 1)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            ingest_new_wiki(config)
        elif selected_index == 1:
            show_text_document(config, VECTOR_CONFIG_PATH, "RAG · CLI VECTOR")
        else:
            show_text_document(config, VECTOR_DATABASES_PATH, "RAG · DATABASES")


def show_text_document(config: dict[str, Any], path: Path, title: str) -> None:
    """Display a small James-owned Markdown or JSON document read-only."""

    try:
        content = path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError as error:
        raise ValueError(f"Document is missing: {path.relative_to(PROJECT_ROOT)}") from error
    clear_screen()
    render_page_header(config, title.lower())
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style(title, fg="bright_white", bold=True))
    print("-" * width)
    print()
    print(content or "(empty)")
    wait_for_back(width)


def show_james_config(config: dict[str, Any]) -> None:
    """Display basic James settings while omitting the long flow collections."""

    basic_config = {key: value for key, value in config.items() if key not in FLOW_CATEGORY_KEYS}
    clear_screen()
    render_page_header(config, "setup", "james")
    terminal = Terminal()
    width = int(config["width"])
    print("-" * width)
    print(terminal.style("JAMES", fg="bright_white", bold=True))
    print("-" * width)
    print()
    print(json.dumps(basic_config, ensure_ascii=False, indent=2))
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


def render_database_menu(config: dict[str, Any], selected_index: int, summary_lines: list[str]) -> None:
    """Draw the cursor-controlled database menu with a cached summary."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    labels = ("list", "filter", "clone")
    clear_screen()
    render_page_header(config, "database")
    print(separator)
    print(terminal.style("DATABASE", fg="bright_white", bold=True))
    print(terminal.color("bright_black", "python .\\cli_db.py --sum"))
    for line in summary_lines:
        print(line)
    print(separator)
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(int(config["width"]))


def run_database_action(config: dict[str, Any], arguments: list[str]) -> None:
    """Run one database command visibly, then return to the database menu."""

    clear_screen()
    render_page_header(config, "database", "action")
    result = subprocess.run(database_command(config, arguments), cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        Terminal().r(f"Database command exited with code {result.returncode}.")
    else:
        Terminal().g("Done.")
    pause()


def read_clone_destination(config: dict[str, Any], prompt: str) -> str | None:
    """Ask for a new, non-conflicting database file under ``data/``."""

    while True:
        value = input(f"{prompt} (empty = cancel): ").strip()
        if not value:
            return None
        candidate = Path(value)
        if candidate.name != value or value in {".", ".."}:
            Terminal().r("Enter only a database file name, without a directory path.")
            continue
        file_name = candidate.name if candidate.suffix.casefold() == ".db" else f"{candidate.name}.db"
        destination = (PROJECT_ROOT / "data" / file_name).resolve()
        if destination == main_database_file(config):
            Terminal().r("The clone name must differ from the current database.")
            continue
        if destination.exists():
            Terminal().r(f"Database already exists: data/{file_name}")
            continue
        return f"data/{file_name}"


def clone_database_by_selector(config: dict[str, Any]) -> None:
    """Choose one selector and clone its records to a new file under ``data/``."""

    selector = pick_filter_value(config, "selector")
    if selector is None:
        return
    destination = read_clone_destination(config, f"New clone name for selector {selector!r}")
    if destination is not None:
        run_database_action(config, ["--selector", selector, "--clone", destination])


def clone_database_by_stars(config: dict[str, Any]) -> None:
    """Clone every record with a positive star rating to a new file under ``data/``."""

    destination = read_clone_destination(config, "New clone name for all starred records")
    if destination is not None:
        run_database_action(config, ["--clone-stars", destination])


def render_clone_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the two choices available below the database clone action."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("selectors", "stars")
    clear_screen()
    render_page_header(config, "database", "clone")
    print("-" * width)
    print(terminal.style("CLONE", fg="bright_white", bold=True))
    print("-" * width)
    print()
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def clone_database(config: dict[str, Any]) -> None:
    """Choose whether a clone is scoped by selector or positive star ratings."""

    selected_index = 0
    while True:
        render_clone_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(1, selected_index + 1)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            clone_database_by_selector(config)
        else:
            clone_database_by_stars(config)


def render_database_record(
    config: dict[str, Any], rows: list[Any], selected_index: int, width: int, location: tuple[str, ...] = ("database",)
) -> int:
    """Show complete records and allow previous/next navigation in the current list."""

    terminal = Terminal()
    while True:
        row = rows[selected_index]
        separator = "-" * width
        clear_screen()
        render_page_header(config, *location, "record", str(row["uid"]))
        print(separator)
        print(terminal.style(f"DATABASE RECORD #{row['uid']}", fg="bright_white", bold=True))
        print(f"Record {selected_index + 1} of {len(rows)}")
        print(separator)
        for field_name in row.keys():
            value = "NULL" if row[field_name] is None else str(row[field_name])
            print(f"{terminal.color('yellow', f'{field_name}:')} {value}")
        footer_fields = (
            ("P", "project"),
            ("S", "selector"),
            ("T", "task"),
            ("M", "model"),
        )
        footer = " | ".join(
            f"{short_name}: {'NULL' if row[field_name] is None else row[field_name]}"
            for short_name, field_name in footer_fields
        )
        print(f"{terminal.color('yellow', 'UID:')} {row['uid']} | {footer}")
        print(separator)
        print(
            f"{MENU_INDENT}{terminal.style('p', fg='yellow', bold=True)}rev ← | "
            f"{terminal.style('n', fg='yellow', bold=True)}ext → || "
            f"{terminal.style('a', fg='yellow', bold=True)}dd | "
            f"{terminal.style('d', fg='yellow', bold=True)}elete | "
            f"{terminal.style('b', fg='yellow', bold=True)}ack (or space)"
        )
        print(separator)
        key = read_key()
        if key in {"b", " "}:
            return selected_index
        # Rows are sorted newest-first.  Therefore a higher UID is one index
        # earlier, which keeps Next/Right as the numeric +1 direction.
        if key in {"p", "left"}:
            selected_index = min(len(rows) - 1, selected_index + 1)
        elif key in {"n", "right"}:
            selected_index = max(0, selected_index - 1)
        elif key == "a":
            answer = input("Answer content for the new record (empty = cancel): ").strip()
            if answer:
                run_database_action(config, ["--add", answer])
        elif key == "d":
            task_id = int(row["uid"])
            confirmation = input(f"Delete selected task ID {task_id}? Type yes to confirm: ").strip().casefold()
            if confirmation == "yes":
                if delete_task(main_database_file(config), task_id):
                    rows.pop(selected_index)
                    Terminal().g(f"Task ID {task_id} deleted.")
                    pause()
                    if not rows:
                        return 0
                    selected_index = min(selected_index, len(rows) - 1)
                else:
                    Terminal().r("Task record no longer exists.")
                    pause()
            else:
                Terminal().y("Delete cancelled.")
                pause()


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
    config: dict[str, Any],
    rows: list[Any],
    selected_index: int,
    width: int,
    max_list_rows: int,
    filter_label: str | None = None,
    location: tuple[str, ...] = ("database", "list"),
) -> None:
    """Draw a compact, keyboard-navigable page of task records."""

    terminal = Terminal()
    separator = "-" * width
    clear_screen()
    render_page_header(config, *location)
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
        "Open a record to add or delete."
    )
    render_back_footer(width)


def browse_database_records(
    config: dict[str, Any],
    filter_field: str | None = None,
    filter_value: str | int | None = None,
    datetime_prefix: str | None = None,
) -> None:
    """Browse main-database rows and apply actions to the selected record."""

    database_path = main_database_file(config)
    filters: dict[str, str | int] = {}
    if filter_field is not None and filter_value is not None:
        filters[filter_field] = filter_value
    if datetime_prefix is not None:
        filters["datetime_prefix"] = datetime_prefix
    rows = list_task_rows(database_path, **filters)
    if not rows:
        clear_screen()
        render_page_header(config, "database", "filter" if filters else "list")
        Terminal().y("No task records found.")
        pause()
        return

    selected_index = 0
    max_list_rows = int(config["max_list_rows"])
    if datetime_prefix is not None:
        filter_label = f"datetime: {datetime_prefix}"
        page_location = ("database", "filter", "datetime", datetime_prefix)
    elif filter_field is not None and filter_value is not None:
        filter_label = f"{filter_field}: {filter_value if filter_value != '' else '(empty)'}"
        page_location = ("database", "filter", filter_field, str(filter_value or "(empty)"))
    else:
        filter_label = None
        page_location = ("database", "list")
    while rows:
        selected_index = min(selected_index, len(rows) - 1)
        render_database_browser(
            config, rows, selected_index, int(config["width"]), max_list_rows, filter_label, page_location
        )
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
            continue
        if key == "down":
            selected_index = min(len(rows) - 1, selected_index + 1)
            continue

        selected_row = rows[selected_index]
        if key in {"s", "\r", "\n"}:
            selected_index = render_database_record(config, rows, selected_index, int(config["width"]), page_location)
            rows = list_task_rows(database_path, **filters)
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


def filter_value_groups(config: dict[str, Any], field_name: str) -> list[tuple[str, int]]:
    """Return each filterable value with its exact task-record count."""

    temporal_fields = {"monthly": 7, "last_week": 10}
    if field_name not in {"project", "selector", "task", "model", "stars", *temporal_fields}:
        raise ValueError(f"Unsupported database filter: {field_name}")
    counts: dict[str, int] = {}
    recent_days = [str(date.today() - timedelta(days=offset)) for offset in range(7)]
    if field_name == "last_week":
        counts = {day: 0 for day in recent_days}
    for row in list_task_rows(main_database_file(config)):
        if field_name in temporal_fields:
            raw_datetime = row["datetime"]
            value = str(raw_datetime)[: temporal_fields[field_name]] if raw_datetime is not None else ""
        else:
            value = str(row[field_name]) if row[field_name] is not None else ""
        if field_name != "last_week" or value in counts:
            counts[value] = counts.get(value, 0) + 1
    if field_name in {"project", "task", "model", "stars", *temporal_fields}:
        counts.pop("", None)
    if field_name == "stars":
        return sorted(counts.items(), key=lambda item: int(item[0]))
    if field_name in {"monthly", "last_week"}:
        return sorted(counts.items(), key=lambda item: item[0], reverse=True)
    return sorted(counts.items(), key=lambda item: item[0].casefold())


def render_filter_value_picker(
    config: dict[str, Any],
    field_name: str,
    values: list[tuple[str, int]],
    selected_index: int,
    width: int,
    max_list_rows: int,
) -> None:
    """Draw one scrollable list of available filter values."""

    terminal = Terminal()
    separator = "-" * width
    clear_screen()
    render_page_header(config, "database", "filter", field_name.replace("_", " "))
    print(separator)
    print(terminal.style(f"FILTER · {field_name.replace('_', ' ').upper()}", fg="bright_white", bold=True))
    print(f"Choices: {len(values)}")
    print(separator)
    start = browser_window_start(selected_index, len(values), max_list_rows)
    end = min(start + max_list_rows, len(values))
    for index in range(start, end):
        value, record_count = values[index]
        line = f"{record_count:>7}  {value or '(empty)'}"
        print(
            f"{MENU_INDENT}> {terminal.style(line, fg='yellow', bold=True)}"
            if index == selected_index
            else f"{MENU_INDENT}  {line}"
        )
    print(f"{MENU_INDENT}↑/↓ move   Enter apply")
    render_back_footer(width)


def pick_filter_value(config: dict[str, Any], field_name: str) -> str | None:
    """Select one discovered value for a database filter field."""

    values = filter_value_groups(config, field_name)
    if not values:
        Terminal().y(f"No {field_name} values found.")
        pause()
        return None
    selected_index = 0
    while True:
        render_filter_value_picker(
            config, field_name, values, selected_index, int(config["width"]), int(config["max_list_rows"])
        )
        key = read_key()
        if key in {"b", " "}:
            return None
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(values) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            return values[selected_index][0]


def render_database_filter_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled first level of database filtering."""

    terminal = Terminal()
    width = int(config["width"])
    separator = "-" * width
    labels = ("project", "selector", "task", "model", "stars", "monthly", "last_week")
    clear_screen()
    render_page_header(config, "database", "filter")
    print(separator)
    print(terminal.style("FILTER", fg="bright_white", bold=True))
    print(separator)
    print()
    for index, label in enumerate(labels):
        prefix = "> " if index == selected_index else "  "
        display_label = label.replace("_", " ")
        text = terminal.style(display_label, fg="yellow", bold=True) if index == selected_index else display_label
        print(f"{MENU_INDENT}{prefix}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def database_filter_menu(config: dict[str, Any]) -> None:
    """Choose a filter field and jump into the filtered database browser."""

    fields = ("project", "selector", "task", "model", "stars", "monthly", "last_week")
    selected_index = 0
    while True:
        render_database_filter_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(fields) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            field_name = fields[selected_index]
            value = pick_filter_value(config, field_name)
            if value is not None:
                if field_name in {"monthly", "last_week"}:
                    browse_database_records(config, datetime_prefix=value)
                else:
                    browse_database_records(config, field_name, int(value) if field_name == "stars" else value)
                return


def mcp_endpoint() -> tuple[str, int, str]:
    """Read the configured local MCP endpoint for display and startup checks."""

    try:
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read MCP setup: {error}") from error
    host, port, path = data.get("host"), data.get("port"), data.get("path")
    if not isinstance(host, str) or not host or not isinstance(port, int) or not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("MCP setup requires host, integer port, and a path beginning with '/'.")
    return host, port, path


def mcp_port_is_open(host: str, port: int) -> bool:
    """Return whether a local TCP listener already accepts the configured port."""

    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def render_mcp_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled local MCP section."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("run MCP server", "list MCP services", "show MCP setup")
    clear_screen()
    render_page_header(config, "mcp")
    print("-" * width)
    print(terminal.style("MCP", fg="bright_white", bold=True))
    print("-" * width)
    print()
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def run_mcp_server(config: dict[str, Any]) -> None:
    """Start the configured local Streamable HTTP server in the background."""

    if not MCP_SERVER_PATH.is_file():
        raise ValueError(f"MCP server is missing: {MCP_SERVER_PATH}")
    host, port, path = mcp_endpoint()
    endpoint = f"http://{host}:{port}{path}"
    clear_screen()
    render_page_header(config, "mcp", "server")
    if mcp_port_is_open(host, port):
        Terminal().y(f"MCP server is already listening at {endpoint}")
        pause()
        return
    popen_options: dict[str, Any] = {"cwd": PROJECT_ROOT, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NO_WINDOW
    server = subprocess.Popen([sys.executable, str(MCP_SERVER_PATH)], **popen_options)
    Terminal().g(f"MCP server started (PID {server.pid}).")
    print(f"Endpoint: {endpoint}")
    print(f"Setup: {MCP_CONFIG_PATH.relative_to(PROJECT_ROOT)}")
    pause()


def list_mcp_services(config: dict[str, Any]) -> None:
    """List the services exposed by the local server using ``cli_mcp --list``."""

    if not MCP_SCRIPT_PATH.is_file():
        raise ValueError(f"MCP CLI is missing: {MCP_SCRIPT_PATH}")
    clear_screen()
    render_page_header(config, "mcp", "services")
    Terminal().c("Listing local MCP services…")
    host, port, _ = mcp_endpoint()
    command = [sys.executable, str(MCP_SCRIPT_PATH), "--list"]
    if mcp_port_is_open(host, port):
        command.append("--connect-local")
        Terminal().c("Using the already running local MCP server.")
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        Terminal().r(f"MCP service listing failed (exit code {result.returncode}).")
    else:
        Terminal().g("MCP services listed.")
    pause()


def mcp_menu(config: dict[str, Any]) -> None:
    """Choose local MCP server actions using arrows and Enter."""

    selected_index = 0
    while True:
        render_mcp_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(2, selected_index + 1)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            run_mcp_server(config)
        elif selected_index == 1:
            list_mcp_services(config)
        else:
            show_text_document(config, MCP_CONFIG_PATH, "MCP · SETUP")


def database_menu(config: dict[str, Any]) -> None:
    """Handle database inspection and record management actions."""

    selected_index = 0
    summary_lines = read_database_summary(config)
    while True:
        render_database_menu(config, selected_index, summary_lines)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
            continue
        if key == "down":
            selected_index = min(2, selected_index + 1)
            continue
        if key not in {"\r", "\n"}:
            continue
        if selected_index == 0:
            browse_database_records(config)
        elif selected_index == 1:
            database_filter_menu(config)
        else:
            clone_database(config)
        summary_lines = read_database_summary(config)


def render_flow_list_menu(config: dict[str, Any], flow_key: str, title: str, selected_index: int) -> None:
    """Draw one cursor-controlled configured collection of flows."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    flows = config[flow_key]
    clear_screen()
    render_page_header(config, "flow", title.casefold())
    print(separator)
    print(terminal.style(title, fg="bright_white", bold=True))
    print(f"Flow {selected_index + 1} of {len(flows)}")
    print(separator)
    print()
    for index, flow_name in enumerate(flows):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(flow_name, fg="yellow", bold=True) if index == selected_index else flow_name
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter run")
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
    """Show chat-local commands and the catalog slash-command shortcut."""

    terminal = Terminal()
    print(
        f"{terminal.style('/bye', fg='yellow', bold=True)} return to menu   "
        f"{terminal.style('/clr', fg='yellow', bold=True)} start a new conversation   "
        f"{terminal.style('/mod NEW', fg='yellow', bold=True)} switch the chat model\n"
        f"{terminal.style('/COMMAND message', fg='yellow', bold=True)} use any command from sc.json"
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


def extract_chat_sc_command(message: str) -> tuple[str, list[str]]:
    """Take one leading catalog slash command out of a chat message, if present.

    ``/bye``, ``/clr``, and ``/mod`` are processed earlier by :func:`run_chat`
    and remain exclusive James commands.  Every catalog command kind is valid
    here; the normal ``cli_ollama`` validation still rejects incompatible
    command combinations when a flow is executed.
    """

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
    render_page_header(config, "chat")
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
            render_page_header(config, "chat")
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
            prompt, sc_commands = extract_chat_sc_command(message)
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


def flow_list_menu(config: dict[str, Any], flow_key: str, title: str) -> None:
    """Run a selected configured flow collection, or return to its category menu."""

    flows = config[flow_key]
    selected_index = 0
    while True:
        render_flow_list_menu(config, flow_key, title, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(flows) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            run_flow(str(flows[selected_index]))


def render_flow_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the Flow category menu."""

    terminal = Terminal()
    width = int(config["width"])
    categories = ("test", "single", "code", "batch", "media", "mcp", "rag_wiki")
    clear_screen()
    render_page_header(config, "flow")
    print("-" * width)
    print(terminal.style("FLOW", fg="bright_white", bold=True))
    print(f"Category {selected_index + 1} of {len(categories)}")
    print("-" * width)
    print()
    for index, label in enumerate(categories):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def flow_menu(config: dict[str, Any]) -> None:
    """Choose a flow category before opening its configured flow list."""

    categories = (
        ("flows_test", "TEST"),
        ("flows_single", "SINGLE"),
        ("flows_code", "CODE"),
        ("flows_batch", "BATCH"),
        ("flows_media", "MEDIA"),
        ("flows_mcp", "MCP"),
        ("flows_rag_wiki", "RAG_WIKI"),
    )
    selected_index = 0
    while True:
        render_flow_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(categories) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            flow_list_menu(config, *categories[selected_index])


def show_help(config: dict[str, Any]) -> None:
    """Display the maintained Help document."""

    show_text_document(config, JAMES_HELP_PATH, "HELP")


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
            if key == "c":
                run_chat(config)
            elif key == "m":
                mcp_menu(config)
            elif key == "a":
                show_text_document(config, JAMES_ABOUT_PATH, "ABOUT")
            elif key == "f":
                flow_menu(config)
            elif key == "r":
                rag_menu(config)
            elif key == "s":
                setup_menu(config)
            elif key == "d":
                database_menu(config)
            elif key == "w":
                show_mock(config, "cowork")
            elif key == "h":
                show_help(config)
    except (KeyboardInterrupt, RuntimeError, ValueError, OSError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

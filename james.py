"""Small cross-platform terminal menu for the local Ollama tools.

Run with ``python james.py``.  The menu reacts to single key presses, so
neither Windows nor Linux needs a shell-specific launcher.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from lib.wrapp_terminal import Terminal, ansi_enabled


PROJECT_ROOT = Path(__file__).resolve().parent
JAMES_CONFIG_PATH = PROJECT_ROOT / "james.json"
DATABASE_SCRIPT_PATH = PROJECT_ROOT / "cli_db.py"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "runner.py"
MENU_INDENT = " " * 8


def load_james_config() -> dict[str, Any]:
    """Load and validate the small menu configuration."""

    try:
        data = json.loads(JAMES_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Configuration is missing: {JAMES_CONFIG_PATH.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {JAMES_CONFIG_PATH.name}: {error}") from error

    if not isinstance(data, dict) or data.get("version") != "0.1":
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires an object with 'version': '0.1'.")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'name'.")
    width = data.get("width")
    if isinstance(width, bool) or not isinstance(width, int) or width < 10:
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires an integer 'width' of at least 10.")
    if not isinstance(data.get("main_db"), str) or not data["main_db"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'main_db'.")
    best_flows = data.get("best_flows")
    if not isinstance(best_flows, list) or not 1 <= len(best_flows) <= 9:
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires one to nine 'best_flows'.")
    for flow in best_flows:
        if not isinstance(flow, str) or not flow.strip() or Path(flow).name != flow:
            raise ValueError("Each 'best_flows' entry must be a non-empty flow filename.")
    if not isinstance(data.get("project_config"), str) or not data["project_config"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'project_config'.")
    return data


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

    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in {"\x00", "\xe0"}:
            msvcrt.getwch()  # consume the second half of a special key
            return ""
        return key.casefold()

    import termios
    import tty

    if not sys.stdin.isatty():
        raise RuntimeError("James requires an interactive terminal.")
    descriptor = sys.stdin.fileno()
    original_settings = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        return sys.stdin.read(1).casefold()
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, original_settings)


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


def render_item(label: str, key: str) -> str:
    """Format one menu name, highlighting its shortcut when it is in the name."""

    terminal = Terminal()
    index = label.casefold().find(key.casefold())
    if index < 0:
        return f"{MENU_INDENT}{label}"
    return f"{MENU_INDENT}{label[:index]}{terminal.style(label[index], fg='yellow', bold=True)}{label[index + 1:]}"


def render_main_menu(config: dict[str, Any]) -> None:
    """Draw the first level of the menu."""

    terminal = Terminal()
    clear_screen()
    try:
        project_name = str(load_project_config(config).get("subdir", "not set"))
    except ValueError:
        project_name = "not set"
    separator = "-" * int(config["width"])
    print(separator)
    print(f"{config['name']} - ver. {config['version']}")
    print(f"actual project: {terminal.color('yellow', project_name)}")
    print(separator)
    print()
    print(render_item("project", "p"))
    print(render_item("camera", "c"))
    print(render_item("voice", "v"))
    print(render_item("chat", "x"))
    print(render_item("flow", "f"))
    print(render_item("cowork", "w"))
    print(render_item("database", "d"))
    print(render_item("setup", "s"))
    print(render_item("help", "h"))
    print()
    print(separator)
    print(f"{MENU_INDENT}{terminal.style('q', fg='yellow', bold=True)} = quit")


def render_project_menu(config: dict[str, Any]) -> None:
    """Draw the second level for the active project configuration."""

    terminal = Terminal()
    clear_screen()
    print(terminal.style("PROJECT", fg="bright_white", bold=True))
    try:
        project_data = load_project_config(config)
        directory = project_data.get("subdir", "not set")
        print(f"{terminal.color('bright_black', 'directory:')} {directory}")
    except ValueError as error:
        terminal.r(f"Cannot load configuration: {error}")
    print()
    print(render_item("show", "s"))
    print(render_item("dir_name", "d"))
    print()
    print(f"{MENU_INDENT}{terminal.color('bright_black', 'b or q = back')}")


def show_project_config(config: dict[str, Any]) -> None:
    """Display the complete shared project JSON."""

    clear_screen()
    path = project_config_path(config)
    print(Terminal().style(path.name, fg="bright_white", bold=True))
    print()
    print(json.dumps(load_project_config(config), ensure_ascii=False, indent=2))
    print()
    pause()


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
    print(terminal.style("PROJECT · dir_name", fg="bright_white", bold=True))
    print(f"Current value: {terminal.color('cyan', current)}")
    print("Enter a relative directory name; empty input cancels the change.")
    value = input("New dir_name: ").strip()
    if not value:
        return
    project_data["subdir"] = validate_directory_name(value)
    save_project_config(config, project_data)
    terminal.g(f"Saved to {project_config_path(config).name}: subdir = {project_data['subdir']}")
    pause()


def project_menu(config: dict[str, Any]) -> None:
    """Handle the project submenu until the user returns to the main menu."""

    while True:
        render_project_menu(config)
        key = read_key()
        if key in {"b", "q", "\x1b"}:
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


def show_mock(label: str) -> None:
    """Give unfinished menu sections a useful, non-destructive placeholder."""

    clear_screen()
    terminal = Terminal()
    print(terminal.style(label.upper(), fg="bright_white", bold=True))
    print()
    terminal.y("This section is a placeholder; its content will be added later.")
    pause()


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
    print(render_item("group project", "g"))
    print(render_item("show ID", "s"))
    print(render_item("delete ID", "d"))
    print(render_item("rating 3", "r"))
    print(separator)
    print(f"{MENU_INDENT}{terminal.color('bright_black', 'b or q = back')}")


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


def database_menu(config: dict[str, Any]) -> None:
    """Handle database inspection and record management actions."""

    while True:
        render_database_menu(config)
        key = read_key()
        if key in {"b", "q", "\x1b"}:
            return
        if key == "l":
            run_database_action(config, ["--list"])
        elif key == "g":
            run_database_action(config, ["--group", "project"])
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


def render_flow_menu(config: dict[str, Any]) -> None:
    """Draw the configured best-flow shortcuts."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    clear_screen()
    print(separator)
    print(terminal.style("FLOW", fg="bright_white", bold=True))
    print(separator)
    for index, flow_name in enumerate(config["best_flows"], start=1):
        print(f"{MENU_INDENT}{terminal.style(index, fg='yellow', bold=True)}. {flow_name}")
    print(separator)
    print(f"{MENU_INDENT}{terminal.color('bright_black', 'b or q = back')}")


def run_flow(flow_name: str) -> None:
    """Run one configured text flow through runner.py."""

    if not RUNNER_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {RUNNER_SCRIPT_PATH.name}")
    clear_screen()
    Terminal().c(f"Starting runner.py {flow_name}…")
    result = subprocess.run([sys.executable, str(RUNNER_SCRIPT_PATH), flow_name], cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        Terminal().r(f"Flow exited with code {result.returncode}.")
    else:
        Terminal().g("Done.")
    pause()


def flow_menu(config: dict[str, Any]) -> None:
    """Run a selected configured flow, or return to the main menu."""

    while True:
        render_flow_menu(config)
        key = read_key()
        if key in {"b", "q", "\x1b"}:
            return
        if key.isdigit():
            flow_index = int(key) - 1
            best_flows = config["best_flows"]
            if 0 <= flow_index < len(best_flows):
                run_flow(str(best_flows[flow_index]))


def show_help() -> None:
    """Describe the first version of the keyboard interface."""

    clear_screen()
    terminal = Terminal()
    print(terminal.style("HELP", fg="bright_white", bold=True))
    print()
    print("Choose an item with one highlighted key; Enter is not required.")
    print("Project opens a second level: show displays project.json and dir_name changes subdir.")
    print("Camera and voice run the existing tools in this project.")
    print()
    pause()


def main() -> int:
    """Run James until the user exits the main menu."""

    try:
        config = load_james_config()
        while True:
            render_main_menu(config)
            key = read_key()
            if key in {"q", "\x1b"}:
                clear_screen()
                return 0
            if key == "p":
                project_menu(config)
            elif key == "c":
                run_tool("cli_camera.py")
            elif key == "v":
                run_tool("cli_record_mp3.py")
            elif key == "h":
                show_help()
            elif key == "d":
                database_menu(config)
            elif key == "f":
                flow_menu(config)
            elif key in {"x", "w", "s"}:
                show_mock({"x": "chat", "w": "cowork", "s": "setup"}[key])
    except (KeyboardInterrupt, RuntimeError, ValueError, OSError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

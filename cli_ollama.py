"""Run a typed text task through the shared local Ollama configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import sys

from lib.wrapp_ffmpeg import __version__ as WRAPP_FFMPEG_VERSION
from lib.wrapp_db import __version__ as WRAPP_DB_VERSION
from lib.wrapp_img import __version__ as WRAPP_IMG_VERSION
from lib.wrapp_img import resolve_image_path
from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_json_object,
    load_project_config,
    read_debug_enabled,
    read_log_enabled,
)
from lib.wrapp_log import __version__ as WRAPP_LOG_VERSION
from lib.wrapp_ollama import __version__ as WRAPP_OLLAMA_VERSION
from lib.wrapp_piper import __version__ as WRAPP_PIPER_VERSION
from lib.wrapp_system import __version__ as WRAPP_SYSTEM_VERSION
from lib.wrapp_system import print_system_info
from lib.wrapp_terminal import Terminal
from lib.wrapp_terminal import __version__ as WRAPP_TERMINAL_VERSION
from lib.wrapp_whisper import __version__ as WRAPP_WHISPER_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
ASSISTANT_TASKS_DIR = PROJECT_DIR / "assistant" / "tasks"
OLLAMA_CONFIG_PATH = PROJECT_DIR / "lib" / "ollama.json"
DEFAULT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
TEXT_FILE_EXTENSIONS = (".txt", ".md")
TRANSLATION_INSTRUCTIONS = {
    "c2a": "Translate from Czech to English. Return only the translation.",
    "e2c": "Translate from English to Czech. Return only the translation.",
}
__version__ = "0.35"
WRAPP_MCP_VERSION = "0.26.01"
MODULE_VERSIONS = (
    ("wrapp_ollama", WRAPP_OLLAMA_VERSION),
    ("wrapp_log", WRAPP_LOG_VERSION),
    ("wrapp_terminal", WRAPP_TERMINAL_VERSION),
    ("wrapp_system", WRAPP_SYSTEM_VERSION),
    ("wrapp_db.py", WRAPP_DB_VERSION),
    ("wrapp_mcp", WRAPP_MCP_VERSION),
    ("wrapp_img", WRAPP_IMG_VERSION),
    ("wrapp_piper", WRAPP_PIPER_VERSION),
    ("wrapp_whisper", WRAPP_WHISPER_VERSION),
    ("wrapp_ffmpeg", WRAPP_FFMPEG_VERSION),
)
VERSION_LABEL_WIDTH = max(len(name) for name, _version in MODULE_VERSIONS) + 1


class VersionAction(argparse.Action):
    """Print a colorized, aligned version overview."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, nargs=0, default=default, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        terminal = Terminal()
        print(terminal.color("y", f"cli_ollama.py {__version__} (Python 3.10+)"))
        for name, version in MODULE_VERSIONS:
            label = f"{name}:".ljust(VERSION_LABEL_WIDTH)
            print(f"{terminal.color('g', label)} {version}")
        parser.exit()


def positive_integer(value: str) -> int:
    """Parse an Ollama option that must be a positive whole number."""

    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def non_negative_float(value: str) -> float:
    """Parse a non-negative Ollama temperature override."""

    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def positive_float(value: str) -> float:
    """Parse a positive Ollama repeat-penalty override."""

    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_boolean(value: str) -> bool:
    """Parse an explicit ``true`` or ``false`` command-line value."""

    normalized_value = value.casefold()
    if normalized_value == "true":
        return True
    if normalized_value == "false":
        return False
    raise argparse.ArgumentTypeError('must be "true" or "false"')


def parse_arguments() -> argparse.Namespace:
    """Parse a task type, optional prompt text or file, and runtime overrides."""

    parser = argparse.ArgumentParser(
        description=(
            "Run a text task from task_*.json through the shared lib/ollama.json configuration. "
            "Task settings override shared defaults; command-line options override the task."
        )
    )
    parser.add_argument(
        "--type",
        dest="task_type",
        metavar="TASK.json",
        help="task configuration in assistant/tasks; required to run a task",
    )
    parser.add_argument(
        "--project",
        metavar="DIRECTORY",
        help="select and save the project directory below the project root, then exit",
    )
    parser.add_argument(
        "--debug",
        type=parse_boolean,
        metavar="true|false",
        help="save the project debug setting for following CLI commands, then exit",
    )
    parser.add_argument(
        "--selector",
        "--setector",
        dest="selector",
        metavar="TEXT",
        help="save the project task-record selector, then exit (--setector is an alias)",
    )
    parser.add_argument(
        "--clrlog",
        "--clear_log",
        dest="clear_log",
        action="store_true",
        help="clear log.txt in the active project directory, then exit",
    )
    parser.add_argument(
        "--echo",
        dest="echo_message",
        metavar="MESSAGE",
        help="print MESSAGE in yellow and append it when project logging is enabled",
    )
    parser.add_argument(
        "--data",
        "--input",
        dest="data",
        nargs="+",
        metavar="VALUE",
        help=(
            "current prompt input or UTF-8 file in the active project directory; "
            "use - to read from standard input, or PROMPT - to label the input request; "
            "overrides the task prompt"
        ),
    )
    parser.add_argument(
        "--text",
        dest="literal_text",
        metavar="TEXT",
        help="literal input text for a translate task; it is never treated as a file name",
    )
    parser.add_argument(
        "--instruction",
        "--replace-rules",
        dest="instruction",
        metavar="TEXT|FILE",
        help="replace task rules with text or an UTF-8 project file (--instruction is a legacy alias)",
    )
    parser.add_argument(
        "--rules",
        action="append",
        metavar="TEXT|FILE",
        help="append runtime rules; may be specified more than once",
    )
    parser.add_argument(
        "--context",
        dest="context_files",
        action="append",
        metavar="FILE",
        help="append a labelled UTF-8 reference file from the active project; may be specified more than once",
    )
    parser.add_argument(
        "--capability",
        dest="extra_capabilities",
        action="append",
        metavar="ID",
        help="append assistant/capabilities/ID.md; may be specified more than once",
    )
    parser.add_argument(
        "--skill",
        dest="extra_legacy_skills",
        action="append",
        metavar="ID",
        help="legacy alias that searches assistant/capabilities then assistant/profiles",
    )
    parser.add_argument(
        "--profile",
        dest="extra_profiles",
        action="append",
        metavar="ID",
        help="append assistant/profiles/ID.md; may be specified more than once",
    )
    sc_language_group = parser.add_mutually_exclusive_group()
    sc_language_group.add_argument(
        "--sc-cz",
        dest="sc_language",
        action="store_const",
        const="cz",
        help="use Czech slash-command rules and require a Czech response",
    )
    sc_language_group.add_argument(
        "--sc-en",
        dest="sc_language",
        action="store_const",
        const="en",
        help="use English slash-command rules and require an English response",
    )
    sc_language_group.add_argument(
        "--sc-es",
        dest="sc_language",
        action="store_const",
        const="es",
        help="use Spanish slash-command rules and require a Spanish response",
    )
    parser.add_argument(
        "--sc",
        dest="sc_commands",
        action="append",
        metavar="NAME",
        help="append a slash command from assistant/commands/sc.json; may be specified more than once",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the fully resolved Ollama JSON request without contacting Ollama",
    )
    parser.add_argument(
        "--in",
        dest="input_file",
        metavar="FILE.txt|FILE.md|-",
        help="input file, or - for standard input, for a translate task; overrides default_input_file",
    )
    parser.add_argument(
        "--out",
        metavar="RESULT.txt|RESULT.md",
        help="response file in the active project directory; overrides default_output_file",
    )
    parser.add_argument(
        "--append-out",
        action="store_true",
        help="append a prompt response to --out or default_output_file instead of replacing the file",
    )
    parser.add_argument(
        "--out-header",
        metavar="TEXT",
        help="write TEXT above the response output file (useful with --append-out)",
    )
    parser.add_argument(
        "--clear-out",
        metavar="RESULT.txt|RESULT.md",
        help="empty a text output file in the active project directory, then exit",
    )
    parser.add_argument(
        "-m",
        "--merge",
        dest="merge_values",
        nargs="+",
        metavar="A",
        help="merge A1 and A2 (a project .txt/.md file or literal text) into optional D; default: merged.txt",
    )
    parser.add_argument("--model", help="Ollama model; overrides the task model")
    seed_group = parser.add_mutually_exclusive_group()
    seed_group.add_argument("--seed", type=int, help="Ollama seed; overrides task and shared options")
    seed_group.add_argument(
        "--seed_rnd",
        action="store_true",
        help="generate and use a random Ollama seed from 1 to 999999",
    )
    parser.add_argument("--temp", type=non_negative_float, metavar="TEMPERATURE", help="Ollama temperature")
    parser.add_argument("--num-predict", type=positive_integer, metavar="TOKENS", help="maximum output tokens")
    parser.add_argument("--num-ctx", type=positive_integer, metavar="TOKENS", help="Ollama context window")
    parser.add_argument(
        "--repeat-penalty",
        type=positive_float,
        metavar="VALUE",
        help="Ollama repeat penalty",
    )
    direction_group = parser.add_mutually_exclusive_group()
    direction_group.add_argument(
        "--direction",
        "--translation-direction",
        dest="translation_direction",
        choices=tuple(TRANSLATION_INSTRUCTIONS),
        help="translation direction for a translate task: c2a or e2c",
    )
    direction_group.add_argument(
        "-c2a",
        "--c2a",
        dest="translation_direction",
        action="store_const",
        const="c2a",
        help="legacy shorthand for --direction c2a",
    )
    direction_group.add_argument(
        "-e2c",
        "--e2c",
        "-a2c",
        "--a2c",
        dest="translation_direction",
        action="store_const",
        const="e2c",
        help="legacy shorthand for --direction e2c (--a2c is also supported)",
    )
    parser.add_argument(
        "-s",
        "--system",
        "--status",
        dest="status",
        action="store_true",
        help="show project, shared Ollama, and selected task configuration",
    )
    connection_action_group = parser.add_mutually_exclusive_group()
    connection_action_group.add_argument(
        "--test",
        action="store_true",
        help="verbose diagnostic of the connection to the configured Ollama server",
    )
    connection_action_group.add_argument(
        "--list",
        dest="list_models",
        action="store_true",
        help="list models available from the configured Ollama server",
    )
    parser.add_argument(
        "-v",
        "--ver",
        "--version",
        action=VersionAction,
        help="show cli_ollama.py and all wrapper versions",
    )
    arguments = parser.parse_args()
    input_values = arguments.data
    arguments.input_prompt = None
    if input_values:
        if len(input_values) == 1:
            arguments.data = input_values[0]
        elif len(input_values) == 2 and input_values[1] == "-" and input_values[0].strip():
            arguments.data = "-"
            arguments.input_prompt = input_values[0]
        else:
            parser.error(
                "--input/--data accepts TEXT|FILE|-, or exactly PROMPT - for interactive input"
            )
    return arguments


def resolve_direct_file(path: str | Path, directory: Path, label: str) -> Path:
    """Resolve a file directly inside a configured directory."""

    resolved_directory = directory.resolve()
    candidate = Path(path)
    resolved_path = candidate.resolve() if candidate.is_absolute() else (resolved_directory / candidate).resolve()
    try:
        resolved_path.relative_to(resolved_directory)
    except ValueError as error:
        raise ValueError(f"The {label} must be inside {resolved_directory}.") from error
    if resolved_path.parent != resolved_directory:
        raise ValueError(f"The {label} must be directly in {resolved_directory}.")
    return resolved_path


def resolve_task_file(path: str | Path) -> Path:
    """Resolve a task configuration directly inside ``assistant/tasks``."""

    return resolve_direct_file(path, ASSISTANT_TASKS_DIR, "task configuration")


def load_task(path: Path) -> dict[str, object]:
    """Load a task JSON object without applying any runtime overrides."""

    task = load_json_object(path)
    if not task:
        raise ValueError(f"Task configuration is empty: {path}")
    return task


def resolve_assistant_path(
    reference: str,
    *,
    category: str,
    required: bool,
    source: str,
) -> Path | None:
    """Resolve one profile or capability below ``assistant/``.

    Bare IDs resolve to ``assistant/<category>/ID.md``. Legacy
    ``./skills/name.md`` task paths still work as aliases while old task files
    are migrated; they resolve to the matching profile or capability when the
    former directory no longer exists.
    """

    if not isinstance(reference, str) or not reference.strip():
        raise ValueError(f"The {source} {category} reference must be non-empty text.")
    candidate = Path(reference)
    if candidate.is_absolute():
        raise ValueError(f"The {source} {category} reference must be relative.")
    filename = candidate.name if candidate.suffix == ".md" else f"{candidate.name}.md"
    candidates: list[Path]
    if len(candidate.parts) == 1:
        candidates = [Path("assistant") / category / filename]
    else:
        candidates = [candidate]
        if candidate.parts[0].casefold() == "skills":
            legacy_relative = Path(*candidate.parts[1:])
            other_category = "profiles" if category == "capabilities" else "capabilities"
            candidates.extend(
                [
                    Path("assistant") / category / legacy_relative,
                    Path("assistant") / other_category / legacy_relative,
                ]
            )
    resolved_paths: list[Path] = []
    for relative_path in candidates:
        resolved_path = (PROJECT_DIR / relative_path).resolve()
        try:
            resolved_path.relative_to(PROJECT_DIR.resolve())
        except ValueError as error:
            raise ValueError(f"The {source} {category} file must be inside the application directory.") from error
        resolved_paths.append(resolved_path)
        if resolved_path.is_file():
            return resolved_path
    if required:
        raise ValueError(f"The {source} {category} file does not exist: {resolved_paths[0]}")
    return None


def read_assistant_instruction(
    reference: str,
    *,
    category: str,
    required: bool,
    source: str,
) -> str:
    """Return one profile or capability's non-empty text, or empty text for an optional miss."""

    component_path = resolve_assistant_path(
        reference,
        category=category,
        required=required,
        source=source,
    )
    if component_path is None:
        return ""
    try:
        return component_path.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        raise ValueError(f"Could not read {source} {category} file {component_path}: {error}") from error


def task_component_references(task: dict[str, object], singular: str, plural: str) -> list[str]:
    """Read one optional component field and its ordered plural counterpart."""

    references: list[str] = []
    singular_value = task.get(singular)
    if singular_value is not None:
        if not isinstance(singular_value, str) or not singular_value.strip():
            raise ValueError(f'The optional task "{singular}" field must be non-empty text.')
        references.append(singular_value)
    plural_value = task.get(plural)
    if plural_value is not None:
        if not isinstance(plural_value, list) or not all(
            isinstance(item, str) and item.strip() for item in plural_value
        ):
            raise ValueError(f'The optional task "{plural}" field must be a list of non-empty text IDs.')
        references.extend(plural_value)
    return references


def task_capability_references(task: dict[str, object]) -> list[str]:
    """Read modern capability fields followed by legacy skill fields."""

    references = task_component_references(task, "capability", "capabilities")
    references.extend(task_component_references(task, "skill", "skills"))
    return references


def apply_assistant_components(
    task: dict[str, object],
    extra_profiles: list[str] | None = None,
    extra_capabilities: list[str] | None = None,
    extra_legacy_skills: list[str] | None = None,
) -> dict[str, object]:
    """Prepend profiles and capabilities to the task's resolved system rules."""

    profile_parts = [
        read_assistant_instruction(reference, category="profiles", required=False, source="task")
        for reference in task_component_references(task, "profile", "profiles")
    ]
    capability_parts = [
        read_assistant_instruction(reference, category="capabilities", required=False, source="task")
        for reference in task_capability_references(task)
    ]
    for reference in extra_profiles or []:
        profile_parts.append(
            read_assistant_instruction(reference, category="profiles", required=True, source="CLI")
        )
    for reference in extra_capabilities or []:
        capability_parts.append(
            read_assistant_instruction(reference, category="capabilities", required=True, source="CLI")
        )
    for reference in extra_legacy_skills or []:
        legacy_part = read_assistant_instruction(
            reference,
            category="capabilities",
            required=False,
            source="CLI legacy skill",
        )
        if not legacy_part:
            legacy_part = read_assistant_instruction(
                reference,
                category="profiles",
                required=True,
                source="CLI legacy skill",
            )
            profile_parts.append(legacy_part)
        else:
            capability_parts.append(legacy_part)
    component_parts = [part for part in (*profile_parts, *capability_parts) if part]
    if not component_parts:
        return task

    resolved_task = task.copy()
    instruction = resolved_task.get("instruction", "")
    if not isinstance(instruction, str):
        raise ValueError('The "instruction" field in a task must be text.')
    resolved_task["instruction"] = "\n\n\n".join(
        (*component_parts, instruction) if instruction else component_parts
    )
    return resolved_task


def apply_skills(task: dict[str, object], extra_skills: list[str] | None = None) -> dict[str, object]:
    """Compatibility wrapper: legacy skills are now assistant capabilities."""

    return apply_assistant_components(task, extra_capabilities=extra_skills)


def apply_skill(task: dict[str, object]) -> dict[str, object]:
    """Compatibility wrapper for callers using the former singular skill API."""

    return apply_skills(task)


def load_sc_catalog() -> dict[str, dict[str, object]]:
    """Load the command catalog and return commands indexed by name and aliases."""

    catalog_path = PROJECT_DIR / "assistant" / "commands" / "sc.json"
    if not catalog_path.is_file():
        catalog_path = PROJECT_DIR / "sc.json"
    catalog = load_json_object(catalog_path)
    groups = catalog.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError(f'{catalog_path} must contain a non-empty "groups" list.')
    indexed_commands: dict[str, dict[str, object]] = {}
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("commands"), list):
            raise ValueError(f'Every group in {catalog_path} must contain a "commands" list.')
        for command in group["commands"]:
            if not isinstance(command, dict):
                raise ValueError(f"Every slash command in {catalog_path} must be a JSON object.")
            name = command.get("sc")
            kind = command.get("kind")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f'Every slash command in {catalog_path} requires non-empty "sc" text.')
            if kind not in {"action", "artifact", "modifier", "persona_modifier"}:
                raise ValueError(f"Slash command {name!r} has an unsupported kind: {kind!r}")
            for key in ("sc_en", "sc_cz"):
                if not isinstance(command.get(key), str) or not command[key].strip():
                    raise ValueError(f"Slash command {name!r} requires non-empty {key!r} text.")
            aliases = command.get("aliases", [])
            if not isinstance(aliases, list) or not all(isinstance(alias, str) and alias.strip() for alias in aliases):
                raise ValueError(f"Slash command {name!r} has invalid aliases.")
            language_neutral = command.get("language_neutral", False)
            if not isinstance(language_neutral, bool):
                raise ValueError(f"Slash command {name!r} has invalid language_neutral value.")
            for raw_name in (name, *aliases):
                normalized_name = raw_name.removeprefix("/").casefold()
                if normalized_name in indexed_commands:
                    raise ValueError(f"Duplicate slash command or alias in {catalog_path}: {raw_name!r}")
                indexed_commands[normalized_name] = command
    return indexed_commands


def resolve_sc_commands(arguments: argparse.Namespace) -> tuple[list[dict[str, object]], str | None]:
    """Resolve requested slash commands and reject ambiguous command stacks."""

    requested_names = getattr(arguments, "sc_commands", None) or []
    language = getattr(arguments, "sc_language", None)
    if requested_names and language is None:
        commands_by_name = load_sc_catalog()
        requested_commands = []
        for raw_name in requested_names:
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise ValueError("Every --sc value must be non-empty text.")
            command = commands_by_name.get(raw_name.strip().removeprefix("/").casefold())
            if command is None:
                raise ValueError(f"Unknown slash command: {raw_name!r}")
            requested_commands.append(command)
        if not all(command.get("language_neutral", False) for command in requested_commands):
            raise ValueError("Specify --sc-cz, --sc-en, or --sc-es when using --sc.")
    if language is None:
        if not requested_names:
            return [], None

    commands_by_name = load_sc_catalog()
    raw_names = requested_names or ["explain"]
    resolved_commands: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for raw_name in raw_names:
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("Every --sc value must be non-empty text.")
        normalized_name = raw_name.strip().removeprefix("/").casefold()
        command = commands_by_name.get(normalized_name)
        if command is None:
            raise ValueError(f"Unknown slash command: {raw_name!r}")
        canonical_name = str(command["sc"])
        if canonical_name not in seen_names:
            resolved_commands.append(command)
            seen_names.add(canonical_name)

    primary_commands = [command for command in resolved_commands if command["kind"] in {"action", "artifact"}]
    if len(primary_commands) > 1:
        names = ", ".join(str(command["sc"]) for command in primary_commands)
        raise ValueError(f"Only one primary slash command may be used per task: {names}")
    persona_commands = [command for command in resolved_commands if command["kind"] == "persona_modifier"]
    if len(persona_commands) > 1:
        names = ", ".join(str(command["sc"]) for command in persona_commands)
        raise ValueError(f"Only one persona slash command may be used per task: {names}")

    return resolved_commands, language


def apply_sc_commands(
    task: dict[str, object],
    commands: list[dict[str, object]],
    language: str | None,
) -> dict[str, object]:
    """Append selected slash-command rules after task rules and before ``--rules``."""

    if language is None and not commands:
        return task
    rule_key = f"sc_{language}" if language is not None else "sc_en"
    command_rules = [
        str(command.get(rule_key) or command["sc_en"]).strip()
        for command in commands
        if command["sc"] != "explain"
    ]
    has_language_neutral_command = any(command.get("language_neutral", False) for command in commands)
    language_rule = ""
    if language is not None and not has_language_neutral_command:
        language_rule = {
            "cz": "Odpovídej pouze česky.",
            "en": "Respond only in English.",
            "es": "Responde solo en español.",
        }[language]
    instruction = task.get("instruction", "")
    if not isinstance(instruction, str):
        raise ValueError('The "instruction" field in a task must be text.')
    resolved_task = task.copy()
    resolved_task["instruction"] = "\n\n\n".join(
        part for part in (instruction, *command_rules, language_rule) if part
    )
    if language is not None:
        resolved_task["sc_language"] = language
    resolved_task["slash_commands"] = [str(command["sc"]) for command in commands]
    return resolved_task


def read_data(path: Path) -> str:
    """Read a non-empty UTF-8 data file used as the task prompt."""

    try:
        data = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ValueError(f"Could not read data file {path}: {error}") from error
    if not data.strip():
        raise ValueError(f"Data file is empty: {path}")
    return data


def read_text_value(value: str, project_directory: Path, label: str) -> str:
    """Return literal text, or the contents of an existing direct project file.

    A file takes precedence when its name exists directly in the active project
    directory. This preserves file-based CLI usage while allowing inline text.
    """

    if not value.strip():
        raise ValueError(f"The {label} must not be empty.")
    if Path(value).name != value:
        return value
    candidate = resolve_direct_file(value, project_directory, label)
    if candidate.is_file():
        return read_data(candidate)
    return value


def read_standard_input(label: str) -> str:
    """Read one interactive line or all piped standard input, rejecting empty text."""

    try:
        if sys.stdin.isatty():
            # Flow logging captures a child process's stdout line by line.
            # Print the label as its own flushed line so it remains visible
            # before input() waits for the terminal response.
            Terminal().y(f"{label}:")
            sys.stdout.flush()
            data = input()
        else:
            data = sys.stdin.read()
    except EOFError as error:
        raise ValueError(f"No {label.casefold()} was provided on standard input.") from error
    if not data.strip():
        raise ValueError(f"The {label.casefold()} from standard input must not be empty.")
    return data


def read_prompt_input(value: str, project_directory: Path, prompt_label: str | None = None) -> str:
    """Read a prompt value, reserving a lone hyphen for standard input."""

    return (
        read_standard_input(prompt_label or "Prompt input")
        if value == "-"
        else read_text_value(value, project_directory, "data")
    )


def append_runtime_rules(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
) -> dict[str, object]:
    """Append each ``--rules`` value to the task's resolved system rules."""

    values = getattr(arguments, "rules", None) or []
    if not values:
        return task
    rule_parts = [read_text_value(value, project_directory, "rules") for value in values]
    instruction = task.get("instruction", "")
    if not isinstance(instruction, str):
        raise ValueError('The "instruction" field in a task must be text.')
    resolved_task = task.copy()
    resolved_task["instruction"] = "\n\n\n".join(part for part in (instruction, *rule_parts) if part)
    return resolved_task


def append_reference_context(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
) -> dict[str, object]:
    """Attach explicit project files to the prompt with stable source labels."""

    filenames = getattr(arguments, "context_files", None) or []
    if not filenames:
        return task
    prompt = task.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("A task needs a non-empty prompt or --input before --context can be used.")
    references = []
    for filename in filenames:
        context_path = resolve_direct_file(filename, project_directory, "context file")
        if not context_path.is_file():
            raise ValueError(f"The context file does not exist: {context_path}")
        references.append(
            f"[REFERENCE FILE: {context_path.name}]\n"
            f"{read_data(context_path)}\n"
            "[END REFERENCE FILE]"
        )
    resolved_task = task.copy()
    resolved_task["prompt"] = "\n\n".join(
        (
            "# Reference context",
            *references,
            "# Current input",
            f"[INPUT]\n{prompt}\n[END INPUT]",
        )
    )
    return resolved_task


def resolve_text_file(
    filename: str,
    project_directory: Path,
    label: str,
    *,
    must_exist: bool,
) -> Path:
    """Resolve a plain-text or Markdown file directly in the active project directory."""

    path = resolve_direct_file(filename, project_directory, label)
    if path.suffix.casefold() not in TEXT_FILE_EXTENSIONS:
        extensions = " or ".join(TEXT_FILE_EXTENSIONS)
        raise ValueError(f"The {label} must have a {extensions} extension: {path}")
    if must_exist and not path.is_file():
        raise ValueError(f"The {label} does not exist: {path}")
    return path


def prepare_merge(
    values: list[str], project_directory: Path
) -> tuple[str, Path]:
    """Read two merge inputs and resolve their optional text-file destination.

    The first input is always an existing ``.txt`` or ``.md`` file in the active project.
    The second keeps the same file-first behavior as ``--data`` and therefore
    may be either another direct project file or literal text.
    """

    if len(values) not in {2, 3}:
        raise ValueError("--merge requires A1 A2 and accepts an optional destination D.")
    first_path = resolve_text_file(values[0], project_directory, "first merge input", must_exist=True)
    first_content = read_data(first_path)
    second_content = read_text_value(values[1], project_directory, "second merge input")
    output_name = values[2] if len(values) == 3 else "merged.txt"
    output_path = resolve_text_file(output_name, project_directory, "merge output file", must_exist=False)
    return f"{first_content.rstrip()}\n\n{second_content.lstrip()}", output_path


def apply_overrides(
    task: dict[str, object],
    arguments: argparse.Namespace,
    data: str | None,
    instruction: str | None = None,
) -> dict[str, object]:
    """Apply text-file and CLI values after the shared and task configuration layers."""

    resolved_task = task.copy()
    if data is not None:
        resolved_task["prompt"] = data
    if instruction is not None:
        resolved_task["instruction"] = instruction
    if arguments.model:
        resolved_task["model"] = arguments.model

    options = dict(resolved_task.get("options", {}))
    if arguments.seed_rnd:
        options["seed"] = secrets.randbelow(999_999) + 1
    for argument_name, option_name in (
        ("seed", "seed"),
        ("temp", "temperature"),
        ("num_predict", "num_predict"),
        ("num_ctx", "num_ctx"),
        ("repeat_penalty", "repeat_penalty"),
    ):
        value = getattr(arguments, argument_name)
        if value is not None:
            options[option_name] = value
    if options:
        resolved_task["options"] = options
    return resolved_task


def materialize_zero_seed(task: dict[str, object], app: object) -> dict[str, object]:
    """Replace an effective seed of zero with one generated random seed.

    Zero is the configuration equivalent of ``--seed_rnd``.  Perform this
    after all configuration layers have been merged, so it works whether zero
    came from ``ollama.json``, a task, or a CLI ``--seed 0`` override.  The
    generated value is stored in the resolved task to keep logging, the Ollama
    request, and the optional database record in agreement.
    """

    effective_options = app.effective_task_options(task)  # type: ignore[attr-defined]
    if effective_options["seed"] != 0:
        return task

    resolved_task = task.copy()
    options = dict(resolved_task.get("options", {}))
    options["seed"] = secrets.randbelow(999_999) + 1
    resolved_task["options"] = options
    return resolved_task


def get_task_kind(task: dict[str, object]) -> str:
    """Return the task kind, defaulting older task files to a prompt task."""

    kind = task.get("type", "prompt")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError('The task "type" field must be non-empty text.')
    if kind not in {"prompt", "translate", "ocr", "describe"}:
        raise ValueError(f"Unsupported task type: {kind!r}")
    return kind


def prepare_prompt_task(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
) -> tuple[dict[str, object], Path | None]:
    """Prepare a regular prompt task and its optional response file."""

    if arguments.input_file:
        raise ValueError("The --in option is available only for translate, OCR, and describe tasks.")
    if getattr(arguments, "literal_text", None) is not None:
        raise ValueError("The --text option is available only for a translate task.")
    if arguments.translation_direction:
        raise ValueError("The --direction, --c2a, and --e2c options are available only for a translate task.")
    data = (
        read_prompt_input(arguments.data, project_directory, getattr(arguments, "input_prompt", None))
        if arguments.data
        else None
    )
    instruction = (
        read_text_value(arguments.instruction, project_directory, "instruction") if arguments.instruction else None
    )
    output_filename = arguments.out or task.get("default_output_file")
    if output_filename is not None and (not isinstance(output_filename, str) or not output_filename.strip()):
        raise ValueError('The prompt task "default_output_file" field must be non-empty text.')
    output_path = (
        resolve_direct_file(output_filename, project_directory, "output file")
        if output_filename
        else None
    )
    resolved_task = apply_overrides(task, arguments, data, instruction)
    return append_reference_context(resolved_task, arguments, project_directory), output_path


def prepare_translate_task(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
) -> tuple[dict[str, object], Path]:
    """Build a single translation task from task defaults and text-file overrides."""

    if arguments.data:
        raise ValueError("Use --in rather than --input/--data for a translate task.")
    literal_text = getattr(arguments, "literal_text", None)
    if literal_text is not None and arguments.input_file:
        raise ValueError("Use either --in or --text for a translate task, not both.")
    if literal_text is not None and (not isinstance(literal_text, str) or not literal_text.strip()):
        raise ValueError("The --text value for a translate task must be non-empty text.")
    for field in ("default_input_file", "default_output_file"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f'Translate task requires a non-empty "{field}" field.')
    configured_direction = task.get("default_direction", "c2a")
    if configured_direction not in TRANSLATION_INSTRUCTIONS:
        raise ValueError('The translate task "default_direction" must be "c2a" or "e2c".')

    direction = arguments.translation_direction or configured_direction
    default_input_key = "default_input_file_e2c" if direction == "e2c" else "default_input_file"
    default_input_file = task.get(default_input_key)
    if not isinstance(default_input_file, str) or not default_input_file.strip():
        raise ValueError(f'Translate task requires a non-empty "{default_input_key}" field.')
    input_filename = arguments.input_file or default_input_file
    output_filename = arguments.out or str(task["default_output_file"])
    input_data = None
    if literal_text is None:
        input_data = (
            read_standard_input("Translation input")
            if input_filename == "-"
            else read_data(
                resolve_text_file(input_filename, project_directory, "translation input file", must_exist=True)
            )
        )
    output_path = resolve_text_file(output_filename, project_directory, "translation output file", must_exist=False)
    translation_task = {
        **task,
        "prompt": literal_text if literal_text is not None else input_data,
        "instruction": TRANSLATION_INSTRUCTIONS[direction],
    }
    instruction = (
        read_text_value(arguments.instruction, project_directory, "replacement rules")
        if arguments.instruction
        else None
    )
    resolved_task = apply_overrides(translation_task, arguments, None, instruction)
    return append_reference_context(resolved_task, arguments, project_directory), output_path


def prepare_image_task(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
    *,
    kind: str,
) -> tuple[dict[str, object], Path, Path]:
    """Prepare one OCR or describe task with a project-root image and text output."""

    if arguments.data:
        raise ValueError("The --input/--data option is available only for a prompt task.")
    if arguments.translation_direction:
        raise ValueError("The --direction, --c2a, and --e2c options are available only for a translate task.")
    for field in ("default_input_file", "default_output_file"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise ValueError(f'{kind} task requires a non-empty "{field}" field.')
    configured_extensions = task.get("image_extensions", DEFAULT_IMAGE_EXTENSIONS)
    if (
        not isinstance(configured_extensions, (list, set))
        or not all(isinstance(extension, str) and extension.startswith(".") for extension in configured_extensions)
    ):
        raise ValueError(f'The {kind} task "image_extensions" field must be a list of extensions.')
    supported_extensions = {str(extension) for extension in configured_extensions}
    fallback_extensions = {".png"} if kind == "describe" else None
    image_path = resolve_image_path(
        arguments.input_file,
        project_directory,
        str(task["default_input_file"]),
        supported_extensions,
        fallback_extensions=fallback_extensions,
    )
    output_filename = arguments.out or str(task["default_output_file"])
    output_path = resolve_text_file(output_filename, project_directory, f"{kind} output file", must_exist=False)
    instruction = (
        read_text_value(arguments.instruction, project_directory, "replacement rules")
        if arguments.instruction
        else None
    )
    resolved_task = apply_overrides(task, arguments, None, instruction)
    resolved_task = append_reference_context(resolved_task, arguments, project_directory)
    return resolved_task, image_path, output_path


def print_status(
    task_path: Path | None,
    project_directory: Path,
    project_config: dict[str, object],
) -> None:
    """Print the configuration layers used by the selected task."""

    terminal = Terminal()
    print(terminal.color("y", "Task status"))
    print(f"{terminal.color('g', 'Project configuration:')} {json.dumps(project_config, ensure_ascii=False)}")
    print(f"{terminal.color('g', 'Ollama configuration:')} {json.dumps(load_json_object(OLLAMA_CONFIG_PATH), ensure_ascii=False)}")
    task_label = str(task_path) if task_path is not None else "not selected"
    print(f"{terminal.color('g', 'Task configuration:')} {task_label}")
    print(f"{terminal.color('g', 'Project directory:')} {project_directory}")
    print()
    print_system_info(project_directory)


def print_resolved_task_options(
    task_kind: str,
    task: dict[str, object],
    app: object,
    arguments: argparse.Namespace,
) -> None:
    """Print the effective model settings when project logging is enabled."""

    effective_options = app.effective_task_options(task)  # type: ignore[attr-defined]
    overrides = []
    for option_name, argument_name in (
        ("--model", "model"),
        ("--seed", "seed"),
        ("--temp", "temp"),
        ("--num-predict", "num_predict"),
        ("--num-ctx", "num_ctx"),
        ("--repeat-penalty", "repeat_penalty"),
    ):
        if getattr(arguments, argument_name) is not None:
            overrides.append(option_name)
    if arguments.seed_rnd:
        overrides.append("--seed_rnd")
    if arguments.translation_direction:
        overrides.append(f"--{arguments.translation_direction}")
    if arguments.instruction:
        overrides.append("--instruction")

    print(
        f"Task: {task_kind} | Model: {task['model']} | Seed: {effective_options['seed']} | "
        f"Temperature: {effective_options['temperature']}"
    )
    details = (
        f"num_predict: {effective_options['num_predict']} | "
        f"num_ctx: {effective_options['num_ctx']} | "
        f"repeat_penalty: {effective_options['repeat_penalty']} | "
        f"think: {str(task.get('think', False)).lower()}"
    )
    if overrides:
        details += f" | CLI overrides: {', '.join(overrides)}"
    print(details)


def build_task_state(
    task: dict[str, object],
    *,
    task_kind: str,
    effective_options: dict[str, object],
    debug_enabled: bool,
    output_path: Path | None,
    image_path: Path | None,
    project_directory: Path,
) -> dict[str, object]:
    """Return the complete resolved task state stored with a DB record.

    Keep the task configuration as it was prepared for this run, while also
    recording values inherited from ``ollama.json``.  This makes a database
    record self-contained even when its source task file or shared defaults
    change later.
    """

    task_state = dict(task)
    task_state["type"] = task_kind
    task_state["debug"] = debug_enabled
    task_state["think"] = task.get("think", False)
    task_state["effective_options"] = dict(effective_options)
    if output_path is not None:
        task_state["output_file"] = str(output_path.relative_to(project_directory))
    if image_path is not None:
        task_state["input_file"] = str(image_path.relative_to(project_directory))
    return task_state


def run_connection_test(project_debug: bool | None) -> int:
    """Run the standalone Ollama connection diagnostic without loading a task."""

    from lib.wrapp_ollama import ollama_api

    try:
        app = ollama_api(
            config_path=OLLAMA_CONFIG_PATH,
            debug_enabled=project_debug,
            time_trace=True,
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: Cannot load Ollama configuration: {error}")
        return 2

    return app.test_connection()


def run_model_list(project_debug: bool | None) -> int:
    """List models from the configured Ollama server without running a task."""

    from lib.wrapp_ollama import ollama_api

    try:
        app = ollama_api(
            config_path=OLLAMA_CONFIG_PATH,
            debug_enabled=project_debug,
            time_trace=True,
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: Cannot load Ollama configuration: {error}")
        return 2

    return app.list_models()


def run_command(
    arguments: argparse.Namespace,
    project_config: dict[str, object],
    project_directory: Path,
    log_enabled: bool,
    project_debug: bool | None,
    db_enabled: bool,
    db_selector: str,
) -> int:
    """Run one CLI command with its project directory already resolved."""

    if arguments.echo_message is not None:
        Terminal().print("y", arguments.echo_message)
        return 0
    merge_values = getattr(arguments, "merge_values", None)
    if merge_values is not None:
        try:
            merged_text, output_path = prepare_merge(merge_values, project_directory)
            output_path.write_text(merged_text, encoding="utf-8")
        except (OSError, ValueError) as error:
            print(f"ERROR: {error}")
            return 2
        print(f"Content merged: {output_path}")
        return 0
    if arguments.test:
        return run_connection_test(project_debug)
    if arguments.list_models:
        return run_model_list(project_debug)
    if arguments.status:
        try:
            task_path = None
            if arguments.task_type:
                task_path = resolve_task_file(arguments.task_type)
                if not task_path.is_file():
                    raise ValueError(f"Task configuration does not exist: {task_path}")
            print_status(task_path, project_directory, project_config)
        except ValueError as error:
            print(f"ERROR: {error}")
            return 2
        return 0
    if not arguments.task_type:
        print("ERROR: Specify --type TASK.json to run a task.")
        return 2

    try:
        task_path = resolve_task_file(arguments.task_type)
        if not task_path.is_file():
            raise ValueError(f"Task configuration does not exist: {task_path}")
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    try:
        task = load_task(task_path)
        task_kind = get_task_kind(task)
        image_path: Path | None = None
        if task_kind == "translate":
            resolved_task, output_path = prepare_translate_task(task, arguments, project_directory)
        elif task_kind in {"ocr", "describe"}:
            resolved_task, image_path, output_path = prepare_image_task(
                task,
                arguments,
                project_directory,
                kind=task_kind,
            )
        else:
            resolved_task, output_path = prepare_prompt_task(task, arguments, project_directory)
        resolved_task = apply_assistant_components(
            resolved_task,
            extra_profiles=getattr(arguments, "extra_profiles", None) or [],
            extra_capabilities=getattr(arguments, "extra_capabilities", None) or [],
            extra_legacy_skills=getattr(arguments, "extra_legacy_skills", None) or [],
        )
        sc_commands, sc_language = resolve_sc_commands(arguments)
        resolved_task = apply_sc_commands(resolved_task, sc_commands, sc_language)
        resolved_task = append_runtime_rules(resolved_task, arguments, project_directory)
        if arguments.append_out and output_path is None:
            raise ValueError("The --append-out option requires --out RESULT.txt.")
        if arguments.out_header is not None and output_path is None:
            raise ValueError("The --out-header option requires --out RESULT.txt.")
        if (arguments.append_out or arguments.out_header is not None) and task_kind != "prompt":
            raise ValueError("The --append-out and --out-header options are available only for a prompt task.")
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    from lib.wrapp_ollama import ollama_api

    response_parts: list[str] = []

    def capture_response(text: str) -> None:
        """Keep only final response chunks; Ollama thinking never uses this callback."""

        response_parts.append(text)

    app = ollama_api(
        config_path=OLLAMA_CONFIG_PATH,
        debug_enabled=project_debug,
        on_response_text=capture_response,
        time_trace=True,
    )
    resolved_task = materialize_zero_seed(resolved_task, app)
    if getattr(arguments, "dry_run", False):
        print(
            json.dumps(
                app.build_task_payload(resolved_task, task_kind, image_path=image_path),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if app.effective_task_debug_enabled(resolved_task):
        print_resolved_task_options(task_kind, resolved_task, app, arguments)
    if task_kind == "ocr":
        assert image_path is not None
        return_code = app.run_ocr_task(resolved_task, image_path, output_path)
    elif task_kind == "describe":
        assert image_path is not None
        return_code = app.run_describe_task(resolved_task, image_path, output_path)
    else:
        return_code = app.run_task(
            resolved_task,
            response_path=output_path,
            append_response=arguments.append_out,
            response_header=arguments.out_header,
        )

    if return_code != 0 or not db_enabled:
        return return_code

    answer = "".join(response_parts)
    if not answer:
        print("ERROR: Completed task did not return a final response for database storage.")
        return 1
    try:
        from lib.wrapp_db import (
            DEFAULT_TASKS_DATABASE_PATH,
            DEFAULT_TASKS_SCHEMA_PATH,
            TaskDatabaseError,
            record_task_output,
        )

        project_label = str(project_directory.resolve().relative_to(PROJECT_DIR.resolve()))
        task_label = task_path.name
        effective_options = dict(app.effective_task_options(resolved_task))
        parameters = dict(effective_options)
        parameters["think"] = resolved_task.get("think", False)
        parameters["task_kind"] = task_kind
        if output_path is not None:
            parameters["output_file"] = str(output_path.relative_to(project_directory))
        if image_path is not None:
            parameters["input_file"] = str(image_path.relative_to(project_directory))
        parameters["task_state"] = build_task_state(
            resolved_task,
            task_kind=task_kind,
            effective_options=effective_options,
            debug_enabled=app.effective_task_debug_enabled(resolved_task),
            output_path=output_path,
            image_path=image_path,
            project_directory=project_directory,
        )
        usage = getattr(app, "last_usage", None)
        usage_key2 = (
            json.dumps(usage, ensure_ascii=False, sort_keys=True)
            if isinstance(usage, dict) and usage
            else None
        )
        uid = record_task_output(
            PROJECT_DIR / DEFAULT_TASKS_DATABASE_PATH,
            PROJECT_DIR / DEFAULT_TASKS_SCHEMA_PATH,
            project=project_label,
            selector=db_selector,
            task=task_label,
            model=str(resolved_task["model"]),
            parameters=parameters,
            prompt=str(resolved_task["prompt"]),
            instruction=resolved_task.get("instruction") if isinstance(resolved_task.get("instruction"), str) else None,
            answer=answer,
            key2=usage_key2,
        )
        print(f"Task recorded in data/tasks.db: {uid}")
    except (OSError, ValueError, TaskDatabaseError) as error:
        print(f"ERROR: Completed task could not be recorded in data/tasks.db: {error}")
        return 1
    return return_code


def main() -> int:
    """Resolve configuration layers and run the requested text task."""

    arguments = parse_arguments()
    try:
        project_config = load_project_config(PROJECT_DIR)
        selector = getattr(arguments, "selector", None)
        if arguments.project or arguments.debug is not None or selector is not None:
            updated_project_config = project_config.copy()
            if arguments.project:
                updated_project_config["subdir"] = arguments.project
            if arguments.debug is not None:
                updated_project_config["debug"] = arguments.debug
            if selector is not None:
                updated_project_config["selector"] = selector
            get_project_directory(PROJECT_DIR, updated_project_config)
            (PROJECT_DIR / "project.json").write_text(
                json.dumps(updated_project_config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            project_config = load_project_config(PROJECT_DIR)
        project_directory = get_project_directory(PROJECT_DIR, project_config)
        log_enabled = read_log_enabled(PROJECT_DIR / "project.json")
        project_debug = read_debug_enabled(PROJECT_DIR / "project.json")
        from lib.wrapp_db import read_db_enabled, read_db_selector

        db_enabled = read_db_enabled(project_config)
        db_selector = read_db_selector(project_config)
        if arguments.clear_log:
            (project_directory / "log.txt").write_text("", encoding="utf-8")
        if arguments.clear_out:
            clear_output_path = resolve_text_file(
                arguments.clear_out,
                project_directory,
                "output file",
                must_exist=False,
            )
            clear_output_path.write_text("", encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2

    if arguments.project:
        print(f"Project directory selected and saved: {project_directory}")
    if arguments.debug is not None:
        print(f"Project debug setting saved: {str(arguments.debug).lower()}")
    if selector is not None:
        print(f"Project selector saved: {selector}")
    if arguments.project or arguments.debug is not None or selector is not None or arguments.clear_log or arguments.clear_out:
        return 0

    with console_log(project_directory, "cli_ollama.py", log_enabled):
        return run_command(
            arguments,
            project_config,
            project_directory,
            log_enabled,
            project_debug,
            db_enabled,
            db_selector,
        )


if __name__ == "__main__":
    raise SystemExit(main())

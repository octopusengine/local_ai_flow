"""Run a typed text task through the shared local Ollama configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.wrapp_ffmpeg import __version__ as WRAPP_FFMPEG_VERSION
from lib.wrapp_img import __version__ as WRAPP_IMG_VERSION
from lib.wrapp_img import resolve_image_path
from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_json_object,
    load_project_config,
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
OLLAMA_CONFIG_PATH = PROJECT_DIR / "lib" / "ollama.json"
DEFAULT_TYPE_FILENAME = "task_test.json"
DEFAULT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
TRANSLATION_INSTRUCTIONS = {
    "c2a": "Translate from Czech to English. Return only the translation.",
    "e2c": "Translate from English to Czech. Return only the translation.",
}
__version__ = "0.3"
MODULE_VERSIONS = (
    ("wrapp_log", WRAPP_LOG_VERSION),
    ("wrapp_ffmpeg", WRAPP_FFMPEG_VERSION),
    ("wrapp_img", WRAPP_IMG_VERSION),
    ("wrapp_ollama", WRAPP_OLLAMA_VERSION),
    ("wrapp_piper", WRAPP_PIPER_VERSION),
    ("wrapp_terminal", WRAPP_TERMINAL_VERSION),
    ("wrapp_system", WRAPP_SYSTEM_VERSION),
    ("wrapp_whisper", WRAPP_WHISPER_VERSION),
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


def parse_arguments() -> argparse.Namespace:
    """Parse a task type, optional data file, and highest-priority overrides."""

    parser = argparse.ArgumentParser(
        description=(
            "Run a text task from task_*.json through the shared lib/ollama.json configuration. "
            "Task settings override shared defaults; command-line options override the task."
        )
    )
    parser.add_argument(
        "--type",
        dest="task_type",
        default=DEFAULT_TYPE_FILENAME,
        metavar="TASK.json",
        help=f"task configuration in the project root (default: {DEFAULT_TYPE_FILENAME})",
    )
    parser.add_argument(
        "--data",
        metavar="TEXT.txt",
        help="UTF-8 prompt data file in the active project directory; overrides the task prompt",
    )
    parser.add_argument(
        "--in",
        dest="input_file",
        metavar="FILE",
        help="input file in the active project directory; overrides default_input_file",
    )
    parser.add_argument(
        "--out",
        metavar="RESULT.txt",
        help="optional response file in the active project directory",
    )
    parser.add_argument("--model", help="Ollama model; overrides the task model")
    parser.add_argument("--seed", type=int, help="Ollama seed; overrides task and shared options")
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
        "-c2a",
        "--c2a",
        dest="translation_direction",
        action="store_const",
        const="c2a",
        help="translate Czech to English",
    )
    direction_group.add_argument(
        "-e2c",
        "--e2c",
        "-a2c",
        "--a2c",
        dest="translation_direction",
        action="store_const",
        const="e2c",
        help="translate English to Czech (--a2c is a legacy alias)",
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
    return parser.parse_args()


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


def load_task(path: Path) -> dict[str, object]:
    """Load a task JSON object without applying any runtime overrides."""

    task = load_json_object(path)
    if not task:
        raise ValueError(f"Task configuration is empty: {path}")
    return task


def read_data(path: Path) -> str:
    """Read a non-empty UTF-8 data file used as the task prompt."""

    try:
        data = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not read data file {path}: {error}") from error
    if not data.strip():
        raise ValueError(f"Data file is empty: {path}")
    return data


def resolve_text_file(
    filename: str,
    project_directory: Path,
    label: str,
    *,
    must_exist: bool,
) -> Path:
    """Resolve a text file directly in the active project directory."""

    path = resolve_direct_file(filename, project_directory, label)
    if path.suffix.casefold() != ".txt":
        raise ValueError(f"The {label} must have a .txt extension: {path}")
    if must_exist and not path.is_file():
        raise ValueError(f"The {label} does not exist: {path}")
    return path


def apply_overrides(task: dict[str, object], arguments: argparse.Namespace, data: str | None) -> dict[str, object]:
    """Apply data and CLI values after the shared and task configuration layers."""

    resolved_task = task.copy()
    if data is not None:
        resolved_task["prompt"] = data
    if arguments.model:
        resolved_task["model"] = arguments.model

    options = dict(resolved_task.get("options", {}))
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
    if arguments.translation_direction:
        raise ValueError("The --c2a and --a2c options are available only for a translate task.")
    data_path = resolve_direct_file(arguments.data, project_directory, "data file") if arguments.data else None
    data = read_data(data_path) if data_path else None
    output_path = resolve_direct_file(arguments.out, project_directory, "output file") if arguments.out else None
    return apply_overrides(task, arguments, data), output_path


def prepare_translate_task(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
) -> tuple[dict[str, object], Path]:
    """Build a single translation task from task defaults and text-file overrides."""

    if arguments.data:
        raise ValueError("Use --in rather than --data for a translate task.")
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
    input_path = resolve_text_file(input_filename, project_directory, "translation input file", must_exist=True)
    output_path = resolve_text_file(output_filename, project_directory, "translation output file", must_exist=False)
    translation_task = {
        **task,
        "prompt": read_data(input_path),
        "instruction": TRANSLATION_INSTRUCTIONS[direction],
    }
    return apply_overrides(translation_task, arguments, None), output_path


def prepare_image_task(
    task: dict[str, object],
    arguments: argparse.Namespace,
    project_directory: Path,
    *,
    kind: str,
) -> tuple[dict[str, object], Path, Path]:
    """Prepare one OCR or describe task with a project-root image and text output."""

    if arguments.data:
        raise ValueError("The --data option is available only for a prompt task.")
    if arguments.translation_direction:
        raise ValueError("The --c2a and --e2c options are available only for a translate task.")
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
    return apply_overrides(task, arguments, None), image_path, output_path


def print_status(task_path: Path, project_directory: Path) -> None:
    """Print the configuration layers used by the selected task."""

    terminal = Terminal()
    print(terminal.color("y", "Task status"))
    print(f"{terminal.color('g', 'Project configuration:')} {json.dumps(load_project_config(PROJECT_DIR), ensure_ascii=False)}")
    print(f"{terminal.color('g', 'Ollama configuration:')} {json.dumps(load_json_object(OLLAMA_CONFIG_PATH), ensure_ascii=False)}")
    print(f"{terminal.color('g', 'Task configuration:')} {task_path}")
    print(f"{terminal.color('g', 'Project directory:')} {project_directory}")
    print()
    print_system_info(project_directory)


def run_connection_test() -> int:
    """Run the standalone Ollama connection diagnostic without loading a task."""

    from lib.wrapp_ollama import ollama_api

    try:
        app = ollama_api(config_path=OLLAMA_CONFIG_PATH)
    except (OSError, ValueError) as error:
        print(f"ERROR: Cannot load Ollama configuration: {error}")
        return 2

    return app.test_connection()


def run_model_list() -> int:
    """List models from the configured Ollama server without running a task."""

    from lib.wrapp_ollama import ollama_api

    try:
        app = ollama_api(config_path=OLLAMA_CONFIG_PATH)
    except (OSError, ValueError) as error:
        print(f"ERROR: Cannot load Ollama configuration: {error}")
        return 2

    return app.list_models()


def main() -> int:
    """Resolve configuration layers and run the requested text task."""

    arguments = parse_arguments()
    try:
        project_config = load_project_config(PROJECT_DIR)
        project_directory = get_project_directory(PROJECT_DIR, project_config)
        log_enabled = read_log_enabled(PROJECT_DIR / "project.json")
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    if arguments.test:
        with console_log(project_directory, "cli_ollama.py", log_enabled):
            return run_connection_test()
    if arguments.list_models:
        with console_log(project_directory, "cli_ollama.py", log_enabled):
            return run_model_list()

    try:
        task_path = resolve_direct_file(arguments.task_type, PROJECT_DIR, "task configuration")
        if not task_path.is_file():
            raise ValueError(f"Task configuration does not exist: {task_path}")
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    if arguments.status:
        try:
            print_status(task_path, project_directory)
        except ValueError as error:
            print(f"ERROR: {error}")
            return 2
        return 0

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
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    with console_log(project_directory, "cli_ollama.py", log_enabled):
        from lib.wrapp_ollama import ollama_api

        app = ollama_api(config_path=OLLAMA_CONFIG_PATH)
        if task_kind == "ocr":
            assert image_path is not None
            return app.run_ocr_task(resolved_task, image_path, output_path)
        if task_kind == "describe":
            assert image_path is not None
            return app.run_describe_task(resolved_task, image_path, output_path)
        return app.run_task(resolved_task, response_path=output_path)


if __name__ == "__main__":
    raise SystemExit(main())

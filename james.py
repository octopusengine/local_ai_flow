"""Small cross-platform terminal menu for the local Ollama tools.

Run with ``python james.py``.  The menu reacts to single key presses, so
neither Windows nor Linux needs a shell-specific launcher.
"""

from __future__ import annotations

import json
import os
import socket
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
JAMES_DIRECTORY = PROJECT_ROOT / "james"
if str(JAMES_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(JAMES_DIRECTORY))

from james_md import JAMES_COLOR_DEFAULTS, configured_color, load_markdown_settings, render_bold_markdown, render_markdown_line
from lib.wrapp_db import delete_task, list_task_rows, set_task_stars, short_text
from lib.wrapp_ollama import OllamaEmbeddingError, embed_texts
from lib.wrapp_terminal import Terminal, ansi_enabled, hide_cursor, show_cursor
from lib.wrapp_vector import (
    DatabaseProfile,
    VectorError,
    load_config as load_vector_config,
    new_database_profile,
    open_database,
    search_text,
    search_vectors,
    select_profile,
)


JAMES_CONFIG_PATH = JAMES_DIRECTORY / "james.json"
JAMES_FLOWS_CONFIG_PATH = JAMES_DIRECTORY / "james_flows.json"
JAMES_MD_CONFIG_PATH = JAMES_DIRECTORY / "james_md.json"
JAMES_ABOUT_PATH = JAMES_DIRECTORY / "about.md"
JAMES_ABOUT_CZ_PATH = JAMES_DIRECTORY / "about_cz.md"
JAMES_HELP_PATH = JAMES_DIRECTORY / "james_help.md"
CHAT_COMMANDS_PATH = JAMES_DIRECTORY / "chat_cmd.md"
CHAT_COMMANDS_CONFIG_PATH = JAMES_DIRECTORY / "chat_cmd.json"
ASSISTANT_TASKS_PATH = PROJECT_ROOT / "assistant" / "tasks"
SC_COMMAND_CATALOG_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc.json"
SC_COMMANDS_CZ_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc_cz.md"
SC_COMMANDS_DEFAULT_PATH = PROJECT_ROOT / "assistant" / "commands" / "README.md"
JAMES_VERSION = "0.2.3"
DATABASE_SCRIPT_PATH = PROJECT_ROOT / "cli_db.py"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "runner.py"
SPEECH_SCRIPT_PATH = PROJECT_ROOT / "cli_speech.py"
VECTOR_SCRIPT_PATH = PROJECT_ROOT / "cli_vector.py"
CAMERA_SCRIPT_PATH = PROJECT_ROOT / "cli_camera.py"
OLLAMA_SCRIPT_PATH = PROJECT_ROOT / "cli_ollama.py"
TOOL_SCRIPT_PATH = PROJECT_ROOT / "cli_tool.py"
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
CHAT_SUMMARY_FILENAME = "chat_summary.txt"
CHAT_ACTIVE_IMAGE_FILENAME = "chat_active_image.txt"
CHAT_RAG_DEFAULT_CHUNKS = 5
CHAT_RAG_MAX_CONTEXT_CHARACTERS = 6_000
CHAT_HISTORY_LIMIT = 200
RAG_DEMO_PROFILE = "btc"
RAG_DEMO_CHUNKS = 21
RAG_DEMO_CHUNK_CHARACTERS = 50
# These guide bands are calibrated for the locally configured embeddinggemma
# vectors.  They are intentionally only a visual aid; retrieval rank remains
# the reliable comparison for one concrete query.
RAG_DEMO_DISTANCE_CLOSE_MAX = 1.10
RAG_DEMO_DISTANCE_FAR_MIN = 1.25
OCR_OUTPUT_FILENAME = "ocr.txt"
IMAGE_OUTPUT_FILENAME = "describe.txt"
CHAT_INITIAL_CONTEXT = "- context:\n  No previous conversation.\n"
CHAT_CONVERSATION_HEADING = "## Conversation"
CHAT_URL_MAX_RESPONSE_BYTES = 5_000_000
CHAT_URL_MAX_TEXT_CHARACTERS = 20_000
CHAT_URL_TIMEOUT_SECONDS = 20
CHAT_URL_USER_AGENT = "James local Ollama chat/0.2"
CHAT_FIND_MAX_RESULTS = 20
CHAT_FIND_MAX_FILE_BYTES = 1_000_000
CHAT_FIND_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".json", ".py", ".csv", ".html", ".xml", ".yaml", ".yml", ".log"})
CHAT_FILES_MAX_RESULTS = 200
CHAT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
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


class _HTMLTextExtractor(HTMLParser):
    """Collect readable text while ignoring markup and non-content elements."""

    _BLOCK_TAGS = {
        "address", "article", "blockquote", "br", "div", "dl", "dt", "dd", "figcaption", "figure",
        "h1", "h2", "h3", "h4", "h5", "h6", "li", "main", "p", "pre", "section", "table", "tr",
    }
    _IGNORED_TAGS = {"canvas", "form", "iframe", "noscript", "script", "style", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.casefold()
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        self._parts.append(data)

    def text(self) -> str:
        """Return normalized visible text, retaining meaningful paragraph breaks."""

        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)


def _validate_chat_url(value: str) -> str:
    """Validate one URL accepted by the chat-local ``/url`` command."""

    candidate = value.strip()
    markdown_link = re.fullmatch(r"\[[^\]]*\]\((https?://[^\s)]+)\)", candidate, re.IGNORECASE)
    if markdown_link is not None:
        candidate = markdown_link.group(1)
    candidate = candidate.strip("<>")
    if not candidate or any(character.isspace() for character in candidate):
        raise ValueError("Use /url followed by one http:// or https:// address.")
    parsed = urlparse(candidate)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("/url accepts only a complete http:// or https:// address.")
    return candidate


def extract_chat_url_command(message: str) -> str | None:
    """Return the URL from an exclusive leading ``/url URL`` command."""

    command_match = re.match(r"^\s*/url(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return _validate_chat_url(command_match.group(1) or "")


def extract_chat_add_command(message: str) -> str | None:
    """Return the project-local file name from an exclusive ``/add FILE`` command."""

    command_match = re.match(r"^\s*/add(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    filename = (command_match.group(1) or "").strip().strip('"')
    if not filename:
        raise ValueError("Use /add followed by a text-file path in the active project directory.")
    return filename


def extract_chat_rag_command(message: str) -> str | None:
    """Return a requested wiki name, or ``off``, from ``/rag DATA``."""

    command_match = re.match(r"^\s*/rag(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    name = (command_match.group(1) or "").strip().casefold()
    if not name:
        raise ValueError("Use /rag DATA, for example /rag btc, or /rag off.")
    if name == "off":
        return name
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("RAG wiki name must use lowercase letters, digits, and underscores.")
    return name


def extract_chat_chunk_command(
    message: str,
    default_count: int = CHAT_RAG_DEFAULT_CHUNKS,
) -> tuple[int, str] | None:
    """Parse ``/chunk [N] FILTER``, using the configured count when N is omitted."""

    command_match = re.match(r"^\s*/chunk(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    if isinstance(default_count, bool) or not isinstance(default_count, int) or default_count <= 0:
        raise ValueError("The default /chunk count must be a positive whole number.")
    argument = (command_match.group(1) or "").strip()
    if not argument:
        raise ValueError("Use /chunk [N] FILTER, for example /chunk #(těžba bitcoinu) or /chunk 5 bitcoin, těžba.")
    first, separator, remainder = argument.partition(" ")
    if re.fullmatch(r"[+-]?\d+", first):
        count = int(first)
        query = remainder.strip()
        if count <= 0:
            raise ValueError("/chunk N requires a positive whole number.")
        if not query:
            raise ValueError("Use /chunk [N] FILTER, for example /chunk #(těžba bitcoinu) or /chunk 5 bitcoin, těžba.")
        return count, query
    count = default_count
    query = argument
    return count, query


def split_chat_rag_filter_expression(value: str) -> tuple[list[str], list[str], str]:
    """Split up to three filters, their optional ``and``/``or`` operators, and trailing text."""

    remaining = value.strip()
    if "," in remaining:
        fields = [field.strip() for field in remaining.split(",")]
        if not all(fields):
            raise ValueError("Each comma-separated RAG filter must contain text.")
        if len(fields) > 3:
            raise ValueError("Use at most three RAG filters per /chunk request.")
        tags: list[str] = []
        for field in fields:
            if field.startswith("#(") or field.startswith("("):
                prefix_length = 2 if field.startswith("#(") else 1
                if not field.endswith(")"):
                    raise ValueError("Each parenthesized RAG filter must end with ).")
                field = field[prefix_length:-1].strip()
            if not field:
                raise ValueError("A RAG filter cannot be empty.")
            tags.append(field)
        return tags, ["AND"] * (len(tags) - 1), ""

    tags: list[str] = []
    operators: list[str] = []
    while remaining.startswith("#(") or remaining.startswith("("):
        prefix_length = 2 if remaining.startswith("#(") else 1
        closing_index = remaining.find(")", prefix_length)
        if closing_index < 0:
            raise ValueError("Each RAG filter must use #(text) or (text).")
        tag = remaining[prefix_length:closing_index].strip()
        if not tag or "(" in tag:
            raise ValueError("A RAG filter cannot be empty or nested.")
        tags.append(tag)
        if len(tags) > 3:
            raise ValueError("Use at most three RAG filters per /chunk request.")
        remaining = remaining[closing_index + 1 :].strip()
        if remaining.startswith("#(") or remaining.startswith("("):
            operators.append("AND")
            continue
        operator_match = re.match(r"^(and|or)\b\s*", remaining, re.IGNORECASE)
        if operator_match is None:
            break
        operators.append(operator_match.group(1).upper())
        remaining = remaining[operator_match.end() :].strip()
        if not (remaining.startswith("#(") or remaining.startswith("(")):
            raise ValueError("RAG operator must be followed by #(text) or (text).")
    if tags and (remaining.startswith("#") or remaining.startswith("(")):
        raise ValueError("Each RAG filter must use #(text) or (text).")
    return tags, operators, remaining


def split_chat_rag_tags(value: str) -> tuple[list[str], str]:
    """Return filters and trailing text for callers that do not need their operators."""

    tags, _operators, remaining = split_chat_rag_filter_expression(value)
    return tags, remaining


def chat_rag_tag_query(tags: list[str], operators: list[str] | None = None) -> str:
    """Build a quoted FTS5 phrase query using user-selected ``AND`` and ``OR`` operators."""

    selected_operators = operators if operators is not None else ["AND"] * (len(tags) - 1)
    if len(selected_operators) != max(0, len(tags) - 1) or any(operator not in {"AND", "OR"} for operator in selected_operators):
        raise ValueError("RAG filters require one AND or OR operator between each pair of filters.")
    parts = [f'"{tag.replace(chr(34), chr(34) * 2)}"' for tag in tags]
    return " ".join(part for pair in zip(parts, [*selected_operators, ""]) for part in pair if part)


def extract_chat_cat_command(message: str) -> str | None:
    """Return the required project-local file name from an exclusive ``/cat FILE`` command."""

    command_match = re.match(r"^\s*/cat(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    filename = (command_match.group(1) or "").strip().strip('"')
    if not filename:
        raise ValueError("Use /cat followed by a UTF-8 text-file path in the active project directory.")
    return filename


def extract_chat_cam_command(message: str) -> str | None:
    """Return the optional requested camera file from an exclusive ``/cam`` command."""

    command_match = re.match(r"^\s*/cam(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_ocr_command(message: str) -> str | None:
    """Return the optional requested OCR image from an exclusive ``/ocr`` command."""

    command_match = re.match(r"^\s*/ocr(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_img_command(message: str) -> str | None:
    """Return the optional requested image from an exclusive ``/img`` command."""

    command_match = re.match(r"^\s*/img(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_drop_command(message: str) -> str | None:
    """Return one context-source name from an exclusive ``/drop NAME`` command."""

    command_match = re.match(r"^\s*/drop(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    source_name = (command_match.group(1) or "").strip()
    if not source_name:
        raise ValueError("Use /drop ocr to remove OCR results from the chat context.")
    return source_name.casefold()


def extract_chat_save_command(message: str) -> str | None:
    """Return the optional export file name from an exclusive ``/save [FILE]`` command."""

    command_match = re.match(r"^\s*/save(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_load_command(message: str) -> str | None:
    """Return the required source file name from an exclusive ``/load FILE`` command."""

    command_match = re.match(r"^\s*/load(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    filename = (command_match.group(1) or "").strip().strip('"')
    if not filename:
        raise ValueError("Use /load followed by a UTF-8 file from the active project directory.")
    return filename


def extract_chat_task_command(message: str) -> str | None:
    """Return an optional task JSON file name from an exclusive ``/task [TASK.json]`` command."""

    command_match = re.match(r"^\s*/task(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def available_chat_tasks() -> list[str]:
    """Return sorted task JSON file names available for the experimental Chat override."""

    if not ASSISTANT_TASKS_PATH.is_dir():
        raise ValueError(f"Chat task directory is missing: {ASSISTANT_TASKS_PATH}")
    return sorted(path.name for path in ASSISTANT_TASKS_PATH.glob("*.json") if path.is_file())


def select_chat_task(task_name: str) -> str:
    """Validate one task JSON file name from ``assistant/tasks`` and return its canonical name."""

    requested_name = task_name.strip()
    candidate = Path(requested_name)
    if not requested_name or candidate.name != requested_name or candidate.suffix.casefold() != ".json":
        raise ValueError("Use /task TASK.json with a JSON file from assistant/tasks.")
    matching_names = {name.casefold(): name for name in available_chat_tasks()}
    selected_name = matching_names.get(requested_name.casefold())
    if selected_name is None:
        raise ValueError(f"Chat task not found: {requested_name}. Use /task to list available tasks.")
    return selected_name


def chat_task_model(task_name: str) -> str:
    """Return the model configured by one available Chat task JSON file."""

    selected_name = select_chat_task(task_name)
    task_path = ASSISTANT_TASKS_PATH / selected_name
    try:
        task = json.loads(task_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read Chat task {selected_name}: {error}") from error
    model = task.get("model") if isinstance(task, dict) else None
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"Chat task {selected_name} requires a non-empty model.")
    return model


def is_chat_ctx_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/ctx`` command."""

    return re.fullmatch(r"\s*/ctx\s*", message, re.IGNORECASE | re.DOTALL) is not None


def is_chat_cmd_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/cmd`` catalog-reference command."""

    return re.fullmatch(r"\s*/cmd\s*", message, re.IGNORECASE | re.DOTALL) is not None


def is_chat_src_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/src`` command."""

    return re.fullmatch(r"\s*/src\s*", message, re.IGNORECASE | re.DOTALL) is not None


def extract_chat_find_command(message: str) -> str | None:
    """Return the required literal search text from an exclusive ``/find TEXT`` command."""

    command_match = re.match(r"^\s*/find(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    search_text = (command_match.group(1) or "").strip()
    if not search_text:
        raise ValueError("Use /find followed by text to search in the active project.")
    return search_text


def is_chat_clip_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/clip`` command."""

    return re.fullmatch(r"\s*/clip\s*", message, re.IGNORECASE | re.DOTALL) is not None


def is_chat_last_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/last`` command."""

    return re.fullmatch(r"\s*/last\s*", message, re.IGNORECASE | re.DOTALL) is not None


def is_chat_files_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/files`` command."""

    return re.fullmatch(r"\s*/files\s*", message, re.IGNORECASE | re.DOTALL) is not None


def extract_chat_debug_command(message: str) -> str | None:
    """Return ``status``, ``on``, or ``off`` for the exclusive ``/debug`` command."""

    command_match = re.match(r"^\s*/debug(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    requested_state = (command_match.group(1) or "").strip().casefold()
    if not requested_state:
        return "status"
    if requested_state in {"on", "true", "1"}:
        return "on"
    if requested_state in {"off", "false", "0"}:
        return "off"
    raise ValueError("Use /debug, /debug on, or /debug off.")


def extract_chat_tool_command(message: str) -> list[str] | None:
    """Parse ``/tool --PARAM ...`` into arguments for ``cli_tool.py``."""

    command_match = re.match(r"^\s*/tool(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    parameter_text = (command_match.group(1) or "").strip()
    if not parameter_text:
        raise ValueError("Use /tool followed by a cli_tool.py parameter, for example /tool --date-time.")
    try:
        arguments = shlex.split(parameter_text)
    except ValueError as error:
        raise ValueError(f"Invalid /tool parameters: {error}") from error
    if not arguments or not arguments[0].startswith("-"):
        raise ValueError("/tool parameters must start with - or --.")
    return arguments


def is_chat_sum_command(message: str) -> bool:
    """Return whether *message* is the exclusive ``/sum`` command."""

    return re.fullmatch(r"\s*/sum\s*", message, re.IGNORECASE | re.DOTALL) is not None


def fetch_chat_url_text(url: str) -> tuple[str, str]:
    """Download one HTML page and return its title and readable body text."""

    try:
        response = requests.get(
            url,
            headers={"User-Agent": CHAT_URL_USER_AGENT},
            timeout=CHAT_URL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise ValueError(f"Could not load URL: {error}") from error

    content_type = response.headers.get("Content-Type", "").casefold()
    if content_type and "html" not in content_type:
        raise ValueError("The URL did not return an HTML page.")
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdecimal() and int(content_length) > CHAT_URL_MAX_RESPONSE_BYTES:
        raise ValueError(f"The page is larger than {CHAT_URL_MAX_RESPONSE_BYTES:,} bytes.")
    if len(response.content) > CHAT_URL_MAX_RESPONSE_BYTES:
        raise ValueError(f"The page is larger than {CHAT_URL_MAX_RESPONSE_BYTES:,} bytes.")

    parser = _HTMLTextExtractor()
    try:
        parser.feed(response.text)
        parser.close()
    except (UnicodeError, ValueError) as error:
        raise ValueError(f"Could not read the page HTML: {error}") from error
    text = parser.text()
    if not text:
        raise ValueError("No readable text was found on the page.")
    if len(text) > CHAT_URL_MAX_TEXT_CHARACTERS:
        text = text[:CHAT_URL_MAX_TEXT_CHARACTERS].rsplit(" ", 1)[0].rstrip() + "\n[Text truncated.]"
    title = " ".join("".join(parser.title_parts).split()) or urlparse(url).netloc
    return title, text


def load_james_config() -> dict[str, Any]:
    """Load and validate the basic James settings and its separate flow lists."""

    try:
        data = json.loads(JAMES_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Configuration is missing: {JAMES_CONFIG_PATH.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {JAMES_CONFIG_PATH.name}: {error}") from error

    try:
        flow_data = json.loads(JAMES_FLOWS_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Flow configuration is missing: {JAMES_FLOWS_CONFIG_PATH.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {JAMES_FLOWS_CONFIG_PATH.name}: {error}") from error

    if not isinstance(data, dict) or data.get("json_version") != "1":
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires an object with 'json_version': '1'.")
    if any(key in data for key in FLOW_CATEGORY_KEYS):
        raise ValueError(f"{JAMES_CONFIG_PATH.name} must not contain flow lists; use {JAMES_FLOWS_CONFIG_PATH.name}.")
    if not isinstance(flow_data, dict) or flow_data.get("json_version") != "1":
        raise ValueError(f"{JAMES_FLOWS_CONFIG_PATH.name} requires an object with 'json_version': '1'.")
    unexpected_flow_keys = set(flow_data).difference(("json_version", *FLOW_CATEGORY_KEYS))
    if unexpected_flow_keys:
        raise ValueError(f"{JAMES_FLOWS_CONFIG_PATH.name} contains unsupported keys: {', '.join(sorted(unexpected_flow_keys))}.")
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
    markdown_settings = load_markdown_settings(JAMES_MD_CONFIG_PATH)
    if not isinstance(data.get("main_db"), str) or not data["main_db"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'main_db'.")
    for key in FLOW_CATEGORY_KEYS:
        flow_list = flow_data.get(key)
        if not isinstance(flow_list, list) or not 1 <= len(flow_list) <= 9:
            raise ValueError(f"{JAMES_FLOWS_CONFIG_PATH.name} requires one to nine '{key}' entries.")
        for flow in flow_list:
            flow_path = PROJECT_ROOT / "flows" / str(flow)
            if (
                not isinstance(flow, str)
                or not flow.strip()
                or Path(flow).name != flow
                or Path(flow).suffix.casefold() != ".txt"
                or not flow_path.is_file()
            ):
                raise ValueError(
                    f"Each {JAMES_FLOWS_CONFIG_PATH.name} '{key}' entry must name an existing flows/*.txt file."
                )
    if not isinstance(data.get("project_config"), str) or not data["project_config"].strip():
        raise ValueError(f"{JAMES_CONFIG_PATH.name} requires a non-empty 'project_config'.")
    return {**data, **{key: flow_data[key] for key in FLOW_CATEGORY_KEYS}, "colors": markdown_settings["colors"]}


def save_james_config(config: dict[str, Any]) -> None:
    """Save James's own small configuration without changing its layout style."""

    persistent_config = {key: value for key, value in config.items() if key not in (*FLOW_CATEGORY_KEYS, "colors")}
    JAMES_CONFIG_PATH.write_text(json.dumps(persistent_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def read_chat_message(prompt: str = ">? ") -> str:
    """Read one chat line and explicitly retain Unix readline history for ↑/↓ recall."""

    readline_module: Any | None = None
    history_length = 0
    if os.name != "nt":
        try:
            import readline as imported_readline

            readline_module = imported_readline
            readline_module.set_history_length(CHAT_HISTORY_LIMIT)
            history_length = readline_module.get_current_history_length()
        except ImportError:
            pass
    message = input(prompt)
    if readline_module is not None and message.strip():
        current_length = readline_module.get_current_history_length()
        latest = readline_module.get_history_item(current_length) if current_length else None
        if current_length == history_length or latest != message:
            readline_module.add_history(message)
    return message


def clear_screen() -> None:
    """Clear the menu when terminal control codes are available."""

    if ansi_enabled(sys.stdout):
        print("\033[2J\033[H", end="", flush=True)
    else:
        print("\n" * 2, end="")


def safe_console_text(value: object, stream: Any | None = None) -> str:
    """Return *value* in a form writable to a legacy console without raising an encoding error."""

    output = stream or sys.stdout
    encoding = getattr(output, "encoding", None) or "utf-8"
    text = str(value)
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def build_rag_demo_preview(text: str, query: str, maximum_characters: int) -> tuple[str, str, str]:
    """Return a short chunk window centred on one literal query word when available."""

    normalized_text = " ".join(text.strip().split())
    if not normalized_text:
        return "", "", ""
    query_words = [
        word for word in re.findall(r"[^\W_]+", query, re.UNICODE)
        if len(word) > 1 and word.casefold() not in {"and", "or"}
    ]
    match: re.Match[str] | None = None
    for word in query_words:
        candidate = re.search(rf"(?<!\w)({re.escape(word)})(?!\w)", normalized_text, re.IGNORECASE)
        if candidate is not None:
            match = candidate
            break
    if match is None:
        preview = normalized_text[:maximum_characters].rstrip()
        return (preview + "..." if len(preview) < len(normalized_text) else preview), "", ""

    remaining = max(0, maximum_characters - len(match.group(1)))
    start = max(0, match.start(1) - remaining // 2)
    end = min(len(normalized_text), match.end(1) + (remaining - remaining // 2))
    if start:
        boundary = normalized_text.rfind(" ", 0, start)
        start = boundary + 1 if boundary >= 0 else start
    if end < len(normalized_text):
        boundary = normalized_text.find(" ", end)
        end = boundary if boundary >= 0 else end
    before = normalized_text[start : match.start(1)].lstrip()
    after = normalized_text[match.end(1) : end].rstrip()
    if start:
        before = "..." + before
    if end < len(normalized_text):
        after += "..."
    return before, match.group(1), after


def rag_demo_distance_queries(query: str, groups: list[str]) -> list[tuple[str, str]]:
    """Build diagnostic vector queries for the complete input, groups, and unique words."""

    selected_groups = groups or [query]
    queries: list[tuple[str, str]] = [("all", " ".join(selected_groups))]
    if len(selected_groups) > 1:
        queries.extend((f"group: {group}", group) for group in selected_groups)
    seen_words: set[str] = set()
    for group in selected_groups:
        for word in re.findall(r"[^\W_]+", group, re.UNICODE):
            normalized_word = word.casefold()
            if len(word) <= 1 or normalized_word in {"and", "or"} or normalized_word in seen_words:
                continue
            seen_words.add(normalized_word)
            queries.append((f"word: {word}", word))
    return queries


def rag_demo_distance_color(distance: float) -> str | None:
    """Return the optional visual band for an embeddinggemma L2 distance."""

    if distance <= RAG_DEMO_DISTANCE_CLOSE_MAX:
        return "yellow"
    if distance >= RAG_DEMO_DISTANCE_FAR_MIN:
        return "green"
    return None


def render_rag_demo_distance(distance: float, terminal: Terminal | None = None) -> str:
    """Render a numeric diagnostic distance, highlighting only its relevance band."""

    rendered = f"{distance:.4f}"
    color = rag_demo_distance_color(distance)
    return (terminal or Terminal()).style(rendered, fg=color, bold=True) if color else rendered


def rag_demo_chunk_distances(
    connection: Any,
    chunk_ids: list[int],
    query_labels: list[str],
    query_embeddings: list[list[float]],
) -> dict[int, dict[str, float]]:
    """Calculate L2 distances from selected chunks to each already-created diagnostic query vector."""

    if len(query_labels) != len(query_embeddings):
        raise ValueError("RAG distance labels and embeddings must have the same length.")
    if not chunk_ids:
        return {}
    try:
        import sqlite_vec
    except ImportError as error:  # pragma: no cover - guarded by open_database in normal installations
        raise VectorError("sqlite-vec is not installed.") from error
    placeholders = ", ".join("?" for _chunk_id in chunk_ids)
    distances = {chunk_id: {} for chunk_id in chunk_ids}
    for label, embedding in zip(query_labels, query_embeddings):
        rows = connection.execute(
            f"SELECT rowid, vec_distance_l2(embedding, ?) AS distance FROM chunk_vectors WHERE rowid IN ({placeholders})",
            (sqlite_vec.serialize_float32(embedding), *chunk_ids),
        ).fetchall()
        for row in rows:
            distances[int(row["rowid"])][label] = float(row["distance"])
    return distances


def active_project_name(config: dict[str, Any]) -> str:
    """Return the selected project name without letting a bad config hide a page."""

    try:
        return str(load_project_config(config).get("subdir", "not set"))
    except (KeyError, ValueError):
        return "not set"


def render_page_header(
    config: dict[str, Any],
    *location: str,
    chat_debug: bool | None = None,
    chat_rag: DatabaseProfile | None = None,
) -> None:
    """Render James' compact common header at the top of every James page."""

    terminal = Terminal()
    if chat_debug is not None:
        language = terminal.color("yellow", str(config.get("language", "?")))
        print(f"{config.get('name', 'James')} - v{JAMES_VERSION} | debug: {str(chat_debug).lower()}")
        details = f"| project: {terminal.color('yellow', active_project_name(config))} | {language}"
        if chat_rag is not None:
            details += f" | RAG: {chat_rag.path.stem}"
        print(details)
        return
    location_text = " | ".join(item for item in location if item)
    header = (
        f"{config.get('name', 'James')} - v{JAMES_VERSION} | "
        f"project: {terminal.color('yellow', active_project_name(config))} | {location_text}"
    )
    print(header)


def render_section_header(width: int, title: str, config: dict[str, Any] | None = None) -> None:
    """Draw a single-line section heading that exactly fits the configured width."""

    prefix = "--- [ "
    suffix = " ] "
    available_title_length = max(1, width - len(prefix) - len(suffix))
    normalized_title = title.upper()
    if len(normalized_title) > available_title_length:
        normalized_title = "…" if available_title_length == 1 else normalized_title[: available_title_length - 1].rstrip() + "…"
    heading = f"{prefix}{normalized_title}{suffix}"
    terminal = Terminal()
    heading_color = configured_color(config, "col_head") if config is not None else JAMES_COLOR_DEFAULTS["col_head"]
    styled_title = terminal.style(normalized_title, fg=heading_color, bold=True)
    muted_prefix = terminal.color("bright_black", prefix)
    muted_suffix = terminal.color("bright_black", f"{suffix}{'-' * max(0, width - len(heading))}")
    print(f"{muted_prefix}{styled_title}{muted_suffix}")


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
    print(f" {active_project_name(config)} | {config['language']} |")
    print(separator)
    print()
    main_menu_rows = (
        (("chat", "c"), ("MCP", "m"), ("about", "a"), f"{' .'.join('.:.')}"),
        (("flow", "f"), ("RAG", "r"), ("setup", "s"), "(c) 2026"),
        (("database", "d"), ("cowork", "w"), ("help", "h"), " octopus"),
    )
    divider = terminal.color("bright_black", "|")
    for first, second, third, footer in main_menu_rows:
        menu_columns = (render_menu_label(*first, width=12), render_menu_label(*second, width=12), render_menu_label(*third, width=12))
        muted_footer = terminal.color("bright_black", footer.ljust(13))
        print(f"{MENU_INDENT}{f' {divider} '.join((*menu_columns, muted_footer))}")
    print()
    print(separator)
    print(f"{MENU_INDENT}{terminal.style('q', fg='yellow', bold=True)} = quit")


def render_project_menu(config: dict[str, Any]) -> None:
    """Draw the second level for the active project configuration."""

    terminal = Terminal()
    separator = "-" * int(config["width"])
    clear_screen()
    render_page_header(config, "setup", "project")
    render_section_header(int(config["width"]), "PROJECT", config)
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
    render_section_header(width, path.name, config)
    print()
    render_json_key_values(load_project_config(config), config)
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
    render_section_header(int(config["width"]), "PROJECT · dir_name", config)
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
    labels = ("project", "language", "james", "james_chat", "ollama", "models", "slash commands")
    clear_screen()
    render_page_header(config, "setup")
    render_section_header(width, "SETUP", config)
    print(f"language: {terminal.color('yellow', config['language'])}")
    print("-" * width)
    print()
    for index, label in enumerate(labels):
        if index == 2:
            print()
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
    render_section_header(width, "SETUP · LANGUAGE", config)
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
            selected_index = (selected_index - 1) % 7
        elif key == "down":
            selected_index = (selected_index + 1) % 7
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            try:
                project_menu(config)
            except ValueError as error:
                Terminal().r(f"Error: {error}")
                pause()
        elif selected_index == 1:
            language_menu(config)
        elif selected_index == 2:
            show_james_config(config)
        elif selected_index == 3:
            show_json_document(config, CHAT_COMMANDS_CONFIG_PATH, "JAMES_CHAT")
        elif selected_index == 4:
            show_json_document(config, OLLAMA_CONFIG_PATH, "OLLAMA")
        elif selected_index == 5:
            show_ollama_models(config)
        else:
            show_text_document(config, slash_commands_document_path(config), "SLASH COMMANDS")


def slash_commands_document_path(config: dict[str, Any]) -> Path:
    """Choose the Czech command reference only for the Czech James language."""

    return SC_COMMANDS_CZ_PATH if config["language"] == "cz" else SC_COMMANDS_DEFAULT_PATH


def show_ollama_models(config: dict[str, Any]) -> None:
    """Display the locally installed models reported by ``ollama list``."""

    clear_screen()
    render_page_header(config, "setup", "models")
    width = int(config["width"])
    render_section_header(width, "OLLAMA · MODELS", config)
    print()
    try:
        result = subprocess.run(
            ["ollama", "list"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        Terminal().r(f"Could not run 'ollama list': {error}")
    else:
        output = result.stdout.strip()
        if output:
            print(output)
        else:
            Terminal().y(result.stderr.strip() or "No Ollama models were reported.")
        if result.returncode:
            Terminal().r(f"'ollama list' exited with code {result.returncode}.")
    wait_for_back(width)


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
    render_section_header(width, label, config)
    print()
    terminal.y("This section is a placeholder; its content will be added later.")
    wait_for_back(width)


def show_todo(config: dict[str, Any], title: str, message: str) -> None:
    """Show a named placeholder with its next planned capability."""

    clear_screen()
    render_page_header(config, title.lower())
    terminal = Terminal()
    width = int(config["width"])
    render_section_header(width, title, config)
    print()
    terminal.y(f"TODO: {message}")
    wait_for_back(width)


def render_rag_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the cursor-controlled RAG action and configuration menu."""

    terminal = Terminal()
    width = int(config["width"])
    labels = ("ingest", "test", "cli_vector.json", "rag_wiki/databases.json", "data_tree")
    clear_screen()
    render_page_header(config, "rag")
    render_section_header(width, "RAG", config)
    print()
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def ingest_new_wiki(config: dict[str, Any]) -> None:
    """Ask for a source-group name and ingest it into a local wiki database."""

    if not VECTOR_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {VECTOR_SCRIPT_PATH.name}")
    clear_screen()
    render_page_header(config, "rag", "ingest")
    terminal = Terminal()
    width = int(config["width"])
    render_section_header(width, "RAG · INGEST NEW WIKI", config)
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

    command = [sys.executable, str(VECTOR_SCRIPT_PATH), "ingest-wiki", requested_profile.name, "--embed"]
    existing_profile = profiles.get(requested_profile.name)
    if existing_profile is not None:
        state = "exists" if existing_profile.path.is_file() else "is missing and will be created"
        print(f"Profile '{existing_profile.name}' is registered; database {state}: {existing_profile.path.name}")
        choice = input("[u] update changed sources / [o] overwrite all sources and reindex / Enter cancel: ").strip().casefold()
        if choice == "o":
            command.append("--overwrite")
        elif choice != "u":
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


def run_rag_demo_test(config: dict[str, Any]) -> None:
    """Run an interactive, read-only vector-retrieval demonstration over a selected wiki."""

    clear_screen()
    render_page_header(config, "rag", "test")
    width = int(config["width"])
    render_section_header(width, "RAG · TEST", config)
    print()
    print("Read-only vector-RAG test: no ingest, reindex, or Chat-context changes.")
    print()
    wiki_name = input(f"RAG setup / wiki name [{RAG_DEMO_PROFILE}]: ").strip().casefold() or RAG_DEMO_PROFILE
    preview_characters = prompt_rag_demo_positive_integer(
        f"Chunk preview characters [{RAG_DEMO_CHUNK_CHARACTERS}]: ",
        RAG_DEMO_CHUNK_CHARACTERS,
    )
    chunk_count = prompt_rag_demo_positive_integer(
        f"Number of chunks [{RAG_DEMO_CHUNKS}]: ",
        RAG_DEMO_CHUNKS,
    )
    query = input("Search phrase (plain text, or (A) and/or (B)): ").strip()
    if not query:
        Terminal().y("RAG test cancelled: a search phrase is required.")
        wait_for_back(width)
        return
    try:
        tags, operators, trailing_text = split_chat_rag_filter_expression(query)
        if tags and trailing_text:
            raise ValueError("Use only RAG filters in the form (A) and/or (B), without trailing question text.")
        distance_queries = rag_demo_distance_queries(query, tags)
        query_labels = [label for label, _text in distance_queries]
        profile = select_chat_rag_profile(wiki_name)
        vector_config, _profiles = load_vector_config(VECTOR_CONFIG_PATH, PROJECT_ROOT)
        embedding_model = str(vector_config["embedding_model"])
        query_embeddings = embed_texts(
            OLLAMA_CONFIG_PATH,
            embedding_model,
            [text for _label, text in distance_queries],
        )
        connection = open_database(profile.path)
        try:
            hits = search_vectors(connection, query_embeddings[0], chunk_count)
            diagnostic_distances = rag_demo_chunk_distances(
                connection,
                [hit.chunk_id for hit in hits],
                query_labels,
                query_embeddings,
            )
        finally:
            connection.close()
    except ValueError as error:
        Terminal().r(f"RAG test could not run: {error}")
        Terminal().y("Choose an existing indexed wiki and valid filters, then run this test again.")
        wait_for_back(width)
        return
    except (OSError, sqlite3.Error, VectorError, OllamaEmbeddingError) as error:
        Terminal().r(f"RAG test could not run: {error}")
        wait_for_back(width)
        return

    if tags:
        Terminal().y("Note: vector distance treats AND/OR filters semantically; exact Boolean filtering is available in Chat /chunk (FTS5).")
    if hits:
        Terminal().g(f"PASS: found {len(hits)} vector chunk(s) in {profile.path.name} for {query!r}.")
        terminal = Terminal()
        close = terminal.style(f"<= {RAG_DEMO_DISTANCE_CLOSE_MAX:.2f} close", fg="yellow", bold=True)
        far = terminal.style(f">= {RAG_DEMO_DISTANCE_FAR_MIN:.2f} distant", fg="green", bold=True)
        print(f"Distance guide (embeddinggemma L2): {close}; {far}; values between them are contextual.")
    else:
        Terminal().y(f"No chunks matched {query!r}; the database opened but needs relevant indexed material.")
    print()
    for index, hit in enumerate(hits, start=1):
        location = hit.path + (f", page {hit.page_number}" if hit.page_number else "")
        before, matched_word, after = build_rag_demo_preview(hit.text, query, preview_characters)
        if hit.distance is None:
            Terminal().c(f"[{index}] {location} · chunk {hit.chunk_index} · distance unavailable")
        else:
            prefix = Terminal().color("cyan", f"[{index}] {location} · chunk {hit.chunk_index} · distance ")
            print(prefix + render_rag_demo_distance(hit.distance))
        highlighted_word = Terminal().style(matched_word, fg="yellow", bold=True) if matched_word else ""
        print(safe_console_text(before + highlighted_word + after))
        details = diagnostic_distances.get(hit.chunk_id, {})
        detail_items = [(label, value) for label, value in details.items() if label != "all"]
        if detail_items:
            rendered_details = " | ".join(
                f"{label} {render_rag_demo_distance(value)}" for label, value in detail_items
            )
            print(safe_console_text(rendered_details))
        print()
    print()
    Terminal().c(f"Try the same workflow in Chat: /rag {profile.name}, then /chunk {chunk_count} {query}.")
    wait_for_back(width)


def prompt_rag_demo_positive_integer(prompt: str, default: int) -> int:
    """Read a positive test setting, using *default* when the user presses Enter."""

    while True:
        entered = input(prompt).strip()
        if not entered:
            return default
        try:
            value = int(entered)
        except ValueError:
            value = 0
        if value > 0:
            return value
        Terminal().y("Enter a positive whole number, or press Enter for the default.")


def rag_menu(config: dict[str, Any]) -> None:
    """Choose RAG actions using arrows and Enter, never letter shortcuts."""

    selected_index = 0
    while True:
        render_rag_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = (selected_index - 1) % 5
        elif key == "down":
            selected_index = (selected_index + 1) % 5
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            ingest_new_wiki(config)
        elif selected_index == 1:
            run_rag_demo_test(config)
        elif selected_index == 2:
            show_text_document(config, VECTOR_CONFIG_PATH, "RAG · CLI VECTOR")
        elif selected_index == 3:
            show_text_document(config, VECTOR_DATABASES_PATH, "RAG · DATABASES")
        else:
            show_rag_data_tree(config)


def show_rag_data_tree(config: dict[str, Any]) -> None:
    """Display the directory tree below ``rag_wiki`` without listing files."""

    clear_screen()
    render_page_header(config, "rag", "data_tree")
    terminal = Terminal()
    width = int(config["width"])
    rag_root = VECTOR_DATABASES_PATH.parent
    render_section_header(width, "RAG · DATA TREE", config)
    print()
    if not rag_root.is_dir():
        print("rag_wiki/ (missing)")
    else:
        print("rag_wiki/")
        directories = sorted(
            (path for path in rag_root.rglob("*") if path.is_dir()),
            key=lambda path: path.as_posix().casefold(),
        )
        for directory in directories:
            relative = directory.relative_to(rag_root)
            indent = "  " * (len(relative.parts) - 1)
            print(f"{indent}{directory.name}/")
    wait_for_back(width)


def show_text_document(config: dict[str, Any], path: Path, title: str) -> None:
    """Display a small James-owned text document read-only, rendering Markdown files lightly."""

    try:
        content = path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError as error:
        raise ValueError(f"Document is missing: {path.relative_to(PROJECT_ROOT)}") from error
    clear_screen()
    render_page_header(config, title.lower())
    width = int(config["width"])
    render_section_header(width, title, config)
    print()
    if not content:
        print("(empty)")
    elif path.suffix.casefold() == ".md":
        for line in content.splitlines():
            print(render_markdown_line(line, config))
    else:
        print(content)
    wait_for_back(width)


def json_scalar_text(value: Any) -> str:
    """Return a compact JSON value while leaving ordinary strings easy to read."""

    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def render_json_key_values(value: Any, config: dict[str, Any], indent: int = 0) -> None:
    """Render parsed JSON with colored ``key`` labels and readable nested values."""

    prefix = " " * indent
    bold_color = configured_color(config, "col_bold")
    if isinstance(value, dict):
        for key, item in value.items():
            rendered_key = render_bold_markdown(f"**{key}**:", bold_color=bold_color)
            if isinstance(item, (dict, list)):
                print(f"{prefix}{rendered_key}")
                render_json_key_values(item, config, indent + 2)
            else:
                print(f"{prefix}{rendered_key} {json_scalar_text(item)}")
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                print(f"{prefix}-")
                render_json_key_values(item, config, indent + 2)
            else:
                print(f"{prefix}- {json_scalar_text(item)}")
        return
    print(f"{prefix}{json_scalar_text(value)}")


def show_json_document(config: dict[str, Any], path: Path, title: str) -> None:
    """Parse and display one James JSON document as readable key-value rows."""

    try:
        content = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise ValueError(f"Document is missing: {path.relative_to(PROJECT_ROOT)}") from error
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path.relative_to(PROJECT_ROOT)}: {error}") from error
    clear_screen()
    render_page_header(config, title.lower())
    width = int(config["width"])
    render_section_header(width, title, config)
    print()
    render_json_key_values(data, config)
    wait_for_back(width)


def show_james_config(config: dict[str, Any]) -> None:
    """Display basic James settings while omitting the long flow collections."""

    basic_config = {key: value for key, value in config.items() if key not in (*FLOW_CATEGORY_KEYS, "colors")}
    clear_screen()
    render_page_header(config, "setup", "james")
    width = int(config["width"])
    render_section_header(width, "JAMES", config)
    print()
    render_json_key_values(basic_config, config)
    print()
    Terminal().c(f"Markdown colors: {JAMES_MD_CONFIG_PATH.relative_to(PROJECT_ROOT).as_posix()}")
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
    render_section_header(int(config["width"]), "DATABASE", config)
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
    render_section_header(width, "CLONE", config)
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
        render_section_header(width, f"DATABASE RECORD #{row['uid']}", config)
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
    render_section_header(width, "DATABASE LIST", config)
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
    render_section_header(width, f"FILTER · {field_name.replace('_', ' ')}", config)
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
    render_section_header(width, "FILTER", config)
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
    render_section_header(width, "MCP", config)
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
            selected_index = (selected_index - 1) % 3
        elif key == "down":
            selected_index = (selected_index + 1) % 3
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
    render_section_header(int(config["width"]), title, config)
    print(f"Flow {selected_index + 1} of {len(flows)}")
    print(separator)
    print()
    for index, flow_name in enumerate(flows):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(flow_name, fg="yellow", bold=True) if index == selected_index else flow_name
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    info_key = terminal.style("i", fg="yellow", bold=True)
    print(f"{MENU_INDENT}↑/↓ move | {info_key}nfo | Enter run")
    render_back_footer(int(config["width"]))


def run_flow(
    flow_name: str,
    pause_after: bool = True,
    report_result: bool = True,
    clear_before: bool = True,
    model_override: str | None = None,
    task_override: str | None = None,
    sc_commands: list[str] | None = None,
    sc_language: str | None = None,
    image_file: str | None = None,
    capture_output: bool = False,
) -> int:
    """Run one configured text flow through runner.py and return its exit code.

    ``capture_output`` lets Chat render the saved reply itself after a successful
    request, while preserving the runner diagnostics when that request fails.
    """

    if not RUNNER_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {RUNNER_SCRIPT_PATH.name}")
    if clear_before:
        clear_screen()
    command = [sys.executable, str(RUNNER_SCRIPT_PATH)]
    if model_override is not None:
        command.extend(("--model", model_override))
    if task_override is not None:
        command.extend(("--task", task_override))
    if sc_language is not None:
        command.extend(("--sc-language", sc_language))
    if image_file is not None:
        command.extend(("--image", image_file))
    for sc_command in sc_commands or []:
        command.extend(("--sc", sc_command))
    command.append(flow_name)
    if task_override is not None and model_override is not None:
        detail_label = f" (task: {task_override} | Model: {model_override})"
    elif task_override is not None:
        detail_label = f" (task: {task_override})"
    elif model_override is not None:
        detail_label = f" (model: {model_override})"
    else:
        detail_label = ""
    Terminal().c(f"Starting runner.py {flow_name}{detail_label}…")
    run_options: dict[str, Any] = {"cwd": PROJECT_ROOT, "check": False}
    if capture_output:
        run_options.update({"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"})
    result = subprocess.run(command, **run_options)
    if capture_output and result.returncode:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
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


def load_chat_command_config() -> dict[str, Any]:
    """Load the chat-local configuration document."""

    try:
        document = json.loads(CHAT_COMMANDS_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load chat command settings: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"Chat command settings must be an object: {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return document


def load_chat_command_settings(command_name: str) -> dict[str, Any]:
    """Load one structured chat-command configuration from ``chat_cmd.json``."""

    document = load_chat_command_config()
    commands = document.get("commands") if isinstance(document, dict) else None
    settings = commands.get(command_name) if isinstance(commands, dict) else None
    if not isinstance(settings, dict):
        raise ValueError(f"Missing settings for /{command_name} in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return settings


def chat_sc_context_defaults(config: dict[str, Any]) -> tuple[str, str]:
    """Return the localized fallback input and history label for a bare chat slash command."""

    defaults = load_chat_command_config().get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError(f"Missing chat defaults in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    inputs = defaults.get("sc_context_input")
    history_label = defaults.get("sc_context_history_label")
    language = config.get("language")
    input_text = inputs.get(language) if isinstance(inputs, dict) else None
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError(f"Missing slash-command context input for language {language!r}.")
    if not isinstance(history_label, str) or not history_label.strip():
        raise ValueError(f"Invalid slash-command history label in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return input_text, history_label


def chat_last_reply_sc_settings(config: dict[str, Any]) -> tuple[set[str], str, str]:
    """Return the commands and flow used to transform the latest chat reply."""

    defaults = load_chat_command_config().get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError(f"Missing chat defaults in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    command_names = defaults.get("last_reply_sc")
    history_label = defaults.get("last_reply_history_label")
    flow_template = defaults.get("last_reply_flow_template")
    if (
        not isinstance(command_names, list)
        or not command_names
        or not all(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in command_names)
        or not isinstance(history_label, str)
        or not history_label.strip()
        or not isinstance(flow_template, str)
        or not flow_template.strip()
    ):
        raise ValueError(f"Invalid latest-reply slash-command settings in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    language = config.get("language")
    if not isinstance(language, str) or not language.strip():
        raise ValueError("Chat language is missing.")
    try:
        flow_name = flow_template.format(language=language)
    except (KeyError, ValueError) as error:
        raise ValueError(f"Invalid latest-reply flow template in {CHAT_COMMANDS_CONFIG_PATH.name}.") from error
    return {name.casefold() for name in command_names}, history_label, flow_name


def chat_debug_default() -> bool:
    """Read the default debug state for one new chat session."""

    defaults = load_chat_command_config().get("defaults")
    value = defaults.get("debug") if isinstance(defaults, dict) else None
    if not isinstance(value, bool):
        raise ValueError(f"Invalid chat debug default in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return value


def chat_context_turns_default() -> int:
    """Return the configured retained-turn limit for a newly opened Chat session."""

    defaults = load_chat_command_config().get("defaults")
    context_turns = defaults.get("context_turns") if isinstance(defaults, dict) else None
    if isinstance(context_turns, bool) or not isinstance(context_turns, int) or context_turns < 1:
        raise ValueError(f"Invalid context_turns in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return context_turns


def chat_rag_chunk_count_default() -> int:
    """Return the configured number of chunks for a bare ``/chunk FILTER`` command."""

    defaults = load_chat_command_config().get("defaults")
    value = defaults.get("rag_chunk_count") if isinstance(defaults, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"Invalid rag_chunk_count in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return value


def chat_context_turns(config: dict[str, Any]) -> int:
    """Return an explicit runtime limit or the default retained-turn limit."""

    context_turns = config.get("chat_context_turns")
    if context_turns is None:
        return chat_context_turns_default()
    if isinstance(context_turns, bool) or not isinstance(context_turns, int) or context_turns < 1:
        raise ValueError("Chat context-turn limit must be a positive integer.")
    return context_turns


def chat_task_default() -> str:
    """Return the configured default task for one newly opened Chat session."""

    defaults = load_chat_command_config().get("defaults")
    task_name = defaults.get("default_task") if isinstance(defaults, dict) else None
    if not isinstance(task_name, str) or not task_name.strip():
        raise ValueError(f"Invalid default_task in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return select_chat_task(task_name)


def chat_image_command_settings(command_name: str) -> tuple[str, list[str], str, str]:
    """Validate and return task, slash commands, output, and context label for one image command."""

    settings = load_chat_command_settings(command_name)
    task = settings.get("task")
    sc_commands = settings.get("sc")
    output_file = settings.get("output")
    context_label = settings.get("context_label")
    if (
        not isinstance(task, str)
        or not task.strip()
        or not isinstance(sc_commands, list)
        or not all(isinstance(item, str) and item.strip() for item in sc_commands)
        or not isinstance(output_file, str)
        or not output_file.strip()
        or not isinstance(context_label, str)
        or not re.fullmatch(r"[A-Za-z0-9 _-]+", context_label)
    ):
        raise ValueError(f"Invalid /{command_name} settings in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return task, sc_commands, output_file, context_label


def configured_sc_language_argument(config: dict[str, Any]) -> str:
    """Return the CLI language switch matching the active James language."""

    language = config.get("language")
    if language not in {"cz", "en", "es"}:
        raise ValueError(f"Unsupported chat language for slash commands: {language!r}.")
    return f"--sc-{language}"


def ensure_chat_context_file(config: dict[str, Any]) -> Path:
    """Ensure the chat context is non-empty before the first model request."""

    project_directory = active_project_directory(config).resolve()
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

    source_context, existing_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    if existing_turns.startswith("- user:\n"):
        turns = ["- user:\n" + turn for turn in existing_turns.removeprefix("- user:\n").split("\n- user:\n")]
    else:
        turns = []
    turns.append(format_chat_turn(user_message, assistant_reply))
    write_chat_context(context_path, source_context, "\n".join(turns[-chat_context_turns(config) :]))


def split_chat_context(existing_context: str) -> tuple[str, str]:
    """Separate persistent source material from the retained conversation turns."""

    existing_context = existing_context.strip()
    marker = f"\n{CHAT_CONVERSATION_HEADING}\n"
    if marker in existing_context:
        return tuple(part.strip() for part in existing_context.split(marker, 1))
    if existing_context.startswith("- user:\n"):
        return "", existing_context
    if existing_context == CHAT_INITIAL_CONTEXT.strip():
        return "", ""
    return existing_context, ""


def write_chat_context(context_path: Path, source_context: str, conversation_turns: str) -> None:
    """Write source material and conversation turns in the chat flow's context format."""

    sections = [source_context.strip()] if source_context.strip() else []
    if conversation_turns.strip():
        if source_context.strip():
            sections.append(f"{CHAT_CONVERSATION_HEADING}\n{conversation_turns.strip()}")
        else:
            sections.append(conversation_turns.strip())
    context_path.write_text("\n\n".join(sections or [CHAT_INITIAL_CONTEXT.strip()]) + "\n", encoding="utf-8")


def append_chat_url_context(config: dict[str, Any], url: str, title: str, text: str) -> None:
    """Append readable content from one web page to the active chat context."""

    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    source = f"## Web source\nURL: {url}\nTitle: {title}\n\n{text.strip()}"
    write_chat_context(context_path, "\n\n".join(part for part in (source_context, source) if part), conversation_turns)


def select_chat_rag_profile(wiki_name: str) -> DatabaseProfile:
    """Resolve an existing named wiki without changing the configured default database."""

    try:
        vector_config, profiles = load_vector_config(VECTOR_CONFIG_PATH, PROJECT_ROOT)
        try:
            profile = select_profile(profiles, wiki_name, vector_config["main_db"])
        except VectorError:
            profile = new_database_profile(vector_config, PROJECT_ROOT, wiki_name)
    except VectorError as error:
        raise ValueError(f"Cannot read RAG wiki configuration: {error}") from error
    if not profile.path.is_file():
        raise ValueError(f"RAG wiki is missing: {profile.path.relative_to(PROJECT_ROOT).as_posix()}")
    return profile


def build_chat_rag_context(profile: DatabaseProfile, query: str, chunk_count: int) -> tuple[str, int]:
    """Retrieve local FTS5 chunks and format one replaceable Chat source section."""

    try:
        connection = open_database(profile.path)
        try:
            hits = search_text(connection, query, chunk_count)
        finally:
            connection.close()
    except (OSError, sqlite3.Error, VectorError) as error:
        raise ValueError(f"Could not search RAG wiki {profile.name}: {error}") from error

    header = (
        "## [RAG]\n"
        f"Database: wiki_{profile.name}.db\n"
        f"Query: {query}\n"
        "Instruction: Answer from the retrieved chunks below. If they do not contain the answer, say so."
    )
    parts = [header]
    used = len(header)
    for number, hit in enumerate(hits, start=1):
        location = hit.path + (f", page {hit.page_number}" if hit.page_number else "")
        block = f"### RAG result {number}: {location} (chunk {hit.chunk_index})\n\n{hit.text.strip()}"
        separator = 2
        if used + separator + len(block) > CHAT_RAG_MAX_CONTEXT_CHARACTERS:
            remaining = CHAT_RAG_MAX_CONTEXT_CHARACTERS - used - separator
            if remaining <= 0:
                break
            parts.append(block[:remaining].rstrip() + "\n\n[context truncated]")
            break
        parts.append(block)
        used += separator + len(block)
    if not hits:
        parts.append("### No matching chunks\n\nThe selected wiki did not return a matching source.")
    return "\n\n".join(parts), len(hits)


def replace_chat_rag_context(config: dict[str, Any], rag_context: str) -> None:
    """Replace the previous transient RAG source while retaining other sources and turns."""

    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    sections = re.split(r"\n{2,}(?=## )", source_context.strip()) if source_context.strip() else []
    retained = [section for section in sections if not section.startswith("## [RAG]\n")]
    write_chat_context(context_path, "\n\n".join([*retained, rag_context.strip()]), conversation_turns)


def render_chat_rag_context(config: dict[str, Any], rag_context: str) -> None:
    """Show exactly the RAG source section that was just attached to Chat."""

    Terminal().c("Attached RAG context:")
    for line in rag_context.strip().splitlines():
        print(render_markdown_line(line, config))
    print()


def drop_chat_rag_context(config: dict[str, Any]) -> int:
    """Remove transient RAG source sections from the active chat context."""

    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    sections = re.split(r"\n{2,}(?=## )", source_context.strip()) if source_context.strip() else []
    retained = [section for section in sections if not section.startswith("## [RAG]\n")]
    write_chat_context(context_path, "\n\n".join(retained), conversation_turns)
    return len(sections) - len(retained)


def resolve_chat_context_file(config: dict[str, Any], filename: str, *, command_name: str = "/add") -> Path:
    """Resolve one readable text file contained in the active project directory."""

    project_directory = active_project_directory(config).resolve()
    candidate = Path(filename)
    if candidate.is_absolute():
        raise ValueError(f"{command_name} accepts only a path relative to the active project directory.")
    file_path = (project_directory / candidate).resolve()
    if not file_path.is_relative_to(project_directory):
        raise ValueError(f"{command_name} cannot read files outside the active project directory.")
    if not file_path.is_file():
        raise ValueError(f"Project file not found: {filename}")
    return file_path


def read_chat_project_file(config: dict[str, Any], filename: str, *, command_name: str = "/cat") -> tuple[Path, str]:
    """Read one UTF-8 project text file without modifying chat context."""

    file_path = resolve_chat_context_file(config, filename, command_name=command_name)
    try:
        return file_path, file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{command_name} accepts UTF-8 text files only: {filename}") from error
    except OSError as error:
        raise ValueError(f"Could not read project file {filename}: {error}") from error


def resolve_chat_project_path(config: dict[str, Any], filename: str, *, must_exist: bool) -> Path:
    """Resolve a chat camera/OCR path while keeping it in the active project."""

    if not filename.strip():
        raise ValueError("A file name is required.")
    project_directory = active_project_directory(config).resolve()
    candidate = Path(filename)
    if candidate.is_absolute():
        raise ValueError("Use a path relative to the active project directory.")
    file_path = (project_directory / candidate).resolve()
    if not file_path.is_relative_to(project_directory):
        raise ValueError("The file must stay inside the active project directory.")
    if must_exist and not file_path.is_file():
        raise ValueError(f"Project image not found: {filename}")
    return file_path


def chat_active_image_state_path(config: dict[str, Any]) -> Path:
    """Return the project-local state file that records the active chat image."""

    defaults = load_chat_command_config().get("defaults")
    filename = defaults.get("active_image_file") if isinstance(defaults, dict) else None
    candidate = Path(filename) if isinstance(filename, str) and filename.strip() else None
    if candidate is None or candidate.is_absolute() or candidate.parent != Path("."):
        raise ValueError(f"Invalid active image file in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return active_project_directory(config).resolve() / candidate


def set_chat_active_image(config: dict[str, Any], image_path: Path) -> str:
    """Record one project image for subsequent vision-enabled chat turns."""

    project_directory = active_project_directory(config).resolve()
    resolved_image = image_path.resolve()
    if not resolved_image.is_file() or resolved_image.suffix.casefold() not in CHAT_IMAGE_EXTENSIONS:
        raise ValueError("The active chat image must be a supported project image file.")
    try:
        relative_path = resolved_image.relative_to(project_directory).as_posix()
    except ValueError as error:
        raise ValueError("The active chat image must stay inside the active project directory.") from error
    chat_active_image_state_path(config).write_text(relative_path + "\n", encoding="utf-8")
    return relative_path


def read_chat_active_image(config: dict[str, Any]) -> str | None:
    """Return the current project-relative vision image, if one has been selected."""

    state_path = chat_active_image_state_path(config)
    if not state_path.is_file():
        return None
    try:
        filename = state_path.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        raise ValueError(f"Could not read the active chat image: {error}") from error
    if not filename:
        return None
    image_path = resolve_chat_project_path(config, filename, must_exist=True)
    if image_path.suffix.casefold() not in CHAT_IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported active chat image: {filename}")
    return image_path.relative_to(active_project_directory(config).resolve()).as_posix()


def clear_chat_active_image(config: dict[str, Any]) -> None:
    """Forget the selected vision image when a chat context is replaced or cleared."""

    state_path = chat_active_image_state_path(config)
    if state_path.is_file():
        state_path.unlink()


def capture_chat_camera(config: dict[str, Any], filename: str, *, debug: bool = False) -> Path:
    """Run the camera CLI and hide successful backend diagnostics unless debugging."""

    output_path = resolve_chat_project_path(config, filename, must_exist=False)
    if not CAMERA_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {CAMERA_SCRIPT_PATH.name}")
    run_options: dict[str, Any] = {"cwd": PROJECT_ROOT, "check": False}
    if not debug:
        run_options.update({"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"})
    result = subprocess.run([sys.executable, str(CAMERA_SCRIPT_PATH), "--out", filename], **run_options)
    if result.returncode:
        diagnostics = "\n".join(
            output.strip()
            for output in (getattr(result, "stdout", ""), getattr(result, "stderr", ""))
            if isinstance(output, str) and output.strip()
        )
        message = f"Camera command exited with code {result.returncode}."
        raise ValueError(f"{message}\n{diagnostics}" if diagnostics else message)
    return output_path


def run_chat_tool(arguments: list[str]) -> None:
    """Run ``cli_tool.py`` with parsed arguments while staying in the project root."""

    if not TOOL_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {TOOL_SCRIPT_PATH.name}")
    result = subprocess.run([sys.executable, str(TOOL_SCRIPT_PATH), *arguments], cwd=PROJECT_ROOT, check=False)
    if result.returncode:
        raise ValueError(f"/tool command exited with code {result.returncode}.")


def run_chat_image_task(config: dict[str, Any], command_name: str, filename: str) -> Path:
    """Run one configured image task over a project-local image."""

    image_path = resolve_chat_project_path(config, filename, must_exist=True)
    if not OLLAMA_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {OLLAMA_SCRIPT_PATH.name}")
    task, sc_commands, _output_file, _context_label = chat_image_command_settings(command_name)
    relative_path = image_path.relative_to(active_project_directory(config).resolve()).as_posix()
    command = [sys.executable, str(OLLAMA_SCRIPT_PATH), "--type", task]
    if sc_commands:
        command.append(configured_sc_language_argument(config))
    for sc_command in sc_commands:
        command.extend(("--sc", sc_command))
    command.extend(("--in", relative_path))
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if result.returncode:
        raise ValueError(f"/{command_name} command exited with code {result.returncode}.")
    return image_path


def run_chat_ocr(config: dict[str, Any], filename: str) -> Path:
    """Run the configured OCR task over an image in the active project directory."""

    return run_chat_image_task(config, "ocr", filename)


def run_chat_img(config: dict[str, Any], filename: str) -> Path:
    """Describe an image with the configured image-analysis task."""

    return run_chat_image_task(config, "img", filename)


def append_chat_image_context(config: dict[str, Any], command_name: str, image_path: Path) -> tuple[Path, int]:
    """Add a configured image-task result to the persistent chat source context."""

    _task, _sc_commands, output_file, context_label = chat_image_command_settings(command_name)
    output_path = resolve_chat_context_file(config, output_file)
    try:
        text = output_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"/{command_name} result is not valid UTF-8: {output_file}") from error
    except OSError as error:
        raise ValueError(f"Could not read /{command_name} result {output_file}: {error}") from error
    if not text.strip():
        raise ValueError(f"/{command_name} result is empty: {output_file}")

    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    project_directory = active_project_directory(config).resolve()
    display_image = image_path.resolve().relative_to(project_directory).as_posix()
    source = f"## [{context_label}]\nImage: {display_image}\nResult: {output_file}\n\n{text.strip()}"
    write_chat_context(context_path, "\n\n".join(part for part in (source_context, source) if part), conversation_turns)
    return output_path, len(text)


def append_chat_ocr_context(config: dict[str, Any], image_path: Path) -> tuple[Path, int]:
    """Add the latest OCR result to the persistent chat source context."""

    return append_chat_image_context(config, "ocr", image_path)


def append_chat_img_context(config: dict[str, Any], image_path: Path) -> tuple[Path, int]:
    """Add the latest image description to the persistent chat source context."""

    return append_chat_image_context(config, "img", image_path)


def chat_command_default_file(command_name: str) -> str:
    """Read and validate the optional-output default for one chat command."""

    default_file = load_chat_command_settings(command_name).get("default_file")
    if not isinstance(default_file, str) or not default_file.strip():
        raise ValueError(f"Invalid /{command_name} default_file in {CHAT_COMMANDS_CONFIG_PATH.name}.")
    return default_file


def chat_context_status(config: dict[str, Any]) -> tuple[int, int, int]:
    """Return the number of sources, conversation turns, and context characters."""

    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    source_count = len(re.findall(r"(?m)^## (?:Web source|File source|\[[^\]]+\])$", source_context))
    turn_count = len(re.findall(r"(?m)^- user:$", conversation_turns))
    return source_count, turn_count, len(context_path.read_text(encoding="utf-8-sig"))


def list_chat_context_sources(config: dict[str, Any]) -> list[str]:
    """Return concise descriptions of the source sections in the chat context."""

    context_path = ensure_chat_context_file(config)
    source_context, _conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    headings = list(re.finditer(r"(?m)^## (Web source|File source|\[[^\]]+\])$", source_context))
    sources: list[str] = []
    for index, heading in enumerate(headings):
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(source_context)
        section = source_context[heading.end() : section_end]
        details = re.search(r"(?m)^(?:URL|Path|Image|Database):\s*(.+)$", section)
        label = heading.group(1)
        sources.append(f"{label}: {details.group(1).strip()}" if details else label)
    return sources


def append_chat_clipboard_context(config: dict[str, Any], text: str) -> int:
    """Append non-empty clipboard text to the persistent chat source context."""

    if not text.strip():
        raise ValueError("Clipboard does not contain text.")
    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    source = f"## [CLIPBOARD]\n\n{text.strip()}"
    write_chat_context(context_path, "\n\n".join(part for part in (source_context, source) if part), conversation_turns)
    return len(text)


def read_clipboard_text() -> str:
    """Read text from the desktop clipboard without keeping a visible Tk window."""

    try:
        import tkinter

        window = tkinter.Tk()
        window.withdraw()
        window.update()
        text = window.clipboard_get()
    except Exception as error:
        raise ValueError(f"Could not read text from the clipboard: {error}") from error
    finally:
        if "window" in locals():
            window.destroy()
    return text if isinstance(text, str) else str(text)


def find_chat_project_text(config: dict[str, Any], search_text: str) -> list[tuple[str, int, str]]:
    """Find up to a bounded number of literal text matches in the active project."""

    project_directory = active_project_directory(config).resolve()
    needle = search_text.casefold()
    matches: list[tuple[str, int, str]] = []
    for file_path in project_directory.rglob("*"):
        if len(matches) >= CHAT_FIND_MAX_RESULTS:
            break
        if not file_path.is_file() or file_path.suffix.casefold() not in CHAT_FIND_TEXT_EXTENSIONS:
            continue
        try:
            if file_path.stat().st_size > CHAT_FIND_MAX_FILE_BYTES:
                continue
            content = file_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        match_index = content.casefold().find(needle)
        if match_index < 0:
            continue
        line_number = content.count("\n", 0, match_index) + 1
        line_end = content.find("\n", match_index)
        line = content[content.rfind("\n", 0, match_index) + 1 : line_end if line_end >= 0 else len(content)].strip()
        matches.append((file_path.relative_to(project_directory).as_posix(), line_number, line[:180]))
    return matches


def list_chat_project_files(config: dict[str, Any]) -> tuple[list[str], int]:
    """List project-local files recursively, limiting only the rendered result count."""

    project_directory = active_project_directory(config).resolve()
    all_files = sorted(
        (
            path.relative_to(project_directory).as_posix()
            for path in project_directory.rglob("*")
            if path.is_file()
        ),
        key=str.casefold,
    )
    return all_files[:CHAT_FILES_MAX_RESULTS], len(all_files)


def read_chat_last_reply(config: dict[str, Any]) -> str:
    """Read the latest model reply saved by the chat flow."""

    reply_path = active_project_directory(config) / CHAT_REPLY_FILENAME
    try:
        text = reply_path.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        raise ValueError(f"Could not read the latest chat reply: {error}") from error
    if not text:
        raise ValueError("The latest chat reply is empty.")
    return text


def render_chat_reply(config: dict[str, Any]) -> None:
    """Render the latest saved chat reply with James' small Markdown subset."""

    for line in read_chat_last_reply(config).splitlines():
        print(render_markdown_line(line, config))
    print()


def read_chat_transform_input(config: dict[str, Any], command_name: str, filename: str) -> tuple[str, str]:
    """Read the latest reply or one project text file for a text-transform command."""

    if not filename:
        return read_chat_last_reply(config), "[last reply]"
    file_path = resolve_chat_context_file(config, filename, command_name=f"/{command_name}")
    try:
        text = file_path.read_text(encoding="utf-8-sig").strip()
    except UnicodeDecodeError as error:
        raise ValueError(f"/{command_name} accepts UTF-8 text files only: {filename}") from error
    except OSError as error:
        raise ValueError(f"Could not read project file {filename}: {error}") from error
    if not text:
        raise ValueError(f"Project file is empty: {filename}")
    display_path = file_path.relative_to(active_project_directory(config).resolve()).as_posix()
    return text, display_path


def drop_chat_ocr_context(config: dict[str, Any]) -> int:
    """Remove every ``[OCR]`` source while preserving other sources and turns."""

    _task, _sc_commands, _output_file, context_label = chat_image_command_settings("ocr")
    context_path = ensure_chat_context_file(config)
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    source_heading = r"(?:Web source|File source|\[[^\]]+\])"
    pattern = rf"(?ms)^## \[{re.escape(context_label)}\]\n.*?(?=^## {source_heading}\n|\Z)"
    updated_source, removed_count = re.subn(pattern, "", source_context)
    if not removed_count:
        raise ValueError("No [OCR] source is present in the chat context.")
    write_chat_context(context_path, updated_source.strip(), conversation_turns)
    return removed_count


def save_chat_context(config: dict[str, Any], filename: str) -> Path:
    """Export the current persistent chat context into a project-local file."""

    output_name = filename or chat_command_default_file("save")
    output_path = resolve_chat_project_path(config, output_name, must_exist=False)
    context_path = ensure_chat_context_file(config).resolve()
    if output_path == context_path:
        raise ValueError(f"Cannot export over {CHAT_CONTEXT_FILENAME}.")
    try:
        output_path.write_text(context_path.read_text(encoding="utf-8-sig"), encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not save chat export {output_name}: {error}") from error
    return output_path


def load_chat_context(config: dict[str, Any], filename: str) -> tuple[Path, int]:
    """Replace the current chat context with one UTF-8 project file."""

    source_path = resolve_chat_context_file(config, filename)
    context_path = ensure_chat_context_file(config).resolve()
    if source_path == context_path:
        raise ValueError(f"Cannot load {CHAT_CONTEXT_FILENAME} over itself.")
    try:
        content = source_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"/load accepts UTF-8 text files only: {filename}") from error
    except OSError as error:
        raise ValueError(f"Could not read chat context file {filename}: {error}") from error
    if not content.strip():
        raise ValueError(f"Chat context file is empty: {filename}")
    try:
        context_path.write_text(content.strip() + "\n", encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not replace the chat context: {error}") from error
    return source_path, len(content)


def append_chat_file_context(config: dict[str, Any], filename: str) -> tuple[Path, int]:
    """Append a project text file to the persistent source section of chat context."""

    file_path = resolve_chat_context_file(config, filename)
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"/add accepts UTF-8 text files only: {filename}") from error
    except OSError as error:
        raise ValueError(f"Could not read project file {filename}: {error}") from error
    if not text.strip():
        raise ValueError(f"Project file is empty: {filename}")

    context_path = ensure_chat_context_file(config)
    if file_path == context_path.resolve():
        raise ValueError(f"Cannot add {CHAT_CONTEXT_FILENAME} to itself.")
    source_context, conversation_turns = split_chat_context(context_path.read_text(encoding="utf-8-sig"))
    display_path = file_path.relative_to(active_project_directory(config).resolve()).as_posix()
    source = f"## File source\nPath: {display_path}\n\n{text.strip()}"
    write_chat_context(context_path, "\n\n".join(part for part in (source_context, source) if part), conversation_turns)
    return file_path, len(text)


def chat_summary_prompt(language: str) -> str:
    """Return the local instruction used to summarize the active chat context."""

    prompts = {
        "cz": (
            "Shrň aktuální kontext konverzace. Zachovej důležitá fakta, rozhodnutí, "
            "otevřené otázky a další kroky. Piš stručně česky v Markdownu."
        ),
        "en": (
            "Summarize the current conversation context. Preserve important facts, decisions, "
            "open questions, and next steps. Write a concise Markdown summary."
        ),
        "es": (
            "Resume el contexto actual de la conversación. Conserva los hechos importantes, "
            "decisiones, preguntas abiertas y próximos pasos. Escribe un resumen breve en Markdown."
        ),
    }
    return prompts.get(language, prompts["en"])


def save_chat_summary(config: dict[str, Any]) -> Path:
    """Copy the latest model reply into the project's persistent chat summary."""

    project_directory = active_project_directory(config)
    reply_path = project_directory / CHAT_REPLY_FILENAME
    try:
        summary = reply_path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError as error:
        raise ValueError(f"Chat summary is missing: {CHAT_REPLY_FILENAME}") from error
    if not summary:
        raise ValueError("Chat summary is empty; no file was saved.")
    summary_path = project_directory / CHAT_SUMMARY_FILENAME
    summary_path.write_text(summary + "\n", encoding="utf-8")
    return summary_path


def clear_chat_context(config: dict[str, Any]) -> None:
    """Discard active exchanges while keeping a valid first-turn context."""

    context_path = active_project_directory(config) / CHAT_CONTEXT_FILENAME
    context_path.write_text(CHAT_INITIAL_CONTEXT, encoding="utf-8")


def render_chat_commands() -> None:
    """Show chat-local commands and the catalog slash-command shortcut."""

    terminal = Terminal()
    print(
        f"{terminal.style('/hlp', fg='yellow', bold=True)} help chat commands   "
        f"{terminal.style('/cmd', fg='yellow', bold=True)} show slash-command catalog   "
        f"{terminal.style('/bye', fg='yellow', bold=True)} quit chat"
    )
    print(
        f"{terminal.style('/COMMAND [/MODIFIER ...] [message]', fg='yellow', bold=True)} use a command plus compatible modifiers"
    )
    print(f"{terminal.style('/task [TASK.json]', fg='yellow', bold=True)} list or select an experimental Chat task override")
    print()


def render_chat_help(config: dict[str, Any]) -> None:
    """Print the chat command help without leaving the active chat session."""

    try:
        content = CHAT_COMMANDS_PATH.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        Terminal().r(f"Cannot read chat help: {error}")
        return
    for line in content.splitlines():
        print(render_markdown_line(line, config))
    print()


def render_chat_slash_commands(config: dict[str, Any]) -> None:
    """Show the localized slash-command catalog without leaving the active chat."""

    document_path = slash_commands_document_path(config)
    try:
        content = document_path.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        Terminal().r(f"Cannot read slash-command catalog: {error}")
        return
    for line in content.splitlines():
        print(render_markdown_line(line, config))
    print()


def render_chat_tasks(active_task: str | None) -> None:
    """List task JSON files that can temporarily override the Chat flow's default task."""

    task_names = available_chat_tasks()
    terminal = Terminal()
    Terminal().c("Available Chat tasks:")
    for task_name in task_names:
        rendered_name = terminal.style(task_name, fg="yellow", bold=True) if task_name == active_task else task_name
        print(f"- {rendered_name}")
    selected = active_task or "the flow default"
    print(f"Active task: {selected}")
    print("Use /task TASK.json to change the task for the rest of this Chat session.")
    print()


def extract_chat_mod_command(message: str) -> tuple[str | None, str] | None:
    """Split a leading ``/mod [NEW]`` command from the chat message, if present.

    Returns ``(None, "")`` for bare ``/mod`` so Chat can list models.
    Otherwise returns ``(new_model, remaining_message)``. Returns ``None``
    when the message does not start with ``/mod`` at all.
    """

    mod_match = re.match(r"^\s*/mod(?:\s+(\S+)(?:\s+(.*))?)?\s*$", message, re.IGNORECASE | re.DOTALL)
    if mod_match is None:
        return None
    new_model = mod_match.group(1)
    if not new_model:
        return None, ""
    remaining_message = (mod_match.group(2) or "").strip()
    return new_model, remaining_message


def extract_chat_lng_command(message: str) -> str | None:
    """Return a supported language from an exclusive ``/lng [LANGUAGE]`` command."""

    command_match = re.match(r"^\s*/lng(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    language = (command_match.group(1) or "").strip().casefold()
    if not language:
        return ""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported chat language: {language}. Available: {', '.join(SUPPORTED_LANGUAGES)}.")
    return language


def render_chat_models(active_model: str) -> None:
    """List local Ollama models and highlight the active Chat model in yellow."""

    try:
        result = subprocess.run(
            ["ollama", "list"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        Terminal().r(f"Could not run 'ollama list': {error}")
        return
    output = result.stdout.strip()
    if not output:
        Terminal().y(result.stderr.strip() or "No Ollama models were reported.")
        if result.returncode:
            Terminal().r(f"'ollama list' exited with code {result.returncode}.")
        return

    Terminal().c("Ollama models; active Chat model is yellow:")
    terminal = Terminal()
    for index, line in enumerate(output.splitlines()):
        if index == 0:
            print(line)
            continue
        model_name, separator, details = line.partition(" ")
        if model_name == active_model:
            print(f"{terminal.color('yellow', model_name)}{separator}{details}")
        else:
            print(line)
    if result.returncode:
        Terminal().r(f"'ollama list' exited with code {result.returncode}.")
    print()


def render_chat_languages(active_language: str) -> None:
    """List Chat languages and highlight the language active for this session."""

    terminal = Terminal()
    Terminal().c("Chat languages:")
    for language in SUPPORTED_LANGUAGES:
        rendered = terminal.style(language, fg="yellow", bold=True) if language == active_language else language
        print(f"- {rendered}")
    print("Use /lng LANGUAGE to switch for this Chat session.")
    print()


def extract_chat_sc_command(message: str) -> tuple[str, list[str]]:
    """Take consecutive leading catalog slash commands out of a chat message.

    Chat-local commands such as ``/hlp``, ``/url``, ``/cat``, ``/cam``, ``/ocr``, ``/img``, ``/ctx``, ``/src``, ``/find``, ``/files``, ``/clip``,
    ``/last``, ``/debug``, ``/tool``, ``/drop``, ``/save``, and ``/load``
    are processed earlier by :func:`run_chat` and remain exclusive James commands. Every catalog command kind is valid
    here; the normal ``cli_ollama`` validation still rejects incompatible
    command combinations when a flow is executed.
    """

    try:
        catalog = json.loads(SC_COMMAND_CATALOG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load slash-command catalog: {error}") from error
    groups = catalog.get("groups") if isinstance(catalog, dict) else None
    if not isinstance(groups, list):
        raise ValueError("Slash-command catalog requires a command-group list.")
    catalog_names: dict[str, str] = {}
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("commands"), list):
            continue
        for command in group["commands"]:
            if not isinstance(command, dict):
                continue
            name = command.get("sc")
            if not isinstance(name, str) or not name.strip():
                continue
            aliases = command.get("aliases", [])
            names = [name, *aliases] if isinstance(aliases, list) else [name]
            for candidate in names:
                if isinstance(candidate, str) and candidate.strip():
                    catalog_names[candidate.removeprefix("/").casefold()] = name

    remaining_message = message.strip()
    commands: list[str] = []
    while command_match := re.match(r"^/([A-Za-z0-9_-]+)(?:\s+|$)", remaining_message):
        command_name = catalog_names.get(command_match.group(1).casefold())
        if command_name is None:
            break
        commands.append(command_name)
        remaining_message = remaining_message[command_match.end() :].strip()
    if not commands:
        return message.strip(), []
    return remaining_message, commands


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

    config = dict(config)
    if not set_chat_selector():
        pause()
        return
    ensure_chat_context_file(config)
    try:
        chat_debug = chat_debug_default()
        active_task = chat_task_default()
        active_model = chat_task_model(active_task)
    except ValueError as error:
        Terminal().r(str(error))
        pause()
        return
    active_rag_profile: DatabaseProfile | None = None
    clear_screen()
    render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
    render_chat_commands()
    while True:
        try:
            message = read_chat_message()
        except EOFError:
            return
        if message.strip().casefold() == "/hlp":
            render_chat_help(config)
            continue
        if is_chat_cmd_command(message):
            render_chat_slash_commands(config)
            continue
        requested_task = extract_chat_task_command(message)
        if requested_task is not None:
            if not requested_task:
                try:
                    render_chat_tasks(active_task)
                except ValueError as error:
                    Terminal().y(str(error))
                continue
            try:
                active_task = select_chat_task(requested_task)
                active_model = chat_task_model(active_task)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Chat task selected for this session: {active_task} (Model: {active_model}).")
            continue
        if message.strip() == "/bye":
            return
        if message.strip() == "/clr":
            clear_chat_context(config)
            clear_chat_active_image(config)
            clear_screen()
            render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
            render_chat_commands()
            Terminal().g("Chat context cleared.")
            continue
        try:
            requested_language = extract_chat_lng_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if requested_language is not None:
            if not requested_language:
                render_chat_languages(str(config["language"]))
                continue
            config["language"] = requested_language
            clear_screen()
            render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
            render_chat_commands()
            Terminal().g(f"Chat language set to {requested_language} for this session.")
            continue
        try:
            rag_name = extract_chat_rag_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if rag_name is not None:
            if rag_name == "off":
                active_rag_profile = None
                removed_count = drop_chat_rag_context(config)
                clear_screen()
                render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
                render_chat_commands()
                Terminal().g(f"RAG disconnected; removed {removed_count} RAG context source(s).")
                continue
            try:
                selected_rag_profile = select_chat_rag_profile(rag_name)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            removed_count = drop_chat_rag_context(config)
            active_rag_profile = selected_rag_profile
            clear_screen()
            render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
            render_chat_commands()
            Terminal().g(
                f"RAG wiki selected: {active_rag_profile.path.name}. "
                f"Removed {removed_count} previous RAG context source(s). "
                f"Use /chunk FILTER[, FILTER ...] (default {chat_rag_chunk_count_default()}), or /chunk N FILTER."
            )
            continue
        try:
            chunk_request = extract_chat_chunk_command(message, chat_rag_chunk_count_default())
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if chunk_request is not None:
            if active_rag_profile is None:
                Terminal().y("Select a RAG wiki first, for example /rag btc.")
                continue
            chunk_count, chunk_input = chunk_request
            try:
                rag_tags, rag_operators, remaining_text = split_chat_rag_filter_expression(chunk_input)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            if rag_tags and remaining_text:
                Terminal().y("/chunk only attaches retrieval filters; enter the chat question on the next line.")
                continue
            search_query = chat_rag_tag_query(rag_tags, rag_operators) if rag_tags else chunk_input
            Terminal().c(f"Searching {active_rag_profile.path.name} for {chunk_count} chunk(s)…")
            try:
                rag_context, hit_count = build_chat_rag_context(active_rag_profile, search_query, chunk_count)
                replace_chat_rag_context(config, rag_context)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            render_chat_rag_context(config, rag_context)
            Terminal().g(f"Added {hit_count} RAG chunk(s); enter a chat question.")
            continue
        try:
            url = extract_chat_url_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if url is not None:
            Terminal().c(f"Loading {url}…")
            try:
                title, text = fetch_chat_url_text(url)
                append_chat_url_context(config, url, title, text)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Added web page to chat context: {title} ({len(text):,} characters).")
            continue
        try:
            filename = extract_chat_add_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if filename is not None:
            try:
                file_path, character_count = append_chat_file_context(config, filename)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Added project file to chat context: {file_path.name} ({character_count:,} characters).")
            continue
        try:
            cat_filename = extract_chat_cat_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if cat_filename is not None:
            try:
                file_path, content = read_chat_project_file(config, cat_filename)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().c(f"{file_path.relative_to(active_project_directory(config).resolve()).as_posix()}:")
            if file_path.suffix.casefold() == ".md":
                for line in content.splitlines():
                    print(render_markdown_line(line, config))
            else:
                print(content, end="" if content.endswith("\n") else "\n")
            print()
            continue
        if is_chat_ctx_command(message):
            try:
                source_count, turn_count, character_count = chat_context_status(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().c(
                f"Chat context: {source_count} source(s), {turn_count} conversation turn(s), "
                f"{character_count:,} characters."
            )
            continue
        if is_chat_src_command(message):
            try:
                sources = list_chat_context_sources(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            if not sources:
                Terminal().c("Chat context has no attached sources.")
                continue
            Terminal().c("Chat context sources:")
            for source in sources:
                print(f"- {source}")
            continue
        try:
            find_text = extract_chat_find_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if find_text is not None:
            try:
                matches = find_chat_project_text(config, find_text)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            if not matches:
                Terminal().c(f"No project text files match: {find_text}")
                continue
            Terminal().c(f"Project matches for {find_text!r}; add one with /add FILE:")
            for filename, line_number, line in matches:
                print(f"- {filename}:{line_number}: {line}")
            if len(matches) == CHAT_FIND_MAX_RESULTS:
                Terminal().y(f"Showing the first {CHAT_FIND_MAX_RESULTS} matches.")
            continue
        if is_chat_files_command(message):
            try:
                files, total_count = list_chat_project_files(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            if not files:
                Terminal().c("The active project has no files.")
                continue
            Terminal().c(f"Project files ({total_count}):")
            for filename in files:
                print(f"- {filename}")
            if total_count > len(files):
                Terminal().y(f"Showing the first {len(files)} files.")
            continue
        if is_chat_clip_command(message):
            try:
                character_count = append_chat_clipboard_context(config, read_clipboard_text())
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Clipboard text added to chat context ({character_count:,} characters).")
            continue
        if is_chat_last_command(message):
            try:
                last_reply = read_chat_last_reply(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().c("Latest chat reply:")
            for line in last_reply.splitlines():
                print(render_markdown_line(line, config))
            print()
            continue
        try:
            debug_action = extract_chat_debug_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if debug_action is not None:
            if debug_action == "on":
                chat_debug = True
            elif debug_action == "off":
                chat_debug = False
            clear_screen()
            render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
            render_chat_commands()
            Terminal().c(f"Chat debug: {'on' if chat_debug else 'off'}.")
            continue
        try:
            tool_arguments = extract_chat_tool_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if tool_arguments is not None:
            try:
                run_chat_tool(tool_arguments)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g("cli_tool.py completed.")
            continue
        try:
            drop_source = extract_chat_drop_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if drop_source is not None:
            if drop_source != "ocr":
                Terminal().y("Only /drop ocr is currently supported.")
                continue
            try:
                removed_count = drop_chat_ocr_context(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Removed {removed_count} [OCR] source(s) from the chat context.")
            continue
        save_filename = extract_chat_save_command(message)
        if save_filename is not None:
            try:
                export_path = save_chat_context(config, save_filename)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Chat context saved: {export_path.name}")
            continue
        try:
            load_filename = extract_chat_load_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if load_filename is not None:
            try:
                source_path, character_count = load_chat_context(config, load_filename)
                clear_chat_active_image(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Chat context replaced from {source_path.name} ({character_count:,} characters).")
            continue
        camera_filename = extract_chat_cam_command(message)
        if camera_filename is not None:
            try:
                camera_filename = camera_filename or chat_command_default_file("camera")
                image_path = capture_chat_camera(config, camera_filename, debug=chat_debug)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Camera image saved: {image_path}")
            continue
        ocr_filename = extract_chat_ocr_command(message)
        if ocr_filename is not None:
            try:
                ocr_filename = ocr_filename or chat_command_default_file("camera")
                image_path = run_chat_ocr(config, ocr_filename)
                output_path, character_count = append_chat_ocr_context(config, image_path)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"OCR completed and added to chat context: {output_path.name} ({character_count:,} characters).")
            continue
        img_filename = extract_chat_img_command(message)
        if img_filename is not None:
            try:
                img_filename = img_filename or chat_command_default_file("camera")
                image_path = run_chat_img(config, img_filename)
                output_path, character_count = append_chat_img_context(config, image_path)
                active_image = set_chat_active_image(config, image_path)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(
                f"Image description added to chat context: {output_path.name} ({character_count:,} characters). "
                f"Vision image active: {active_image}"
            )
            continue
        if is_chat_sum_command(message):
            write_chat_input(config, chat_summary_prompt(str(config["language"])))
            exit_code = run_flow(
                chat_flow_name(config),
                pause_after=False,
                report_result=False,
                clear_before=False,
                model_override=active_model,
                task_override=active_task,
                capture_output=not chat_debug,
            )
            if exit_code:
                pause()
                return
            if not chat_debug:
                try:
                    render_chat_reply(config)
                except ValueError as error:
                    Terminal().y(str(error))
                    continue
            try:
                summary_path = save_chat_summary(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Chat summary saved: {summary_path.name}")
            continue
        try:
            mod_result = extract_chat_mod_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if mod_result is not None:
            requested_model, remaining_message = mod_result
            if requested_model is None:
                render_chat_models(active_model)
                continue
            active_model = requested_model
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
        try:
            last_reply_commands, last_reply_label, last_reply_flow = chat_last_reply_sc_settings(config)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        transform_commands = [command for command in sc_commands if command.casefold() in last_reply_commands]
        if len(transform_commands) == 1:
            transform_command = transform_commands[0]
            try:
                prompt, history_prompt = read_chat_transform_input(config, transform_command, prompt)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            write_chat_input(config, prompt)
            exit_code = run_flow(
                last_reply_flow,
                pause_after=False,
                report_result=False,
                clear_before=False,
                model_override=active_model,
                task_override=active_task,
                sc_commands=sc_commands,
                sc_language=str(config["language"]),
                capture_output=not chat_debug,
            )
            if exit_code:
                pause()
                return
            if not chat_debug:
                try:
                    render_chat_reply(config)
                except ValueError as error:
                    Terminal().y(str(error))
                    continue
            append_chat_turn(config, f"/{transform_command} {history_prompt if history_prompt != '[last reply]' else last_reply_label}")
            continue
        history_prompt = prompt
        if not prompt and sc_commands:
            try:
                prompt, history_label = chat_sc_context_defaults(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            history_prompt = f"/{sc_commands[0]} {history_label}"
        write_chat_input(config, prompt)
        try:
            active_image = read_chat_active_image(config)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        exit_code = run_flow(
            chat_flow_name(config),
            pause_after=False,
            report_result=False,
            clear_before=False,
            model_override=active_model,
            task_override=active_task,
            sc_commands=sc_commands,
            image_file=active_image,
            capture_output=not chat_debug,
        )
        if exit_code:
            pause()
            return
        if not chat_debug:
            try:
                render_chat_reply(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
        append_chat_turn(config, history_prompt)


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
        elif key == "i":
            try:
                show_flow_info(config, str(flows[selected_index]), title)
            except ValueError as error:
                Terminal().r(str(error))
                pause()
        elif key in {"\r", "\n"}:
            run_flow(str(flows[selected_index]))


def show_flow_info(config: dict[str, Any], flow_name: str, category_title: str) -> None:
    """Show one configured flow file without running it."""

    flow_path = Path(flow_name)
    if flow_path.name != flow_name or flow_path.suffix.casefold() != ".txt":
        raise ValueError("Flow info requires a flows/*.txt filename without a directory path.")
    selected_path = PROJECT_ROOT / "flows" / flow_name
    if not selected_path.is_file():
        raise ValueError(f"Flow file not found in flows: {flow_name}")
    show_text_document(config, selected_path, f"FLOW · {category_title} · {flow_name}")


def render_flow_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the Flow category menu."""

    terminal = Terminal()
    width = int(config["width"])
    categories = ("test", "single", "code", "batch", "media", "mcp", "rag_wiki")
    clear_screen()
    render_page_header(config, "flow")
    render_section_header(width, "FLOW", config)
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
            selected_index = (selected_index - 1) % len(categories)
        elif key == "down":
            selected_index = (selected_index + 1) % len(categories)
        elif key in {"\r", "\n"}:
            flow_list_menu(config, *categories[selected_index])


def show_help(config: dict[str, Any]) -> None:
    """Display the maintained Help document."""

    show_text_document(config, JAMES_HELP_PATH, "HELP")


def about_document_path(config: dict[str, Any]) -> Path:
    """Choose the Czech About document only for the Czech James language."""

    return JAMES_ABOUT_CZ_PATH if config.get("language") == "cz" else JAMES_ABOUT_PATH


def show_about(config: dict[str, Any]) -> None:
    """Display the About document in the configured James language."""

    show_text_document(config, about_document_path(config), "ABOUT")


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
                show_about(config)
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

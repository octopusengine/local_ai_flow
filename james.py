"""Small cross-platform terminal menu for the local Ollama tools.

Run with ``python james.py``.  The menu reacts to single key presses, so
neither Windows nor Linux needs a shell-specific launcher.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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

from lib.wrapp_agent import (
    DEFAULT_MAX_STEPS,
    SYSTEM_PROMPT as AGENT_SYSTEM_PROMPT,
    AgentCallbacks,
    AgentEngine,
    AgentRun,
    ProjectToolScope,
    ToolPolicy,
    build_file_tools,
    format_session_info,
    load_tool_schema,
    record_agent_run,
    review_agent_run,
    resolve_agent_options,
    session_info_context,
    session_info_requested,
    tools_for_schema,
)
from lib.wrapp_db import (
    DEFAULT_TASKS_SCHEMA_PATH,
    TaskDatabaseError,
    create_database,
    delete_task,
    get_task_row,
    list_task_rows,
    set_task_stars,
    short_text,
)
from lib.wrapp_audio import play_audio_file
from lib.wrapp_md import (
    MARKDOWN_COLOR_DEFAULTS,
    configured_color,
    load_markdown_settings,
    render_bold_markdown,
    render_markdown_line,
    render_markdown_lines,
)
from lib.wrapp_ollama import OllamaEmbeddingError, embed_texts, ollama_api
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
WRAPP_MD_CONFIG_PATH = PROJECT_ROOT / "lib" / "wrapp_md.json"
JAMES_ABOUT_PATH = JAMES_DIRECTORY / "about.md"
JAMES_ABOUT_CZ_PATH = JAMES_DIRECTORY / "about_cz.md"
JAMES_HELP_PATH = JAMES_DIRECTORY / "james_help.md"
CHAT_COMMANDS_PATH = JAMES_DIRECTORY / "chat_cmd.md"
CHAT_COMMANDS_CONFIG_PATH = JAMES_DIRECTORY / "chat_cmd.json"
ASSISTANT_TASKS_PATH = PROJECT_ROOT / "assistant" / "tasks"
SC_COMMAND_CATALOG_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc.json"
SC_COMMANDS_CZ_PATH = PROJECT_ROOT / "assistant" / "commands" / "sc_cz.md"
SC_COMMANDS_DEFAULT_PATH = PROJECT_ROOT / "assistant" / "commands" / "README.md"
__version__ = "0.3.1"
DATABASE_SCRIPT_PATH = PROJECT_ROOT / "cli_db.py"
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "runner.py"
SPEECH_SCRIPT_PATH = PROJECT_ROOT / "cli_speech.py"
VECTOR_SCRIPT_PATH = PROJECT_ROOT / "cli_vector.py"
CAMERA_SCRIPT_PATH = PROJECT_ROOT / "cli_camera.py"
RECORD_SCRIPT_PATH = PROJECT_ROOT / "cli_record_mp3.py"
WHISPER_SCRIPT_PATH = PROJECT_ROOT / "cli_whisper_mp3.py"
OLLAMA_SCRIPT_PATH = PROJECT_ROOT / "cli_ollama.py"
TOOL_SCRIPT_PATH = PROJECT_ROOT / "cli_tool.py"
OLLAMA_CONFIG_PATH = PROJECT_ROOT / "lib" / "ollama.json"
AGENT_CONFIG_PATH = PROJECT_ROOT / "cli_agent.json"
AGENT_TOOL_SCHEMA_PATH = PROJECT_ROOT / "assistant" / "tools" / "tool_schema.json"
COWORK_AGENTS_CONFIG_PATH = JAMES_DIRECTORY / "agents.json"
MCP_CONFIG_PATH = PROJECT_ROOT / "mcp" / "mcp_config.json"
MCP_SCRIPT_PATH = PROJECT_ROOT / "cli_mcp.py"
MCP_SERVER_PATH = PROJECT_ROOT / "mcp" / "wrapp_mcp_server.py"
MCP_HW_SERVER_CONFIG_PATH = PROJECT_ROOT / "mcp" / "hw_server.json"
MCP_HW_SERVER_PATH = PROJECT_ROOT / "mcp" / "hw_mcp_server.py"
BLE_SCRIPT_PATH = PROJECT_ROOT / "cli_ble.py"
BLE_REQUIREMENTS_PATH = PROJECT_ROOT / "requirements_ble.txt"
NOSTR_SCRIPT_PATH = PROJECT_ROOT / "cli_nostr.py"
NOSTR_REQUIREMENTS_PATH = PROJECT_ROOT / "requirements_nostr.txt"
OPTIONAL_WRAPPER_PATHS = (
    ("wrapp_ble", PROJECT_ROOT / "lib" / "wrapp_ble.py"),
    ("wrapp_nostr", PROJECT_ROOT / "lib" / "wrapp_nostr.py"),
)
VECTOR_CONFIG_PATH = PROJECT_ROOT / "cli_vector.json"
VECTOR_DATABASES_PATH = PROJECT_ROOT / "rag_wiki" / "databases.json"
MENU_INDENT = " " * 7
CHAT_FLOW_NAME_TEMPLATE = "flow_chat_{language}.json"
CHAT_CONTEXT_FILENAME = "chat_context.txt"
CHAT_REPLY_FILENAME = "chat_reply.txt"
CHAT_INPUT_FILENAME = "chat_input.txt"
CHAT_SUMMARY_FILENAME = "chat_summary.txt"
CHAT_ACTIVE_IMAGE_FILENAME = "chat_active_image.txt"
CHAT_PROJECT_SUBDIR_OVERRIDE_KEY = "_chat_project_subdir"
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
DEFAULT_COWORK_MODEL = "gpt-oss:latest"
HARDWARE_AGENT_SYSTEM_PROMPT = """You are a careful local hardware agent.
Call hardware_list_devices when the user asks what is available or a device or
action is not already established in this conversation. Do not search project
files to guess hardware capabilities, and do not reload the catalog before
every action. Use only established device_id values and agent-enabled action_id
values; never invent or substitute a color, BLE UUID, payload, address, key,
command, or action ID.

For a request containing several actions, execute every supported requested
action once through hardware_run_action, and separately report unsupported
actions. Never claim a physical action succeeded until its tool result has
"ok": true. If the device is disconnected or an action fails, report that
structured error and do not retry a physical action unless the user explicitly
asks. You may inspect project files only when the request is genuinely about
the project; local secret files are unavailable."""
NOSTR_AGENT_SYSTEM_PROMPT = """You are a careful local Nostr work agent.
Your Nostr capability is deliberately narrow: synchronize recent messages from
relays, inspect only messages whose sender is allowed by the local whitelist,
carry out work the user has authorized using the available light and hardware
tools, record a concise handling report, then send at most one reply. Never
send a general Nostr message, add a contact, publish an event, change relay
configuration, or reply before nostr_mark_handled succeeds. Never invent a
message ID, sender, hardware action, or claim delivery until nostr_reply
returns confirmation.

Use nostr_status or nostr_doctor for local setup problems and nostr_list_relays
only for relay diagnostics. Use system_datetime before interpreting a request
such as "today's messages"; message records include their saved_at time. Do
not retry receiving, physical actions, or a reply unless the user explicitly
asks. The Nostr policy is owned by the local host configuration, outside the
active project: never search project files for it, never try to modify it, and
never use light tools to work around a disabled-policy error. If a Nostr tool
reports a disabled policy or empty whitelist, state that exact blocker once
and stop. nostr_list_messages is intentionally capped by local policy: use its
default limit, summarize the returned items, and do not request a larger batch
when has_more is true. For a request about the latest messages, always call
nostr_sync first. It fetches silently and returns only a count; wait for that
result, then call nostr_list_messages and use the newest returned content as
the working prompt. Local secret files are unavailable."""
COWORK_DIRECTORY_NAME = ".cowork"
COWORK_PLANS_FILENAME = "plans.json"
COWORK_PLAN_STEP_STATUSES = ("todo", "in_progress", "done", "blocked", "skipped")
PLAN_PREPARE_TOOL_NAMES = frozenset(
    {"session_info", "list_files", "read_file", "find_text", "file_info", "python_runtime_info", "web_runtime_info", "browser_test"}
)
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
CHAT_AUDIO_EXTENSION = ".mp3"
SUPPORTED_LANGUAGES = ("cz", "en", "es")
FLOW_CATEGORY_KEYS = (
    "flows_test",
    "flows_single",
    "flows_code",
    "flows_batch",
    "flows_media",
    "flows_mcp_base",
    "flows_mcp_hardware",
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


@dataclass
class CoworkSession:
    """Session-local Agent settings; never writes a selected project to project.json."""

    project_directory: Path
    agent_id: str = "code"
    agent_label: str = "coding session"
    model: str = DEFAULT_COWORK_MODEL
    policy: ToolPolicy = ToolPolicy.CODE
    run_confirm: bool = True
    auto_continue: bool = True
    review_enabled: bool = False
    tool_schema_light: bool = True
    tool_schema_profile: str | None = None
    agent_options: dict[str, int | float] | None = None
    db_enabled: bool = True
    db_selector: str = "agent"


@dataclass(frozen=True)
class CoworkAgentProfile:
    """One declarative Cowork agent variant from ``james/agents.json``."""

    agent_id: str
    label: str
    description: str
    model: str
    agent_options: dict[str, int | float]
    tool_schema_profile: str


def load_cowork_agents_config() -> dict[str, CoworkAgentProfile]:
    """Load named Cowork variants and validate their declared tool profiles.

    ``cli_agent.json`` remains the shared source for runtime defaults such as
    persistence, confirmation and Ollama options. This smaller catalog owns
    the independently selectable model and capability profile of each session.
    """

    shared_settings = load_cowork_agent_config()
    try:
        data = json.loads(COWORK_AGENTS_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise ValueError(f"Cannot read {COWORK_AGENTS_CONFIG_PATH}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {COWORK_AGENTS_CONFIG_PATH}: {error}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"{COWORK_AGENTS_CONFIG_PATH.name} must contain a version 1 JSON object.")
    agents = data.get("agents")
    if not isinstance(agents, dict) or not agents:
        raise ValueError(f"{COWORK_AGENTS_CONFIG_PATH.name} requires a non-empty 'agents' object.")

    profiles: dict[str, CoworkAgentProfile] = {}
    for agent_id, raw_profile in agents.items():
        if not isinstance(agent_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", agent_id):
            raise ValueError(f"{COWORK_AGENTS_CONFIG_PATH.name} agent IDs must use lowercase letters, digits, '-' or '_'.")
        if not isinstance(raw_profile, dict):
            raise ValueError(f"Agent '{agent_id}' must be an object.")
        values: dict[str, str] = {}
        for field_name in ("label", "description", "model", "tools"):
            value = raw_profile.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Agent '{agent_id}' requires non-empty text field '{field_name}'.")
            values[field_name] = value.strip()
        try:
            options = resolve_agent_options(dict(shared_settings["options"]), raw_profile.get("options"))
        except ValueError as error:
            raise ValueError(f"Agent '{agent_id}' has invalid options: {error}") from error
        try:
            load_tool_schema(AGENT_TOOL_SCHEMA_PATH, values["tools"])
        except ValueError as error:
            raise ValueError(f"Agent '{agent_id}' has invalid tools profile: {error}") from error
        profiles[agent_id] = CoworkAgentProfile(
            agent_id=agent_id,
            label=values["label"],
            description=values["description"],
            model=values["model"],
            agent_options=options,
            tool_schema_profile=values["tools"],
        )
    return profiles


def load_cowork_agent_config() -> dict[str, object]:
    """Load the runtime policy shared with ``cli_agent.json``."""
    try:
        data = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise ValueError(f"Cannot read {AGENT_CONFIG_PATH.name}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {AGENT_CONFIG_PATH.name}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{AGENT_CONFIG_PATH.name} must contain a JSON object.")
    for name in ("log", "db", "run_confirm", "auto_continue", "review", "tool_schema_light"):
        if not isinstance(data.get(name), bool):
            raise ValueError(f"{AGENT_CONFIG_PATH.name} requires '{name}': true or false.")
    model = data.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"{AGENT_CONFIG_PATH.name} requires a non-empty 'model'.")
    options = resolve_agent_options({}, data.get("options"))
    selector = data.get("selector", "agent")
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError(f"{AGENT_CONFIG_PATH.name} requires a non-empty 'selector'.")
    explicit_schema_profile = data.get("tool_schema_profile")
    if explicit_schema_profile is None:
        schema_profile = "light" if data["tool_schema_light"] else "extended"
    elif not isinstance(explicit_schema_profile, str) or not explicit_schema_profile.strip():
        raise ValueError(f"{AGENT_CONFIG_PATH.name} field 'tool_schema_profile' must be non-empty text when present.")
    else:
        schema_profile = explicit_schema_profile.strip()
    return {
        "log": data["log"],
        "db": data["db"],
        "model": model.strip(),
        "options": options,
        "run_confirm": data["run_confirm"],
        "auto_continue": data["auto_continue"],
        "review": data["review"],
        "tool_schema_light": data["tool_schema_light"],
        "tool_schema_profile": schema_profile,
        "selector": selector,
    }


def cowork_schema_profile(session: CoworkSession) -> str:
    """Return the explicit schema profile, preserving old light/extended sessions."""

    return session.tool_schema_profile or ("light" if session.tool_schema_light else "extended")


def cowork_session_from_profile(project_directory: Path, profile: CoworkAgentProfile) -> CoworkSession:
    """Create one independent Cowork session from its named agent profile."""

    settings = load_cowork_agent_config()
    is_hardware = profile.tool_schema_profile == "hardware"
    is_nostr = profile.tool_schema_profile == "nostr"
    return CoworkSession(
        project_directory=project_directory,
        agent_id=profile.agent_id,
        agent_label=profile.label,
        model=profile.model,
        agent_options=dict(profile.agent_options),
        run_confirm=bool(settings["run_confirm"]),
        # A second model turn must never silently retry or reinterpret a
        # physical action. The hardware result itself is the evidence.
        auto_continue=bool(settings["auto_continue"]) and not (is_hardware or is_nostr),
        review_enabled=bool(settings["review"]) and not (is_hardware or is_nostr),
        tool_schema_light=profile.tool_schema_profile == "light",
        tool_schema_profile=profile.tool_schema_profile,
        db_enabled=bool(settings["db"]),
        db_selector=str(settings["selector"]),
    )


def cowork_system_prompt(session: CoworkSession) -> str:
    """Return the narrow instruction set matching the selected session type."""

    if session.agent_id == "hardware":
        return HARDWARE_AGENT_SYSTEM_PROMPT
    if session.agent_id == "nostr":
        return NOSTR_AGENT_SYSTEM_PROMPT
    return AGENT_SYSTEM_PROMPT


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
    """Parse ``/chunk FILTER`` and use the configured chunk count."""

    command_match = re.match(r"^\s*/chunk(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    if isinstance(default_count, bool) or not isinstance(default_count, int) or default_count <= 0:
        raise ValueError("The default /chunk count must be a positive whole number.")
    argument = (command_match.group(1) or "").strip()
    if not argument:
        raise ValueError("Use /chunk FILTER, for example /chunk #(těžba bitcoinu) or /chunk bitcoin, těžba.")
    if re.match(r"^[+-]?\d+(?:\s|$)", argument):
        raise ValueError("Use /chunk FILTER; the number of chunks is configured in chat_cmd.json.")
    return default_count, argument


def extract_chat_ask_command(message: str) -> tuple[str, str] | None:
    """Parse one ``/ask FILTER :: QUESTION`` command for retrieval and an immediate Chat turn."""

    command_match = re.match(r"^\s*/ask(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    argument = (command_match.group(1) or "").strip()
    filters, separator, question = argument.partition("::")
    if not separator or not filters.strip() or not question.strip():
        raise ValueError("Use /ask FILTER :: QUESTION, for example /ask (bitcoin mining) or (hardware wallet) :: Explain the difference.")
    return filters.strip(), question.strip()


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
    """Return a project-local file name, defaulting bare ``/cat`` to Chat context."""

    command_match = re.match(r"^\s*/cat(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    filename = (command_match.group(1) or "").strip().strip('"')
    return filename or CHAT_CONTEXT_FILENAME


def extract_chat_proj_command(message: str) -> str | None:
    """Return the optional session-only project subdirectory from ``/proj [SUBDIR]``."""

    command_match = re.match(r"^\s*/proj(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_cam_command(message: str) -> str | None:
    """Return the optional requested camera file from an exclusive ``/cam`` command."""

    command_match = re.match(r"^\s*/cam(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_rec_command(message: str) -> str | None:
    """Return the optional destination from an exclusive ``/rec [FILE.mp3]`` command."""

    command_match = re.match(r"^\s*/rec(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_voice_command(message: str) -> str | None:
    """Return the optional destination from ``/voice`` or ``/voi [FILE.mp3]``."""

    command_match = re.match(r"^\s*/(?:voice|voi)(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_whisper_command(message: str) -> str | None:
    """Return the optional source from an exclusive ``/whisper [FILE.mp3]`` command."""

    command_match = re.match(r"^\s*/whisper(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_play_command(message: str) -> str | None:
    """Return the optional source from an exclusive ``/play [FILE.mp3]`` command."""

    command_match = re.match(r"^\s*/play(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    return (command_match.group(1) or "").strip().strip('"')


def extract_chat_say_command(message: str) -> tuple[str, str] | None:
    """Return ``(kind, value)`` for ``/say``, quoted text, or a project file."""

    command_match = re.match(r"^\s*/say(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    value = (command_match.group(1) or "").strip()
    if not value:
        return "last", ""
    if value.startswith('"') or value.endswith('"'):
        if len(value) < 2 or not (value.startswith('"') and value.endswith('"')):
            raise ValueError('Use /say "text", /say FILE, or /say without a parameter.')
        return "text", value[1:-1].strip()
    return "file", value


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


def extract_chat_db_command(message: str) -> int | None:
    """Return a positive task-record ID from an exclusive ``/db ID`` command."""

    command_match = re.match(r"^\s*/db(?:\s+(.*))?\s*$", message, re.IGNORECASE | re.DOTALL)
    if command_match is None:
        return None
    value = (command_match.group(1) or "").strip()
    try:
        task_id = int(value)
    except ValueError as error:
        raise ValueError("Use /db followed by a positive database record ID.") from error
    if task_id < 1:
        raise ValueError("Use /db followed by a positive database record ID.")
    return task_id


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
    """Return whether *message* is the exclusive ``/files`` or ``/ls`` command."""

    return re.fullmatch(r"\s*/(?:files|ls)\s*", message, re.IGNORECASE | re.DOTALL) is not None


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
    raise ValueError("Use /debug, /debug on/off, or /debug true/false.")


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
    markdown_settings = load_markdown_settings(WRAPP_MD_CONFIG_PATH)
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


def ensure_main_database(config: dict[str, Any]) -> Path:
    """Create the configured empty task database once when a clone lacks it.

    Existing databases are intentionally left untouched here; schema validation
    and legacy migration remain explicit database operations. This is the
    in-process equivalent of ``cli_db.py --create tasks.db tasks.json``.
    """

    database_path = main_database_file(config)
    if not database_path.exists():
        create_database(database_path, PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH)
    return database_path


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
        overridden_directory = config.get(CHAT_PROJECT_SUBDIR_OVERRIDE_KEY)
        if overridden_directory is not None:
            if not isinstance(overridden_directory, str):
                raise ValueError("Chat project override must be text.")
            return validate_directory_name(overridden_directory)
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
        print(f"{config.get('name', 'James')} - v{__version__} | debug: {str(chat_debug).lower()}")
        details = f"| project: {terminal.color('yellow', active_project_name(config))} | {language}"
        if chat_rag is not None:
            details += f" | RAG: {chat_rag.path.stem}"
        print(details)
        return
    location_text = " | ".join(item for item in location if item)
    header = (
        f"{config.get('name', 'James')} - v{__version__} | "
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
    heading_color = configured_color(config, "col_head") if config is not None else MARKDOWN_COLOR_DEFAULTS["col_head"]
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


def cowork_project_label(project_directory: Path) -> str:
    """Render a project directory relative to the shared repository root."""
    try:
        return project_directory.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix() or "."
    except ValueError:
        return str(project_directory)


def render_cowork_menu(
    config: dict[str, Any], selected_index: int, profiles: tuple[CoworkAgentProfile, ...]
) -> None:
    """Draw named Agent-session choices before the shared Cowork areas."""
    terminal = Terminal()
    width = int(config["width"])
    labels = tuple(profile.label for profile in profiles) + ("Manage plans", "Activity")
    clear_screen()
    render_page_header(config, "cowork")
    render_section_header(width, "COWORK", config)
    print()
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def render_cowork_code_menu(config: dict[str, Any], session: CoworkSession, selected_index: int) -> None:
    """Draw available Cowork Agent actions and the current session settings."""
    terminal = Terminal()
    width = int(config["width"])
    labels = ("start agent session", "one-shot task", "select model", "project", "tool policy", "recent runs", "setup-info")
    clear_screen()
    render_page_header(config, "cowork", session.agent_id)
    render_section_header(width, f"COWORK · AGENT · {session.agent_label.upper()}", config)
    print(f"{terminal.color('bright_black', 'agent:')} {terminal.color('cyan', session.agent_id)} — {session.agent_label}")
    print(f"{terminal.color('bright_black', 'project:')} {terminal.color('cyan', cowork_project_label(session.project_directory))}")
    print(f"{terminal.color('bright_black', 'model:')} {terminal.color('cyan', session.model)}")
    confirmation = "on" if session.run_confirm else "off (test mode)"
    schema_profile = cowork_schema_profile(session)
    print(f"{terminal.color('bright_black', 'policy:')} {terminal.color('cyan', session.policy.value)} | run confirmation: {confirmation} | schema: {schema_profile}")
    print("-" * width)
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def installed_ollama_models() -> list[str]:
    """Return names from ``ollama list`` without assuming a specific model family."""
    try:
        result = subprocess.run(
            ["ollama", "list"], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except OSError as error:
        raise ValueError(f"Could not run 'ollama list': {error}") from error
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"'ollama list' exited with code {result.returncode}.")
    lines = [line.split() for line in result.stdout.splitlines() if line.strip()]
    return [columns[0] for columns in lines[1:] if columns]


def select_cowork_model(config: dict[str, Any], session: CoworkSession) -> None:
    """Show local models and store one model choice for this Cowork session only."""
    clear_screen()
    render_page_header(config, "cowork", session.agent_id, "model")
    width = int(config["width"])
    render_section_header(width, "COWORK · AGENT · MODEL", config)
    print(f"Current: {Terminal().color('cyan', session.model)}\n")
    try:
        models = installed_ollama_models()
    except ValueError as error:
        Terminal().r(str(error))
        wait_for_back(width)
        return
    if models:
        print("Installed models:")
        for model in models:
            print(f"{MENU_INDENT}{model}")
    else:
        Terminal().y("Ollama reported no installed models.")
    value = input("Model name (empty = cancel): ").strip()
    if value:
        session.model = value
        Terminal().g(f"Cowork model selected: {session.model}")
    wait_for_back(width)


def select_cowork_project(config: dict[str, Any], session: CoworkSession) -> None:
    """Change only the Cowork session's project directory."""
    clear_screen()
    render_page_header(config, "cowork", session.agent_id, "project")
    width = int(config["width"])
    render_section_header(width, "COWORK · AGENT · PROJECT", config)
    print(f"Current: {Terminal().color('cyan', cowork_project_label(session.project_directory))}")
    print("Enter a project-relative directory; empty input keeps the current session project.")
    value = input("Project directory: ").strip()
    if value:
        try:
            session.project_directory = (PROJECT_ROOT / validate_directory_name(value)).resolve()
            session.project_directory.mkdir(parents=True, exist_ok=True)
            Terminal().g(f"Cowork project selected: {cowork_project_label(session.project_directory)}")
        except ValueError as error:
            Terminal().r(f"Project not changed: {error}")
    wait_for_back(width)


def render_cowork_policy_picker(config: dict[str, Any], selected_index: int) -> None:
    """Explain and select a tool policy before starting a coding run."""
    terminal = Terminal()
    width = int(config["width"])
    choices = (
        (ToolPolicy.OBSERVE, "read files only"),
        (ToolPolicy.DRAFT, "confirm every write and command"),
        (ToolPolicy.CODE, "write in project; commands follow run_confirm"),
    )
    clear_screen()
    render_page_header(config, "cowork", "agent", "policy")
    render_section_header(width, "COWORK · AGENT · TOOL POLICY", config)
    print()
    for index, (policy, description) in enumerate(choices):
        marker = "> " if index == selected_index else "  "
        name = terminal.style(policy.value, fg="yellow", bold=True) if index == selected_index else policy.value
        print(f"{MENU_INDENT}{marker}{name} — {description}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def select_cowork_policy(config: dict[str, Any], session: CoworkSession) -> None:
    """Store the selected policy only in the active Cowork session."""
    policies = tuple(ToolPolicy)
    selected_index = policies.index(session.policy)
    while True:
        render_cowork_policy_picker(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(policies) - 1, selected_index + 1)
        elif key in {"\r", "\n"}:
            session.policy = policies[selected_index]
            Terminal().g(f"Cowork policy selected: {session.policy.value}")
            pause()
            return


def create_cowork_callbacks() -> AgentCallbacks:
    """Render streamed engine events in James with the same cues as ``cli_agent``."""
    terminal = Terminal()
    in_thinking = False
    in_content = False

    def on_status(text: str) -> None:
        print(f"{terminal.color('bright_black', '[agent]')} {text}", flush=True)

    def on_thinking(text: str) -> None:
        nonlocal in_thinking
        if not in_thinking:
            terminal.v("\n[thinking]")
            in_thinking = True
        print(terminal.color("v", text), end="", flush=True)

    def on_content(text: str) -> None:
        nonlocal in_content
        if not in_content:
            terminal.w("\n\n[answer]")
            in_content = True
        print(terminal.color("w", text), end="", flush=True)

    def on_tool_call(name: str, arguments: dict[str, object]) -> None:
        print(f"{terminal.color('y', '[tool]')} {name}({arguments})", flush=True)

    def on_tool_result(_name: str, result: str) -> None:
        print(f"{terminal.color('g', '[result]')} {result}", flush=True)

    return AgentCallbacks(on_status, on_thinking, on_content, on_tool_call, on_tool_result)


def run_cowork_prompt(
    config: dict[str, Any],
    session: CoworkSession,
    messages: list[dict[str, object]],
    prompt: str,
    *,
    policy_override: ToolPolicy | None = None,
    allowed_tool_names: frozenset[str] | None = None,
    task: str = "cowork_code",
) -> AgentRun:
    """Run one model turn with the shared engine and store a completed report."""
    project_data = load_project_config(config)
    debug_enabled = project_data.get("debug")
    if debug_enabled is not None and not isinstance(debug_enabled, bool):
        raise ValueError("'debug' must be true or false in project.json.")
    scope = ProjectToolScope(session.project_directory)
    effective_policy = policy_override or session.policy
    run = AgentRun(session.model, scope.root, effective_policy, prompt)
    schema_profile = cowork_schema_profile(session)
    session_info_provider = lambda: format_session_info(
        run,
        schema_profile=schema_profile,
        options=agent_options,
        max_steps=DEFAULT_MAX_STEPS,
        run_confirm=session.run_confirm,
        auto_continue=session.auto_continue,
        review_enabled=session.review_enabled,
    )
    available_tools = build_file_tools(
        scope,
        effective_policy,
        run_confirm=None if session.run_confirm else lambda _message: True,
        on_artifact=run.artifacts.add,
        session_info_provider=session_info_provider,
    )
    tool_schema = load_tool_schema(AGENT_TOOL_SCHEMA_PATH, schema_profile)
    if allowed_tool_names is not None:
        tool_schema = [
            tool
            for tool in tool_schema
            if isinstance(tool.get("function"), dict) and tool["function"].get("name") in allowed_tool_names
        ]
    tools = tools_for_schema(tool_schema, available_tools)
    api = ollama_api(config_path=OLLAMA_CONFIG_PATH, debug_enabled=debug_enabled, time_trace=True)
    agent_options = resolve_agent_options(api.default_options, session.agent_options or {})
    engine = AgentEngine(
        api=api,
        model=session.model,
        tool_schema=tool_schema,
        tools=tools,
        max_steps=DEFAULT_MAX_STEPS,
        timeout_seconds=api.read_timeout_seconds,
        options=agent_options,
        auto_continue=session.auto_continue,
        verbose=True,
        callbacks=create_cowork_callbacks(),
    )
    if session_info_requested(prompt):
        messages.append({"role": "system", "content": session_info_context(session_info_provider())})
    messages.append({"role": "user", "content": prompt})
    engine.run(messages, run)
    if session.review_enabled:
        try:
            run.review = review_agent_run(
                run,
                api=api,
                model=session.model,
                scope=scope,
                timeout_seconds=api.read_timeout_seconds,
                options=agent_options,
            )
        except RuntimeError as error:
            run.review_error = str(error)
    if session.db_enabled:
        try:
            uid = record_agent_run(
                run,
                database_path=main_database_file(config),
                schema_path=PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
                project_root=PROJECT_ROOT,
                selector=session.db_selector,
                instruction=AGENT_SYSTEM_PROMPT,
                run_confirm=session.run_confirm,
                task=task,
            )
        except (OSError, ValueError, TaskDatabaseError) as error:
            raise RuntimeError(f"Completed Cowork run could not be recorded: {error}") from error
        Terminal().g(f"Cowork run recorded in data/tasks.db: {uid}")
    return run


def print_cowork_run(run: AgentRun) -> None:
    """Display the model's verified final answer and the independent run report."""
    terminal = Terminal()
    if run.final_answer is not None:
        print(f"\n{terminal.color('c', 'Agent:')} {terminal.color('w', run.final_answer)}")
    if run.review is not None:
        print(f"\n{terminal.color('c', 'Review:')} {terminal.color('w', run.review)}")
    print(f"\n{terminal.color('c', run.summary())}")


def run_cowork_one_shot(config: dict[str, Any], session: CoworkSession) -> None:
    """Ask for one objective, execute it, then return to the Agent menu."""
    clear_screen()
    render_page_header(config, "cowork", session.agent_id, "one-shot")
    width = int(config["width"])
    render_section_header(width, "COWORK · AGENT · ONE-SHOT", config)
    prompt = input("Task (empty = cancel): ").strip()
    if not prompt:
        return
    try:
        run = run_cowork_prompt(config, session, [{"role": "system", "content": cowork_system_prompt(session)}], prompt)
        print_cowork_run(run)
    except RuntimeError as error:
        Terminal().r(f"Agent error: {error}")
    pause()


def run_cowork_coding_session(config: dict[str, Any], session: CoworkSession) -> None:
    """Keep an independent agent conversation open until the user enters exit or quit."""
    clear_screen()
    render_page_header(config, "cowork", session.agent_id, "session")
    Terminal().c(f"Agent session ({session.agent_label}): {cowork_project_label(session.project_directory)} | {session.model} | {session.policy.value}")
    Terminal().y("Type 'exit' or 'quit' to return to Cowork Agent.")
    messages: list[dict[str, object]] = [{"role": "system", "content": cowork_system_prompt(session)}]
    while True:
        try:
            prompt = input(f"\n{Terminal().color('c', 'You: ')}")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if prompt.strip().casefold() in {"exit", "quit"}:
            return
        if not prompt.strip():
            continue
        try:
            run = run_cowork_prompt(config, session, messages, prompt)
            print_cowork_run(run)
        except RuntimeError as error:
            Terminal().r(f"Agent error: {error}")
            return


def show_cowork_recent_runs(config: dict[str, Any], session: CoworkSession) -> None:
    """Display the newest Cowork Agent records for the session-local project."""
    clear_screen()
    render_page_header(config, "cowork", session.agent_id, "recent runs")
    width = int(config["width"])
    render_section_header(width, "COWORK · AGENT · RECENT RUNS", config)
    try:
        rows = list_task_rows(
            main_database_file(config),
            project=cowork_project_label(session.project_directory),
            selector=session.db_selector,
            task="cowork_code",
        )
    except TaskDatabaseError as error:
        Terminal().y(f"No Cowork run history: {error}")
        wait_for_back(width)
        return
    if not rows:
        Terminal().y("No completed Cowork Agent runs for this project yet.")
    else:
        for row in rows[: int(config["max_list_rows"])]:
            print(f"#{row['uid']}  {row['datetime']}  {short_text(row['model'], 18)}")
            print(f"  {short_text(row['prompt'], 56)}")
            print(f"  {short_text(row['answer'], 56)}")
    wait_for_back(width)


def show_cowork_setup_info(config: dict[str, Any], session: CoworkSession) -> None:
    """Show parsed Agent JSON settings without changing session-local choices."""
    clear_screen()
    render_page_header(config, "cowork", session.agent_id, "setup-info")
    width = int(config["width"])
    render_section_header(width, "COWORK · AGENT · SETUP-INFO", config)
    try:
        settings = load_cowork_agent_config()
        profiles = load_cowork_agents_config()
        task_names = available_chat_tasks()
    except ValueError as error:
        Terminal().r(f"Setup error: {error}")
        wait_for_back(width)
        return

    schema_profile = str(settings.get("tool_schema_profile") or ("light" if bool(settings["tool_schema_light"]) else "extended"))
    terminal = Terminal()
    print(f"{terminal.color('cyan', 'shared runtime defaults')}: {AGENT_CONFIG_PATH}")
    render_json_key_values(settings, config, 2)
    print()
    print(terminal.color("cyan", "active session (runtime only)"))
    render_json_key_values(
        {
            "agent_id": session.agent_id,
            "agent_label": session.agent_label,
            "model": session.model,
            "tool_schema_profile": cowork_schema_profile(session),
            "default_tool_schema_profile": schema_profile,
            "run_confirm": session.run_confirm,
            "auto_continue": session.auto_continue,
            "review": session.review_enabled,
            "tool_schema_path": str(AGENT_TOOL_SCHEMA_PATH),
        },
        config,
        2,
    )
    print()
    print(f"{terminal.color('cyan', 'Cowork agent catalog')}: {COWORK_AGENTS_CONFIG_PATH}")
    render_json_key_values(
        {
            profile.agent_id: {
                "label": profile.label,
                "description": profile.description,
                "model": profile.model,
                "options": profile.agent_options,
                "tools": profile.tool_schema_profile,
            }
            for profile in profiles.values()
        },
        config,
        2,
    )
    print()
    print(f"{terminal.color('cyan', 'Chat task definitions')}: {ASSISTANT_TASKS_PATH}")
    render_json_key_values({"task_path": str(ASSISTANT_TASKS_PATH), "json_files": len(task_names)}, config, 2)
    print("  Their model fields apply to James Chat tasks; Cowork uses the selected Agent profile above,")
    print("  unless 'select model' changes it for the current Cowork session.")
    wait_for_back(width)


def cowork_code_menu(config: dict[str, Any], session: CoworkSession) -> None:
    """Run Cowork Agent actions without affecting global James or project settings."""
    selected_index = 0
    while True:
        render_cowork_code_menu(config, session, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(6, selected_index + 1)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            run_cowork_coding_session(config, session)
        elif selected_index == 1:
            run_cowork_one_shot(config, session)
        elif selected_index == 2:
            select_cowork_model(config, session)
        elif selected_index == 3:
            select_cowork_project(config, session)
        elif selected_index == 4:
            select_cowork_policy(config, session)
        elif selected_index == 5:
            show_cowork_recent_runs(config, session)
        else:
            show_cowork_setup_info(config, session)


def cowork_plans_path(project_directory: Path) -> Path:
    """Return the project-local persistent storage path for Cowork plans."""
    return project_directory.resolve() / COWORK_DIRECTORY_NAME / COWORK_PLANS_FILENAME


def load_cowork_plans(project_directory: Path) -> list[dict[str, object]]:
    """Load the small user-authored plan collection, or return an empty collection."""
    path = cowork_plans_path(project_directory)
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read Cowork plans: {error}") from error
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("plans"), list):
        raise ValueError(f"{path} must contain a version 1 Cowork plans document.")
    plans: list[dict[str, object]] = []
    for index, plan in enumerate(document["plans"], start=1):
        if not isinstance(plan, dict):
            raise ValueError(f"Plan {index} must be an object.")
        for name in ("id", "title", "goal", "status", "created_at", "updated_at"):
            if not isinstance(plan.get(name), str) or not plan[name].strip():
                raise ValueError(f"Plan {index} requires non-empty '{name}'.")
        steps = plan.get("steps")
        if not isinstance(steps, list) or not all(
            isinstance(step, dict)
            and isinstance(step.get("title"), str)
            and step["title"].strip()
            and isinstance(step.get("status"), str)
            and step["status"].strip()
            for step in steps
        ):
            raise ValueError(f"Plan {index} requires a list of named steps with status.")
        for step_index, step in enumerate(steps, start=1):
            last_run = step.get("last_run")
            if last_run is not None and (
                not isinstance(last_run, dict)
                or not isinstance(last_run.get("status"), str)
                or not last_run["status"].strip()
                or not isinstance(last_run.get("finished_at"), str)
                or not last_run["finished_at"].strip()
                or not isinstance(last_run.get("summary"), str)
                or ("mode" in last_run and last_run["mode"] not in {"implement", "prepare"})
            ):
                raise ValueError(f"Plan {index}, step {step_index} has an invalid 'last_run' record.")
        plans.append(plan)
    return plans


def save_cowork_plans(project_directory: Path, plans: list[dict[str, object]]) -> Path:
    """Persist all plans as one transparent project-local JSON document."""
    path = cowork_plans_path(project_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "plans": plans}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def new_cowork_plan_id(plans: list[dict[str, object]]) -> str:
    """Create a stable, collision-free local plan identifier."""
    prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
    existing = {str(plan.get("id")) for plan in plans}
    suffix = 1
    candidate = prefix
    while candidate in existing:
        suffix += 1
        candidate = f"{prefix}_{suffix}"
    return candidate


def refresh_cowork_plan_status(plan: dict[str, object]) -> None:
    """Derive the aggregate plan state from the user-managed states of its steps."""
    steps = plan["steps"]
    assert isinstance(steps, list)  # Validated when a plan is loaded or created.
    statuses = {str(step["status"]) for step in steps if isinstance(step, dict)}
    if statuses and statuses <= {"done", "skipped"}:
        plan["status"] = "done"
    elif "in_progress" in statuses:
        plan["status"] = "in_progress"
    elif "blocked" in statuses:
        plan["status"] = "blocked"
    else:
        plan["status"] = "draft"


def update_cowork_plan_step(
    project_directory: Path,
    plan_id: str,
    step_index: int,
    *,
    status: str | None = None,
    last_run: dict[str, str] | None = None,
) -> dict[str, object]:
    """Persist an explicit step-state decision and/or the last Code run evidence."""
    plans = load_cowork_plans(project_directory)
    plan = next((item for item in plans if item["id"] == plan_id), None)
    if plan is None:
        raise ValueError("The selected plan no longer exists.")
    steps = plan["steps"]
    assert isinstance(steps, list)  # Validated by load_cowork_plans().
    if not 0 <= step_index < len(steps):
        raise ValueError("The selected plan step no longer exists.")
    step = steps[step_index]
    assert isinstance(step, dict)  # Validated by load_cowork_plans().
    if status is not None:
        if status not in COWORK_PLAN_STEP_STATUSES:
            raise ValueError(f"Unknown plan step status: {status}")
        step["status"] = status
    if last_run is not None:
        step["last_run"] = last_run
    refresh_cowork_plan_status(plan)
    plan["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    save_cowork_plans(project_directory, plans)
    return plan


def cowork_plan_status_label(terminal: Terminal, status: object) -> str:
    """Color one persisted planning state consistently wherever Plans renders it."""
    text = str(status)
    colors = {
        "done": "green",
        "completed": "green",
        "in_progress": "yellow",
        "blocked": "red",
        "failed": "red",
        "error": "red",
        "todo": "bright_black",
        "skipped": "bright_black",
        "draft": "bright_black",
    }
    return terminal.color(colors.get(text, "white"), text)


def create_cowork_plan(config: dict[str, Any], session: CoworkSession) -> None:
    """Collect a minimal user-controlled plan without starting a coding agent."""
    clear_screen()
    render_page_header(config, "cowork", "plans", "new")
    width = int(config["width"])
    render_section_header(width, "COWORK · PLANS · NEW", config)
    print("A plan is preparation only; it does not run Code or modify project files.")
    title = input("Title (empty = cancel): ").strip()
    if not title:
        return
    goal = input("Goal: ").strip()
    if not goal:
        Terminal().y("Plan was not created: a goal is required.")
        pause()
        return
    print("Steps (enter an empty line when finished):")
    steps: list[dict[str, str]] = []
    while True:
        step_title = input(f"  Step {len(steps) + 1}: ").strip()
        if not step_title:
            break
        steps.append({"title": step_title, "status": "todo"})
    if not steps:
        Terminal().y("Plan was not created: add at least one step.")
        pause()
        return
    try:
        plans = load_cowork_plans(session.project_directory)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        plan: dict[str, object] = {
            "id": new_cowork_plan_id(plans),
            "title": title,
            "goal": goal,
            "status": "draft",
            "created_at": timestamp,
            "updated_at": timestamp,
            "steps": steps,
        }
        path = save_cowork_plans(session.project_directory, [*plans, plan])
    except ValueError as error:
        Terminal().r(f"Plan was not saved: {error}")
        pause()
        return
    Terminal().g(f"Plan saved: {path}")
    pause()


def show_cowork_plans(config: dict[str, Any], session: CoworkSession) -> None:
    """Render all project-local plans and their explicit user-managed states."""
    clear_screen()
    render_page_header(config, "cowork", "plans")
    width = int(config["width"])
    render_section_header(width, "COWORK · PLANS", config)
    try:
        plans = load_cowork_plans(session.project_directory)
    except ValueError as error:
        Terminal().r(f"Plans unavailable: {error}")
        wait_for_back(width)
        return
    if not plans:
        Terminal().y("No plans for this project yet. Create one from the Plans menu.")
    else:
        terminal = Terminal()
        for plan in plans:
            steps = plan["steps"]
            completed = sum(1 for step in steps if step["status"] == "done")
            plan_status = cowork_plan_status_label(terminal, plan["status"])
            print(f"{terminal.color('cyan', str(plan['title']))}  [{plan_status}]  {completed}/{len(steps)} steps")
            print(f"  Goal: {plan['goal']}")
            for index, step in enumerate(steps, start=1):
                status = cowork_plan_status_label(terminal, step["status"])
                print(f"  {index}. [{status}] {step['title']}")
                last_run = step.get("last_run")
                if isinstance(last_run, dict):
                    run_status = cowork_plan_status_label(terminal, last_run["status"])
                    mode = last_run.get("mode")
                    mode_text = f" ({mode})" if isinstance(mode, str) else ""
                    print(f"     Last Agent run{mode_text}: {run_status} · {last_run['finished_at']}")
                    if last_run["summary"]:
                        print(f"     {short_text(last_run['summary'], 100)}")
            print()
    print(f"Storage: {cowork_plans_path(session.project_directory)}")
    wait_for_back(width)


def cowork_plan_step_prompt(plan: dict[str, object], step_index: int, *, mode: str = "implement") -> str:
    """Build the bounded, self-contained task handed from a saved plan to Code."""
    if mode not in {"implement", "prepare"}:
        raise ValueError(f"Unknown plan execution mode: {mode}")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 0 <= step_index < len(steps):
        raise ValueError("The selected plan step does not exist.")
    selected_step = steps[step_index]
    if not isinstance(selected_step, dict):
        raise ValueError("The selected plan step is invalid.")
    selected_title = selected_step.get("title")
    if not isinstance(selected_title, str) or not selected_title.strip():
        raise ValueError("The selected plan step needs a title.")
    completed = [
        str(step["title"])
        for step in steps
        if isinstance(step, dict) and step.get("status") == "done" and isinstance(step.get("title"), str)
    ]
    skipped = [
        str(step["title"])
        for step in steps
        if isinstance(step, dict) and step.get("status") == "skipped" and isinstance(step.get("title"), str)
    ]
    remaining = [
        str(step["title"])
        for index, step in enumerate(steps)
        if index != step_index
        and isinstance(step, dict)
        and step.get("status") not in {"done", "skipped"}
        and isinstance(step.get("title"), str)
    ]
    completed_text = "\n".join(f"- {title}" for title in completed) or "- (none)"
    skipped_text = "\n".join(f"- {title}" for title in skipped) or "- (none)"
    remaining_text = "\n".join(f"- {title}" for title in remaining) or "- (none)"
    mode_instruction = (
        "Implement the selected step now."
        if mode == "implement"
        else (
            "Prepare the selected step only: inspect and analyze the project, then return a concrete proposal. "
            "Do not create, modify, delete, run, compile, or serve anything; this run has read-only tools only."
        )
    )
    return (
        "Handle one explicitly user-approved Cowork plan step.\n\n"
        f"Plan title: {plan['title']}\n"
        f"Plan goal: {plan['goal']}\n"
        f"Selected step ({step_index + 1}/{len(steps)}): {selected_title}\n\n"
        "Steps already marked done (context only):\n"
        f"{completed_text}\n\n"
        "Skipped steps (do not implement these):\n"
        f"{skipped_text}\n\n"
        "Other incomplete steps (do not implement these now):\n"
        f"{remaining_text}\n\n"
        f"{mode_instruction} Work on the selected step and only its necessary supporting changes. "
        "Do not start a later plan step. The plan file is user-managed: "
        "do not modify .cowork/plans.json and do not claim that a plan step is done merely because this run "
        "ended. In your final answer, report concrete files changed, verification performed, and any remaining "
        "blocker for the user to decide the plan status."
    )


def choose_cowork_plan_step(
    config: dict[str, Any], session: CoworkSession, *, action: str = "send to agent"
) -> tuple[dict[str, object], int] | None:
    """Let the user explicitly choose one persisted plan step for an Agent run."""
    clear_screen()
    render_page_header(config, "cowork", "plans", action)
    width = int(config["width"])
    render_section_header(width, f"COWORK · PLANS · {action.upper()}", config)
    try:
        plans = load_cowork_plans(session.project_directory)
    except ValueError as error:
        Terminal().r(f"Plans unavailable: {error}")
        pause()
        return None
    if not plans:
        Terminal().y("No plans for this project yet.")
        pause()
        return None
    for index, plan in enumerate(plans, start=1):
        terminal = Terminal()
        print(f"{index}. {terminal.color('cyan', str(plan['title']))}  [{cowork_plan_status_label(terminal, plan['status'])}]")
        print(f"   {plan['goal']}")
    raw_plan_index = input("Plan number (empty = cancel): ").strip()
    if not raw_plan_index:
        return None
    try:
        plan_index = int(raw_plan_index) - 1
    except ValueError:
        Terminal().y("Enter a plan number.")
        pause()
        return None
    if not 0 <= plan_index < len(plans):
        Terminal().y("That plan does not exist.")
        pause()
        return None
    plan = plans[plan_index]
    steps = plan["steps"]
    assert isinstance(steps, list)  # Validated by load_cowork_plans().
    print()
    for index, step in enumerate(steps, start=1):
        terminal = Terminal()
        print(f"{index}. [{cowork_plan_status_label(terminal, step['status'])}] {step['title']}")
    raw_step_index = input("Step number to send (empty = cancel): ").strip()
    if not raw_step_index:
        return None
    try:
        step_index = int(raw_step_index) - 1
    except ValueError:
        Terminal().y("Enter a step number.")
        pause()
        return None
    if not 0 <= step_index < len(steps):
        Terminal().y("That step does not exist.")
        pause()
        return None
    return plan, step_index


def send_cowork_plan_step_to_code(config: dict[str, Any], session: CoworkSession) -> None:
    """Run the plan's coding Agent once and persist its outcome for review."""
    selected = choose_cowork_plan_step(config, session)
    if selected is None:
        return
    plan, step_index = selected
    mode_choice = input("Mode: [i]mplement now, [p]repare proposal only (empty = cancel): ").strip().casefold()
    modes = {"i": "implement", "p": "prepare"}
    if mode_choice not in modes:
        return
    mode = modes[mode_choice]
    try:
        if mode == "implement":
            plan = update_cowork_plan_step(
                session.project_directory,
                str(plan["id"]),
                step_index,
                status="in_progress",
            )
        prompt = cowork_plan_step_prompt(plan, step_index, mode=mode)
    except ValueError as error:
        Terminal().r(f"Plan cannot be sent: {error}")
        pause()
        return
    Terminal().c(f"Sending to Agent: {plan['title']} · step {step_index + 1}")
    if mode == "implement":
        Terminal().y("The step is now in progress. You will confirm its final plan status after the run.")
    else:
        Terminal().y("Prepare mode is read-only: it may inspect, but cannot write or run project programs.")
    try:
        run = run_cowork_prompt(
            config,
            session,
            [{"role": "system", "content": AGENT_SYSTEM_PROMPT}],
            prompt,
            policy_override=ToolPolicy.OBSERVE if mode == "prepare" else None,
            allowed_tool_names=PLAN_PREPARE_TOOL_NAMES if mode == "prepare" else None,
            task="cowork_plan_prepare" if mode == "prepare" else "cowork_code",
        )
        print_cowork_run(run)
    except RuntimeError as error:
        Terminal().r(f"Agent error: {error}")
        pause()
        return
    last_run = {
        "mode": mode,
        "status": str(run.status),
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": short_text(run.final_answer or "No final answer.", 240),
    }
    try:
        update_cowork_plan_step(
            session.project_directory,
            str(plan["id"]),
            step_index,
            last_run=last_run,
        )
    except ValueError as error:
        Terminal().r(f"Code outcome was not saved into the plan: {error}")
        pause()
        return
    terminal = Terminal()
    terminal.c("Plan step result recorded. Choose its user-managed status:")
    choice = input("[d]one  [b]locked  [t]odo  [Enter] keep in progress: ").strip().casefold()
    statuses = {"d": "done", "b": "blocked", "t": "todo"}
    if choice in statuses:
        try:
            plan = update_cowork_plan_step(
                session.project_directory,
                str(plan["id"]),
                step_index,
                status=statuses[choice],
            )
        except ValueError as error:
            terminal.r(f"Plan status was not updated: {error}")
        else:
            terminal.g(f"Step marked {statuses[choice]}; plan status: {plan['status']}.")
    elif choice:
        terminal.y("Status unchanged: the step remains in progress.")
    else:
        terminal.y("Status unchanged: the step remains in progress.")
    pause()


def update_cowork_plan_step_status(config: dict[str, Any], session: CoworkSession) -> None:
    """Let the user correct, defer, finish, block, or skip a step without a Code run."""
    selected = choose_cowork_plan_step(config, session, action="update step")
    if selected is None:
        return
    plan, step_index = selected
    terminal = Terminal()
    terminal.c("Choose a user-managed status for this step:")
    choice = input("[t]odo  [i]n progress  [d]one  [b]locked  [s]kipped (empty = cancel): ").strip().casefold()
    statuses = {"t": "todo", "i": "in_progress", "d": "done", "b": "blocked", "s": "skipped"}
    if choice not in statuses:
        return
    try:
        updated_plan = update_cowork_plan_step(
            session.project_directory,
            str(plan["id"]),
            step_index,
            status=statuses[choice],
        )
    except ValueError as error:
        terminal.r(f"Plan status was not updated: {error}")
    else:
        terminal.g(f"Step marked {statuses[choice]}; plan status: {updated_plan['status']}.")
    pause()


def render_cowork_plans_menu(config: dict[str, Any], session: CoworkSession, selected_index: int) -> None:
    """Draw the Plans workspace and its explicit Code handoff action."""
    terminal = Terminal()
    width = int(config["width"])
    labels = ("new plan", "show plans", "send step to Code", "update step status")
    clear_screen()
    render_page_header(config, "cowork", "plans")
    render_section_header(width, "COWORK · PLANS", config)
    print(f"{terminal.color('bright_black', 'project:')} {terminal.color('cyan', cowork_project_label(session.project_directory))}")
    print("Plans are user-controlled. Sending a selected step starts one bounded Code run.")
    print("-" * width)
    for index, label in enumerate(labels):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def cowork_plans_menu(config: dict[str, Any], session: CoworkSession) -> None:
    """Open planning and let the user explicitly hand one step to Code."""
    selected_index = 0
    while True:
        render_cowork_plans_menu(config, session, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(3, selected_index + 1)
        elif key in {"\r", "\n"}:
            if selected_index == 0:
                create_cowork_plan(config, session)
            elif selected_index == 1:
                show_cowork_plans(config, session)
            elif selected_index == 2:
                send_cowork_plan_step_to_code(config, session)
            else:
                update_cowork_plan_step_status(config, session)


def cowork_menu(config: dict[str, Any]) -> None:
    """Enter Cowork and keep one independent session for every named agent."""
    profiles = load_cowork_agents_config()
    profile_list = tuple(profiles.values())
    project_directory = active_project_directory(config)
    sessions = {
        profile.agent_id: cowork_session_from_profile(project_directory, profile)
        for profile in profile_list
    }
    plan_session = sessions.get("code") or sessions[profile_list[0].agent_id]
    selected_index = 0
    while True:
        render_cowork_menu(config, selected_index, profile_list)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = max(0, selected_index - 1)
        elif key == "down":
            selected_index = min(len(profile_list) + 1, selected_index + 1)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index < len(profile_list):
            cowork_code_menu(config, sessions[profile_list[selected_index].agent_id])
        elif selected_index == len(profile_list):
            cowork_plans_menu(config, plan_session)
        else:
            show_todo(config, "COWORK · ACTIVITY", "TODO · Activity will aggregate Cowork reports later.")


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
    Terminal().c(f"Try the same workflow in Chat: /rag {profile.name}, then /chunk {query}.")
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

    if path.suffix.casefold() == ".json":
        show_json_document(config, path, title)
        return
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
        for rendered_line in render_markdown_lines(content.splitlines(), config):
            print(rendered_line)
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
    Terminal().c(f"Markdown colors: {WRAPP_MD_CONFIG_PATH.relative_to(PROJECT_ROOT).as_posix()}")
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


MCP_MODULE_LABELS = ("MCP base", "MCP hardware", "MCP Nostr")
MCP_BASE_MENU_LABELS = ("run MCP server", "list MCP services", "show MCP setup")
MCP_HARDWARE_MENU_LABELS = (
    "list MCP hardware tools",
    "show MCP hardware setup",
    "show BLE requirements",
)


def missing_module_files(paths: tuple[Path, ...]) -> list[Path]:
    """Return optional-module files that are absent without importing them."""

    return [path for path in paths if not path.is_file()]


def display_project_path(path: Path) -> str:
    """Render a project-relative path, including when tests use a temp path."""

    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def show_missing_mcp_module(config: dict[str, Any], title: str, missing_paths: list[Path]) -> None:
    """Explain an optional MCP module's missing local prerequisites."""

    clear_screen()
    render_page_header(config, "mcp", title.lower())
    Terminal().y(f"{title} is not ready on this installation.")
    print()
    print("Install or add these files:")
    for path in missing_paths:
        print(f"  - {display_project_path(path)}")
    print()
    print("James remains available without this optional module.")
    pause()


def render_mcp_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the top-level catalog of local MCP modules."""

    terminal = Terminal()
    width = int(config["width"])
    clear_screen()
    render_page_header(config, "mcp")
    render_section_header(width, "MCP MODULES", config)
    print()
    for index, label in enumerate(MCP_MODULE_LABELS):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        suffix = " · preparing" if index == 2 else ""
        print(f"{MENU_INDENT}{marker}{text}{suffix}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def render_mcp_base_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the established local Streamable HTTP MCP actions."""

    terminal = Terminal()
    width = int(config["width"])
    clear_screen()
    render_page_header(config, "mcp", "base")
    render_section_header(width, "MCP BASE", config)
    print()
    for index, label in enumerate(MCP_BASE_MENU_LABELS):
        marker = "> " if index == selected_index else "  "
        text = terminal.style(label, fg="yellow", bold=True) if index == selected_index else label
        print(f"{MENU_INDENT}{marker}{text}")
    print()
    print(f"{MENU_INDENT}↑/↓ move   Enter select")
    render_back_footer(width)


def render_mcp_hardware_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the setup and discovery actions for the optional BLE MCP module."""

    terminal = Terminal()
    width = int(config["width"])
    clear_screen()
    render_page_header(config, "mcp", "hardware")
    render_section_header(width, "MCP HARDWARE", config)
    print()
    for index, label in enumerate(MCP_HARDWARE_MENU_LABELS):
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


def hardware_mcp_required_files() -> tuple[Path, ...]:
    """Return only the project files required to start the optional HW module."""

    return (
        MCP_SCRIPT_PATH,
        MCP_HW_SERVER_CONFIG_PATH,
        MCP_HW_SERVER_PATH,
        BLE_SCRIPT_PATH,
        BLE_REQUIREMENTS_PATH,
    )


def list_mcp_hardware_services(config: dict[str, Any]) -> None:
    """List the allowlisted tools from the optional stdio hardware MCP server."""

    missing_paths = missing_module_files(hardware_mcp_required_files())
    if missing_paths:
        show_missing_mcp_module(config, "MCP hardware", missing_paths)
        return

    clear_screen()
    render_page_header(config, "mcp", "hardware tools")
    Terminal().c("Listing MCP hardware tools…")
    command = [
        sys.executable,
        str(MCP_SCRIPT_PATH),
        "--server-config",
        str(MCP_HW_SERVER_CONFIG_PATH),
        "--list",
        "--no-db",
        "--timeout",
        "30",
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    print()
    if result.returncode:
        Terminal().r(f"MCP hardware tool listing failed (exit code {result.returncode}).")
    else:
        Terminal().g("MCP hardware tools listed.")
    pause()


def show_mcp_hardware_setup(config: dict[str, Any]) -> None:
    """Open the stdio server configuration when the optional module is present."""

    if not MCP_HW_SERVER_CONFIG_PATH.is_file():
        show_missing_mcp_module(config, "MCP hardware", [MCP_HW_SERVER_CONFIG_PATH])
        return
    show_text_document(config, MCP_HW_SERVER_CONFIG_PATH, "MCP HARDWARE · SETUP")


def show_ble_requirements(config: dict[str, Any]) -> None:
    """Open the optional BLE dependency list without attempting installation."""

    if not BLE_REQUIREMENTS_PATH.is_file():
        show_missing_mcp_module(config, "MCP hardware", [BLE_REQUIREMENTS_PATH])
        return
    show_text_document(config, BLE_REQUIREMENTS_PATH, "MCP HARDWARE · BLE REQUIREMENTS")


def show_mcp_nostr_status(config: dict[str, Any]) -> None:
    """Show a calm placeholder for the intentionally not-yet-installed module."""

    missing_paths = missing_module_files((NOSTR_SCRIPT_PATH, NOSTR_REQUIREMENTS_PATH))
    clear_screen()
    render_page_header(config, "mcp", "nostr")
    Terminal().y("MCP Nostr · preparing")
    print()
    if missing_paths:
        print("This module is not installed yet. To add it, provide:")
        for path in missing_paths:
            print(f"  - {display_project_path(path)}")
    else:
        print("Module files are ready; its MCP server will be connected later.")
    print()
    print("Other MCP modules remain available.")
    pause()


def mcp_base_menu(config: dict[str, Any]) -> None:
    """Choose the established local Streamable HTTP MCP actions."""

    selected_index = 0
    while True:
        render_mcp_base_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = (selected_index - 1) % len(MCP_BASE_MENU_LABELS)
        elif key == "down":
            selected_index = (selected_index + 1) % len(MCP_BASE_MENU_LABELS)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            run_mcp_server(config)
        elif selected_index == 1:
            list_mcp_services(config)
        else:
            show_text_document(config, MCP_CONFIG_PATH, "MCP · SETUP")


def mcp_hardware_menu(config: dict[str, Any]) -> None:
    """Choose discovery and setup actions for the optional hardware MCP module."""

    selected_index = 0
    while True:
        render_mcp_hardware_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = (selected_index - 1) % len(MCP_HARDWARE_MENU_LABELS)
        elif key == "down":
            selected_index = (selected_index + 1) % len(MCP_HARDWARE_MENU_LABELS)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            list_mcp_hardware_services(config)
        elif selected_index == 1:
            show_mcp_hardware_setup(config)
        else:
            show_ble_requirements(config)


def mcp_menu(config: dict[str, Any]) -> None:
    """Choose one MCP module; optional modules never block the main menu."""

    selected_index = 0
    while True:
        render_mcp_menu(config, selected_index)
        key = read_key()
        if key in {"b", " "}:
            return
        if key == "up":
            selected_index = (selected_index - 1) % len(MCP_MODULE_LABELS)
        elif key == "down":
            selected_index = (selected_index + 1) % len(MCP_MODULE_LABELS)
        elif key not in {"\r", "\n"}:
            continue
        elif selected_index == 0:
            mcp_base_menu(config)
        elif selected_index == 1:
            mcp_hardware_menu(config)
        else:
            show_mcp_nostr_status(config)


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
    quiet: bool = False,
) -> int:
    """Run one configured text flow through runner.py and return its exit code.

    ``capture_output`` lets Chat render the saved reply itself after a successful
    request, while preserving the runner diagnostics when that request fails.
    ``quiet`` replaces runner details with one muted status message for a
    minimalist Chat conversation.
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
    if not quiet:
        Terminal().c(f"Starting runner.py {flow_name}{detail_label}…")
    else:
        Terminal().print("bright_black", "• Running…")
    run_options: dict[str, Any] = {"cwd": PROJECT_ROOT, "check": False}
    if capture_output:
        run_options.update({"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"})
    result = subprocess.run(command, **run_options)
    if capture_output and result.returncode:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if not quiet:
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

    configured_directory = config.get(CHAT_PROJECT_SUBDIR_OVERRIDE_KEY)
    if configured_directory is None:
        project_data = load_project_config(config)
        configured_directory = project_data.get("subdir")
    if not isinstance(configured_directory, str):
        raise ValueError("'subdir' must be non-empty text in project.json or the current Chat session.")
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


def read_chat_database_answer(config: dict[str, Any], task_id: int) -> str:
    """Return one database answer exactly as ``cli_db.py -E ID`` would print it."""

    try:
        row = get_task_row(main_database_file(config), task_id)
    except TaskDatabaseError as error:
        raise ValueError(str(error)) from error
    if row is None:
        raise ValueError(f"No task record found: {task_id}")
    answer = row["answer"]
    if not isinstance(answer, str):
        raise ValueError(f"Task record {task_id} has a non-text answer.")
    if not answer.strip():
        raise ValueError(f"Task record {task_id} has an empty answer and cannot be sent to chat.")
    return answer


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


def format_chat_rag_context(profile: DatabaseProfile, query: str, hits: list[Any]) -> tuple[str, int]:
    """Format retrieved hits as one bounded, replaceable Chat RAG source section."""

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
    return format_chat_rag_context(profile, query, hits)


def chat_rag_query_words(groups: list[str]) -> list[str]:
    """Return up to five unique meaningful words for a compact RAG map."""

    words: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for word in re.findall(r"[^\W_]+", group, re.UNICODE):
            normalized = word.casefold()
            if len(word) < 2 or normalized in {"and", "or"} or normalized in seen:
                continue
            seen.add(normalized)
            words.append(word)
            if len(words) == 5:
                return words
    return words


def semantic_group_distance(distances: dict[str, float], groups: list[str], operators: list[str]) -> float:
    """Combine group distances: AND requires every group; OR accepts the closest branch."""

    values = [distances[f"group: {group}"] for group in groups]
    if not values:
        return float("inf")
    # Honour ordinary Boolean precedence: combine AND chains first, then choose
    # the closest OR branch. Smaller L2 distance is better throughout.
    branches: list[float] = []
    current = values[0]
    for operator, value in zip(operators, values[1:]):
        if operator == "AND":
            current = max(current, value)
        else:
            branches.append(current)
            current = value
    branches.append(current)
    return min(branches)


def build_chat_semantic_rag_context(
    profile: DatabaseProfile,
    groups: list[str],
    operators: list[str],
    chunk_count: int,
) -> tuple[str, list[Any], dict[int, dict[str, float]], dict[int, float]]:
    """Retrieve a small vector candidate set, rank it by semantic group coverage, and format it for Chat."""

    if not groups:
        raise ValueError("/ask needs at least one retrieval filter.")
    try:
        vector_config, _profiles = load_vector_config(VECTOR_CONFIG_PATH, PROJECT_ROOT)
        embedding_model = str(vector_config["embedding_model"])
        words = chat_rag_query_words(groups)
        queries = [(f"group: {group}", group) for group in groups] + [(f"word: {word}", word) for word in words]
        embeddings = embed_texts(OLLAMA_CONFIG_PATH, embedding_model, [text for _label, text in queries])
        connection = open_database(profile.path)
        try:
            candidates: dict[int, Any] = {}
            candidate_limit = max(chunk_count * 4, 20)
            for embedding in embeddings[: len(groups)]:
                for hit in search_vectors(connection, embedding, candidate_limit):
                    candidates[hit.chunk_id] = hit
            distances = rag_demo_chunk_distances(
                connection,
                list(candidates),
                [label for label, _text in queries],
                embeddings,
            )
        finally:
            connection.close()
    except (OSError, sqlite3.Error, VectorError, OllamaEmbeddingError) as error:
        raise ValueError(f"Could not perform semantic RAG search in {profile.name}: {error}") from error

    scores = {
        chunk_id: semantic_group_distance(values, groups, operators)
        for chunk_id, values in distances.items()
    }
    hits = sorted(candidates.values(), key=lambda hit: scores[hit.chunk_id])[:chunk_count]
    query_label = "Semantic groups: " + " ".join(
        group if index == 0 else f"{operators[index - 1]} {group}"
        for index, group in enumerate(groups)
    )
    context, _attached_count = format_chat_rag_context(profile, query_label, hits)
    return context, hits, distances, scores


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
    for rendered_line in render_markdown_lines(rag_context.strip().splitlines(), config):
        print(rendered_line)
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
    """Resolve a chat-local path while keeping it in the active project."""

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
        raise ValueError(f"Project file not found: {filename}")
    return file_path


def resolve_chat_mp3_path(config: dict[str, Any], filename: str, *, must_exist: bool, command_name: str) -> Path:
    """Resolve one active-project MP3 file for a chat audio command."""

    audio_path = resolve_chat_project_path(config, filename, must_exist=must_exist)
    if audio_path.suffix.casefold() != CHAT_AUDIO_EXTENSION:
        raise ValueError(f"{command_name} accepts MP3 files only: {filename}")
    return audio_path


def chat_project_directory_argument(config: dict[str, Any]) -> str:
    """Return the active Chat project directory relative to the repository root."""

    project_directory = active_project_directory(config).resolve()
    try:
        return project_directory.relative_to(PROJECT_ROOT).as_posix()
    except ValueError as error:
        raise ValueError("The active Chat project must remain inside the repository.") from error


def run_chat_record(config: dict[str, Any], filename: str) -> Path:
    """Record the microphone through the portable MP3 recorder CLI."""

    output_path = resolve_chat_mp3_path(config, filename, must_exist=False, command_name="/rec")
    project_directory = active_project_directory(config).resolve()
    if output_path.parent != project_directory:
        raise ValueError("/rec saves MP3 files directly in the active project directory.")
    if not RECORD_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {RECORD_SCRIPT_PATH.name}")
    output_name = output_path.relative_to(project_directory).as_posix()
    result = subprocess.run(
        [
            sys.executable,
            str(RECORD_SCRIPT_PATH),
            "--project-dir",
            chat_project_directory_argument(config),
            output_name,
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"/rec command exited with code {result.returncode}.")
    return output_path


def run_chat_whisper(config: dict[str, Any], filename: str, *, debug: bool) -> Path:
    """Transcribe one active-project MP3 through the Whisper CLI."""

    source_path = resolve_chat_mp3_path(config, filename, must_exist=True, command_name="/whisper")
    project_directory = active_project_directory(config).resolve()
    if source_path.parent != project_directory:
        raise ValueError("/whisper accepts MP3 files directly in the active project directory.")
    if not WHISPER_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {WHISPER_SCRIPT_PATH.name}")
    run_options: dict[str, Any] = {"cwd": PROJECT_ROOT, "check": False}
    if not debug:
        run_options.update({"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"})
    result = subprocess.run(
        [
            sys.executable,
            str(WHISPER_SCRIPT_PATH),
            "--project-dir",
            chat_project_directory_argument(config),
            source_path.name,
        ],
        **run_options,
    )
    if result.returncode:
        diagnostics = "\n".join(
            output.strip()
            for output in (getattr(result, "stdout", ""), getattr(result, "stderr", ""))
            if isinstance(output, str) and output.strip()
        )
        message = f"/whisper command exited with code {result.returncode}."
        raise ValueError(f"{message}\n{diagnostics}" if diagnostics else message)
    return source_path.with_suffix(".txt")


def read_chat_transcript(transcript_path: Path) -> str:
    """Read one successfully saved Whisper transcript for immediate Chat display."""

    try:
        transcript = transcript_path.read_text(encoding="utf-8-sig").strip()
    except UnicodeDecodeError as error:
        raise ValueError(f"Transcript is not valid UTF-8: {transcript_path.name}") from error
    except OSError as error:
        raise ValueError(f"Could not read transcript {transcript_path.name}: {error}") from error
    if not transcript:
        raise ValueError(f"Transcript is empty: {transcript_path.name}")
    return transcript


def extract_transcript_body(transcript: str) -> str:
    """Return only recognized speech, without Whisper's saved-file metadata."""

    lines = transcript.splitlines()
    body_start = 0
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    while body_start < len(lines) and re.match(r"^(?:Source file|Whisper language):\s*", lines[body_start]):
        body_start += 1
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    body = "\n".join(lines[body_start:]).strip()
    if not body:
        raise ValueError("Whisper transcript contains no recognized speech.")
    return body


def run_chat_say(text: str, language: str, *, debug: bool) -> None:
    """Speak text with the configured voice for the active Chat language."""

    if not SPEECH_SCRIPT_PATH.is_file():
        raise ValueError(f"Tool not found: {SPEECH_SCRIPT_PATH.name}")
    language_options = {"cz": "--cz", "en": "--en", "es": "--es"}
    language_option = language_options.get(language)
    if language_option is None:
        raise ValueError(f"Unsupported speech language: {language}")
    if not text.strip():
        raise ValueError("Speech text is empty.")
    run_options: dict[str, Any] = {
        "cwd": PROJECT_ROOT,
        "check": False,
        "input": text,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if not debug:
        run_options["capture_output"] = True
    result = subprocess.run([sys.executable, str(SPEECH_SCRIPT_PATH), language_option, "-"], **run_options)
    if result.returncode:
        diagnostics = "\n".join(
            output.strip()
            for output in (getattr(result, "stdout", ""), getattr(result, "stderr", ""))
            if isinstance(output, str) and output.strip()
        )
        message = f"/say command exited with code {result.returncode}."
        raise ValueError(f"{message}\n{diagnostics}" if diagnostics else message)


def play_chat_mp3(config: dict[str, Any], filename: str) -> Path:
    """Play one MP3 found anywhere below the active project directory."""

    audio_path = resolve_chat_mp3_path(config, filename, must_exist=True, command_name="/play")
    try:
        play_audio_file(audio_path)
    except (FileNotFoundError, RuntimeError, OSError) as error:
        raise ValueError(str(error)) from error
    return audio_path


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


def clean_markdown_for_speech(markdown: str) -> str:
    """Remove common Markdown syntax while retaining text suitable for speech."""

    text = re.sub(r"^\s*```[^`]*\s*$", "", markdown, flags=re.MULTILINE)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:[-+*]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:---+|\*\*\*+|___+)\s*$", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("__", "").replace("~~", "").replace("`", "")
    text = re.sub(r"(?<!\w)\*(?=\S)|(?<=\S)\*(?!\w)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_chat_reply(config: dict[str, Any]) -> None:
    """Render the latest saved chat reply with James' small Markdown subset."""

    for rendered_line in render_markdown_lines(read_chat_last_reply(config).splitlines(), config):
        print(rendered_line)
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
    print(f"{terminal.style('/proj [SUBDIR]', fg='yellow', bold=True)} show project.json or temporarily switch the active project")
    print(f"{terminal.style('/db ID', fg='yellow', bold=True)} send an answer stored under ID in the main task database")
    print()


def render_chat_help(config: dict[str, Any]) -> None:
    """Print the chat command help without leaving the active chat session."""

    try:
        content = CHAT_COMMANDS_PATH.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        Terminal().r(f"Cannot read chat help: {error}")
        return
    for rendered_line in render_markdown_lines(content.splitlines(), config):
        print(rendered_line)
    print()


def render_chat_project_config(config: dict[str, Any]) -> None:
    """Render parsed project.json and the optional active Chat-only directory override."""

    path = project_config_path(config)
    Terminal().c(f"{path.name}:")
    render_json_key_values(load_project_config(config), config)
    overridden_directory = config.get(CHAT_PROJECT_SUBDIR_OVERRIDE_KEY)
    if overridden_directory is None:
        Terminal().c("Chat project: project.json subdir (no session override).")
    else:
        Terminal().g(f"Chat project override: {validate_directory_name(str(overridden_directory))} (this session only).")
    print()


def render_chat_slash_commands(config: dict[str, Any]) -> None:
    """Show the localized slash-command catalog without leaving the active chat."""

    document_path = slash_commands_document_path(config)
    try:
        content = document_path.read_text(encoding="utf-8-sig").strip()
    except OSError as error:
        Terminal().r(f"Cannot read slash-command catalog: {error}")
        return
    for rendered_line in render_markdown_lines(content.splitlines(), config):
        print(rendered_line)
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
        requested_project = extract_chat_proj_command(message)
        if requested_project is not None:
            if not requested_project:
                try:
                    render_chat_project_config(config)
                except ValueError as error:
                    Terminal().y(str(error))
                continue
            try:
                config[CHAT_PROJECT_SUBDIR_OVERRIDE_KEY] = validate_directory_name(requested_project)
                ensure_chat_context_file(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            clear_screen()
            render_page_header(config, "chat", chat_debug=chat_debug, chat_rag=active_rag_profile)
            render_chat_commands()
            Terminal().g(
                f"Chat project switched to {config[CHAT_PROJECT_SUBDIR_OVERRIDE_KEY]} for this session only; "
                f"{project_config_path(config).name} was not changed."
            )
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
                f"Use /chunk FILTER[, FILTER ...] ({chat_rag_chunk_count_default()} chunks by default)."
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
            ask_request = extract_chat_ask_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if ask_request is not None:
            if active_rag_profile is None:
                Terminal().y("Select a RAG wiki first, for example /rag btc.")
                continue
            filter_input, question = ask_request
            try:
                rag_tags, rag_operators, remaining_text = split_chat_rag_filter_expression(filter_input)
                if rag_tags and remaining_text:
                    raise ValueError("Use only /ask retrieval filters before ::, for example (bitcoin mining) or (hardware wallet).")
                groups = rag_tags or [filter_input]
                operators = rag_operators if rag_tags else []
                chunk_count = chat_rag_chunk_count_default()
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().c(f"Semantic RAG search in {active_rag_profile.path.name} for {chunk_count} chunk(s)…")
            try:
                rag_context, hits, _distances, _scores = build_chat_semantic_rag_context(
                    active_rag_profile,
                    groups,
                    operators,
                    chunk_count,
                )
                replace_chat_rag_context(config, rag_context)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            render_chat_rag_context(config, rag_context)
            Terminal().g(f"Semantic RAG attached {len(hits)} chunk(s); submitting the question.")
            message = question
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
            if message.strip().casefold() == "/cat" or file_path.suffix.casefold() == ".md":
                for rendered_line in render_markdown_lines(content.splitlines(), config):
                    print(rendered_line)
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
                Terminal().c("Latest chat reply:")
                render_chat_reply(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            continue
        try:
            say_request = extract_chat_say_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if say_request is not None:
            say_kind, say_value = say_request
            try:
                if say_kind == "text":
                    speech_text = say_value
                    source_label = "provided text"
                elif say_kind == "file":
                    source_path, speech_text = read_chat_project_file(config, say_value, command_name="/say")
                    source_label = source_path.name
                else:
                    speech_text = clean_markdown_for_speech(read_chat_last_reply(config))
                    source_label = "latest chat reply"
                Terminal().c(f"Speaking {source_label} ({config['language']})…")
                run_chat_say(speech_text, str(config["language"]), debug=chat_debug)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g("Speech finished.")
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
        voice_filename = extract_chat_voice_command(message)
        if voice_filename is not None:
            try:
                voice_filename = voice_filename or chat_command_default_file("record")
                output_path = run_chat_record(config, voice_filename)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Recording saved: {output_path.name}")
            try:
                Terminal().c(f"Transcribing {output_path.name}…")
                transcript_path = run_chat_whisper(config, output_path.name, debug=chat_debug)
                transcript = read_chat_transcript(transcript_path)
                voice_prompt = extract_transcript_body(transcript)
                _last_reply_commands, _last_reply_label, isolated_chat_flow = chat_last_reply_sc_settings(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().y(f"Transcript saved: {transcript_path.name}")
            Terminal().g(transcript)
            print()
            Terminal().c("Correcting likely speech-recognition errors…")
            write_chat_input(config, voice_prompt)
            exit_code = run_flow(
                isolated_chat_flow,
                pause_after=False,
                report_result=False,
                clear_before=False,
                model_override=active_model,
                task_override=active_task,
                sc_commands=["speechfix"],
                sc_language="cz",
                capture_output=not chat_debug,
                quiet=not chat_debug,
            )
            if exit_code:
                pause()
                return
            try:
                corrected_transcript = read_chat_last_reply(config)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().c("Submitting corrected transcription to Chat…")
            write_chat_input(config, corrected_transcript)
            exit_code = run_flow(
                isolated_chat_flow,
                pause_after=False,
                report_result=False,
                clear_before=False,
                model_override=active_model,
                task_override=active_task,
                sc_commands=["chat"],
                sc_language=str(config["language"]),
                capture_output=not chat_debug,
                quiet=not chat_debug,
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
            append_chat_turn(config, corrected_transcript)
            continue
        record_filename = extract_chat_rec_command(message)
        if record_filename is not None:
            try:
                record_filename = record_filename or chat_command_default_file("record")
                output_path = run_chat_record(config, record_filename)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Recording saved: {output_path.name}")
            continue
        whisper_filename = extract_chat_whisper_command(message)
        if whisper_filename is not None:
            try:
                whisper_filename = whisper_filename or chat_command_default_file("whisper")
                Terminal().c(f"Transcribing {whisper_filename}…")
                transcript_path = run_chat_whisper(config, whisper_filename, debug=chat_debug)
                transcript = read_chat_transcript(transcript_path)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().y(f"Transcript saved: {transcript_path.name}")
            Terminal().g(transcript)
            print()
            continue
        play_filename = extract_chat_play_command(message)
        if play_filename is not None:
            try:
                play_filename = play_filename or chat_command_default_file("play")
                Terminal().c(f"Playing {play_filename}…")
                audio_path = play_chat_mp3(config, play_filename)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().g(f"Finished playing: {audio_path.name}")
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
                quiet=not chat_debug,
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
            database_task_id = extract_chat_db_command(message)
        except ValueError as error:
            Terminal().y(str(error))
            continue
        if database_task_id is not None:
            try:
                prompt = read_chat_database_answer(config, database_task_id)
            except ValueError as error:
                Terminal().y(str(error))
                continue
            Terminal().c(f"Database answer {database_task_id} sent as chat input:")
            print(prompt, end="" if prompt.endswith("\n") else "\n")
            print()
            # A saved answer is submitted verbatim, even if it starts with a slash.
            sc_commands: list[str] = []
        else:
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
                quiet=not chat_debug,
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
            quiet=not chat_debug,
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


def resolve_flow_file(flow_name: str) -> Path:
    """Resolve one user-selected filename strictly below the ``flows`` directory."""

    candidate = Path(flow_name.strip())
    if not flow_name.strip() or candidate.name != flow_name.strip() or candidate.suffix.casefold() != ".txt":
        raise ValueError("Enter a flows/*.txt filename without a directory path.")
    selected_path = PROJECT_ROOT / "flows" / candidate.name
    if not selected_path.is_file():
        raise ValueError(f"Flow file not found in flows: {candidate.name}")
    return selected_path


def run_user_input_flow(config: dict[str, Any]) -> None:
    """Ask for an existing ``flows/*.txt`` file and run it through the normal runner."""

    clear_screen()
    render_page_header(config, "flow", "user input")
    width = int(config["width"])
    render_section_header(width, "FLOW · USER INPUT", config)
    print("Enter a flow filename from flows/, for example flow_test.txt.")
    flow_name = input("Flow (*.txt; empty = cancel): ").strip()
    if not flow_name:
        return
    try:
        selected_path = resolve_flow_file(flow_name)
    except ValueError as error:
        Terminal().r(str(error))
        pause()
        return
    run_flow(selected_path.name)


def show_flow_info(config: dict[str, Any], flow_name: str, category_title: str) -> None:
    """Show one configured flow file without running it."""

    try:
        selected_path = resolve_flow_file(flow_name)
    except ValueError as error:
        raise ValueError(f"Flow info requires a flows/*.txt filename without a directory path: {error}") from error
    show_text_document(config, selected_path, f"FLOW · {category_title} · {flow_name}")


def render_flow_menu(config: dict[str, Any], selected_index: int) -> None:
    """Draw the Flow category menu."""

    terminal = Terminal()
    width = int(config["width"])
    categories = (
        "user input",
        "test",
        "single",
        "code",
        "batch",
        "media",
        "MCP base",
        "MCP hardware",
        "rag_wiki",
    )
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
        None,
        ("flows_test", "TEST"),
        ("flows_single", "SINGLE"),
        ("flows_code", "CODE"),
        ("flows_batch", "BATCH"),
        ("flows_media", "MEDIA"),
        ("flows_mcp_base", "MCP BASE"),
        ("flows_mcp_hardware", "MCP HARDWARE"),
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
            selected_category = categories[selected_index]
            if selected_category is None:
                run_user_input_flow(config)
            else:
                flow_list_menu(config, *selected_category)


def show_help(config: dict[str, Any]) -> None:
    """Display the maintained Help document."""

    show_text_document(config, JAMES_HELP_PATH, "HELP")


def about_document_path(config: dict[str, Any]) -> Path:
    """Choose the Czech About document only for the Czech James language."""

    return JAMES_ABOUT_CZ_PATH if config.get("language") == "cz" else JAMES_ABOUT_PATH


def optional_wrapper_versions() -> list[tuple[str, str | None]]:
    """Read optional wrapper versions without importing plugins or their dependencies."""

    versions: list[tuple[str, str | None]] = []
    for name, path in OPTIONAL_WRAPPER_PATHS:
        if not path.is_file():
            versions.append((name, None))
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
        except OSError:
            versions.append((name, None))
            continue
        match = re.search(r'^\s*__version__\s*=\s*["\']([^"\']+)["\']\s*$', source, re.MULTILINE)
        version = match.group(1) if match else "present (version not declared)"
        versions.append((name, version))
    return versions


def render_optional_wrapper_versions(config: dict[str, Any]) -> None:
    """Render present and absent optional wrappers with intentionally distinct colors."""

    terminal = Terminal()
    print()
    print(terminal.style("OPTIONAL PLUGIN VERSIONS", fg=configured_color(config, "col_head"), bold=True))
    for name, version in optional_wrapper_versions():
        rendered_name = terminal.style(f"{name}:", fg="yellow", bold=True)
        if version is None:
            rendered_status = terminal.color("bright_black", "not present")
        elif version == "present (version not declared)":
            rendered_status = terminal.color("yellow", version)
        else:
            rendered_status = terminal.color("green", version)
        print(f"  {rendered_name} {rendered_status}")


def show_about(config: dict[str, Any]) -> None:
    """Display About plus versions of locally present optional wrappers."""

    path = about_document_path(config)
    try:
        content = path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError as error:
        raise ValueError(f"Document is missing: {path.relative_to(PROJECT_ROOT)}") from error
    clear_screen()
    render_page_header(config, "about")
    width = int(config["width"])
    render_section_header(width, "ABOUT", config)
    print()
    for rendered_line in render_markdown_lines(content.splitlines(), config):
        print(rendered_line)
    render_optional_wrapper_versions(config)
    wait_for_back(width)


def main() -> int:
    """Run James until the user exits the main menu."""

    try:
        config = load_james_config()
        ensure_main_database(config)
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
                cowork_menu(config)
            elif key == "h":
                show_help(config)
    except (KeyboardInterrupt, RuntimeError, ValueError, OSError) as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

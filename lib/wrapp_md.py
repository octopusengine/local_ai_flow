"""Small, reusable Markdown renderer for terminal screens.

The renderer intentionally supports only the compact Markdown subset used by
the local terminal UI: headings, bullets, inline code, bold and italic spans,
fenced code blocks, and rules.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .wrapp_terminal import COLOR_ALIASES, COLORS, Terminal


__version__ = "0.26.07"


MARKDOWN_COLOR_DEFAULTS = {
    "col_text": "white",
    "col_basic": "green",
    "col_bold": "yellow",
    "col_italic": "green",
    "col_code": "bright_blue",
    "col_head": "bright_magenta",
    "col_dark": "bright_black",
    "col_err": "red",
}
TERMINAL_COLOR_NAMES = frozenset((*COLORS, *COLOR_ALIASES))
INLINE_MARKDOWN_PATTERN = re.compile(
    r"`([^`]+)`|\*\*(.+?)\*\*|(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)"
)
FENCED_CODE_BLOCK_PATTERN = re.compile(r"^\s*```[^`]*\s*$")


def load_markdown_settings(config_path: Path) -> dict[str, Any]:
    """Load and validate the renderer-specific JSON settings."""

    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Markdown settings are missing: {config_path.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {config_path.name}: {error}") from error
    if not isinstance(data, dict) or data.get("json_version") != "1":
        raise ValueError(f"{config_path.name} requires an object with 'json_version': '1'.")
    colors = data.get("colors")
    if not isinstance(colors, dict) or set(colors) != set(MARKDOWN_COLOR_DEFAULTS):
        expected_names = ", ".join(MARKDOWN_COLOR_DEFAULTS)
        raise ValueError(f"{config_path.name} requires a 'colors' object with: {expected_names}.")
    for name, color in colors.items():
        if not isinstance(color, str) or color not in TERMINAL_COLOR_NAMES:
            raise ValueError(f"{config_path.name} color '{name}' must be a supported terminal color name.")
    return data


def configured_color(config: dict[str, Any], name: str) -> str:
    """Read one configured Markdown color with a safe fallback for partial config."""

    colors = config.get("colors")
    color = colors.get(name) if isinstance(colors, dict) else None
    return color if isinstance(color, str) and color in TERMINAL_COLOR_NAMES else MARKDOWN_COLOR_DEFAULTS[name]


def render_bold_markdown(
    text: str,
    terminal: Terminal | None = None,
    *,
    bold_color: str = MARKDOWN_COLOR_DEFAULTS["col_bold"],
) -> str:
    """Render simple Markdown bold spans in the configured color."""

    output = terminal or Terminal()
    return re.sub(
        r"\*\*(.+?)\*\*",
        lambda match: output.color(bold_color, match.group(1)),
        text,
    )


def render_markdown_line(
    text: str,
    config: dict[str, Any],
    terminal: Terminal | None = None,
) -> str:
    """Render the compact Markdown subset used by terminal text screens."""

    width = int(config.get("width", 80))
    if re.fullmatch(r"\s*---\s*", text):
        return "_" * width

    heading_match = re.match(r"^\s*(#{1,3})\s+(.+?)\s*$", text)
    if heading_match is not None:
        heading_level = len(heading_match.group(1))
        heading_color = configured_color(config, "col_head" if heading_level == 1 else "col_bold")
        heading_text = f"*** {heading_match.group(2)} ***" if heading_level == 1 else heading_match.group(2)
        return (terminal or Terminal()).color(heading_color, heading_text)

    bullet_match = re.match(r"^(\s*)-\s+(.*)$", text)
    if bullet_match is not None:
        text = f"{bullet_match.group(1)}• {bullet_match.group(2)}"

    output = terminal or Terminal()
    bold_color = configured_color(config, "col_bold")
    italic_color = configured_color(config, "col_italic")
    code_color = configured_color(config, "col_code")

    def render_inline(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            return output.color(code_color, match.group(1))
        if match.group(2) is not None:
            return output.color(bold_color, match.group(2))
        return output.color(italic_color, match.group(3))

    return INLINE_MARKDOWN_PATTERN.sub(render_inline, text)


def render_markdown_lines(
    lines: Iterable[str],
    config: dict[str, Any],
    terminal: Terminal | None = None,
) -> list[str]:
    """Render Markdown lines, coloring fenced code-block content with ``col_basic``.

    Opening and closing triple-backtick fence lines are omitted from the output.
    """

    output = terminal or Terminal()
    basic_color = configured_color(config, "col_basic")
    is_fenced_code_block = False
    rendered_lines: list[str] = []
    for line in lines:
        if FENCED_CODE_BLOCK_PATTERN.fullmatch(line):
            is_fenced_code_block = not is_fenced_code_block
            continue
        if is_fenced_code_block:
            rendered_lines.append(output.color(basic_color, line))
        else:
            rendered_lines.append(render_markdown_line(line, config, output))
    return rendered_lines

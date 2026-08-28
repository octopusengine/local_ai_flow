"""Small, reusable Markdown renderer for James terminal screens.

The renderer intentionally supports only the compact Markdown subset used by
the local terminal UI: headings, bullets, inline code, bold spans, and rules.
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

from lib.wrapp_terminal import COLOR_ALIASES, COLORS, Terminal


JAMES_COLOR_DEFAULTS = {
    "col_text": "white",
    "col_basic": "green",
    "col_bold": "yellow",
    "col_head": "bright_magenta",
    "col_dark": "bright_black",
    "col_err": "red",
}
TERMINAL_COLOR_NAMES = frozenset((*COLORS, *COLOR_ALIASES))


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
    if not isinstance(colors, dict) or set(colors) != set(JAMES_COLOR_DEFAULTS):
        expected_names = ", ".join(JAMES_COLOR_DEFAULTS)
        raise ValueError(f"{config_path.name} requires a 'colors' object with: {expected_names}.")
    for name, color in colors.items():
        if not isinstance(color, str) or color not in TERMINAL_COLOR_NAMES:
            raise ValueError(f"{config_path.name} color '{name}' must be a supported terminal color name.")
    return data


def configured_color(config: dict[str, Any], name: str) -> str:
    """Read one configured James color, retaining a safe fallback for partial config."""

    colors = config.get("colors")
    color = colors.get(name) if isinstance(colors, dict) else None
    return color if isinstance(color, str) and color in TERMINAL_COLOR_NAMES else JAMES_COLOR_DEFAULTS[name]


def render_bold_markdown(
    text: str,
    terminal: Terminal | None = None,
    *,
    bold_color: str = JAMES_COLOR_DEFAULTS["col_bold"],
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
    """Render the compact Markdown subset used by James text and Chat screens."""

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
    basic_color = configured_color(config, "col_basic")

    def render_inline(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            return output.color(bold_color, match.group(1))
        return output.color(basic_color, match.group(2))

    return re.sub(r"\*\*(.+?)\*\*|`([^`]+)`", render_inline, text)

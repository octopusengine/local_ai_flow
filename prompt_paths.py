"""Ordered prompt lookup shared by the CLI and flow runner."""

from pathlib import Path
import re


def prompt_entries(value, root):
    entries = value if isinstance(value, list) else [value]
    if not entries or any(not isinstance(item, str) or not item.strip() for item in entries):
        raise ValueError("prompt_file must be a non-empty string or array of non-empty strings")
    root = Path(root)
    return [Path(item) if Path(item).is_absolute() else root / item for item in entries]


def find_prompt(value, root, name=None):
    candidates = []
    for entry in prompt_entries(value, root):
        if isinstance(value, list):
            candidate = entry / (f"{name}.txt" if name is not None else "prompt.txt")
        elif name is None:
            candidate = entry
        else:
            candidate = entry.parent / f"{name}.txt"
        candidates.append(candidate)
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Prompt file not found; searched: " + ", ".join(map(str, candidates)))


def resolve_short_prompt(value, sources, root):
    if isinstance(value, str) and re.fullmatch(r"/[A-Za-z0-9_-]+", value):
        return find_prompt(sources, root, value[1:])
    return None

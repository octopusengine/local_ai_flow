"""Základní souborové nástroje používané spolu s ``tool_schema.json``."""

from __future__ import annotations

import os
import subprocess


def list_files(path: str = ".") -> str:
    """Vrátí seřazený obsah adresáře; podadresáře označí lomítkem."""
    entries = []
    with os.scandir(path) as directory:
        for entry in directory:
            entries.append(entry.name + ("/" if entry.is_dir() else ""))
    return "\n".join(sorted(entries)) or "(empty directory)"


def read_file(path: str) -> str:
    """Přečte textový soubor v UTF-8."""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def write_file(path: str, content: str) -> str:
    """Vytvoří nebo přepíše textový soubor v UTF-8."""
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
    return f"Saved {path} ({len(content)} characters)"


def run_command(command: str) -> str:
    """Po výslovném potvrzení spustí shellový příkaz a vrátí jeho výstup."""
    answer = input(f"Run '{command}'? [y/N] ")
    if answer.strip().lower() != "y":
        return "The user declined to run this command."

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = (result.stdout + result.stderr).strip()
    return output or f"(no output, exit code {result.returncode})"


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
}

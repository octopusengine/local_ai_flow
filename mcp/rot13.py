"""Provide the ROT13 function used by the local MCP server."""

from __future__ import annotations


def rot13(word: str) -> str:
    """Encrypt one ASCII word with an uppercase ROT13 Caesar cipher."""

    if not isinstance(word, str) or not word:
        raise ValueError("word must be a non-empty string")

    uppercase_word = word.upper()
    if not uppercase_word.isascii() or not uppercase_word.isalpha():
        raise ValueError("word must contain ASCII letters A-Z only")

    return "".join(
        chr((ord(character) - ord("A") + 13) % 26 + ord("A"))
        for character in uppercase_word
    )

"""Reserve a command-line interface for future RAG vector-database management."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the placeholder parser and expose the future RAG scope in help."""

    return argparse.ArgumentParser(
        description="Reserved interface for local RAG vector-database management.",
        epilog="Vector storage, chunking, embedding, search, and maintenance are not implemented yet.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Accept the future command interface without performing any operation yet."""

    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

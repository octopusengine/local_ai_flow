"""Outline of a command-line interface for local RAG vector-database management.

The parser intentionally has no storage, embedding, or network side effects yet.
It reserves a stable command vocabulary before the selected vector backend is added.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the future-facing parser without implementing its commands."""

    parser = argparse.ArgumentParser(
        description="Reserved interface for local RAG vector-database management.",
        epilog=(
            "Outline only: vector storage, chunking, embedding, search, and "
            "maintenance are not implemented yet."
        ),
    )
    parser.add_argument(
        "--store",
        default="data/vector_db",
        help="persistent database directory (future default: %(default)s)",
    )
    parser.add_argument(
        "--backend",
        choices=("qdrant-local", "chroma", "faiss"),
        default="qdrant-local",
        help="storage adapter to use (future default: %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="reserve JSON output for automation")

    commands = parser.add_subparsers(dest="command", title="planned commands")

    init = commands.add_parser("init", help="create or inspect a collection schema")
    init.add_argument("--collection", default="knowledge", help="collection name")
    init.add_argument("--embedding-model", help="Ollama embedding model recorded in the schema")

    ingest = commands.add_parser("ingest", help="discover, chunk, embed, and upsert sources")
    ingest.add_argument("sources", nargs="+", help="files or directories to ingest")
    ingest.add_argument("--collection", default="knowledge", help="target collection")
    ingest.add_argument("--chunk-size", type=int, default=800, help="target chunk size in tokens")
    ingest.add_argument("--chunk-overlap", type=int, default=120, help="overlap in tokens")
    ingest.add_argument("--glob", default="**/*", help="source-file glob when a directory is supplied")
    ingest.add_argument("--dry-run", action="store_true", help="show the ingestion plan only")
    ingest.add_argument("--reindex", action="store_true", help="replace chunks from changed sources")

    search = commands.add_parser("search", help="embed a query and show retrieved chunks")
    search.add_argument("query", help="natural-language query")
    search.add_argument("--collection", default="knowledge", help="collection to search")
    search.add_argument("-k", type=int, default=5, help="maximum chunks to return")
    search.add_argument("--min-score", type=float, help="optional relevance cutoff")
    search.add_argument("--where", action="append", default=[], help="metadata filter: key=value")

    ask = commands.add_parser("ask", help="reserve RAG answer generation from retrieved chunks")
    ask.add_argument("question", help="question for the chat model")
    ask.add_argument("--collection", default="knowledge", help="collection to retrieve from")
    ask.add_argument("-k", type=int, default=5, help="maximum context chunks")
    ask.add_argument("--model", help="Ollama chat model")
    ask.add_argument("--show-context", action="store_true", help="print selected chunks and sources")

    inspect = commands.add_parser("inspect", help="show collections, schema, and chunk statistics")
    inspect.add_argument("--collection", help="limit output to one collection")

    verify = commands.add_parser("verify", help="check source hashes and embedding/schema compatibility")
    verify.add_argument("--collection", default="knowledge", help="collection to validate")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Accept the future command interface without performing any operation yet."""

    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

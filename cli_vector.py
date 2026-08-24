"""Create and query named local RAG databases backed by SQLite and sqlite-vec."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from lib.wrapp_ollama import OllamaEmbeddingError, embed_texts
from lib.wrapp_log import get_project_directory, load_project_config
from lib.wrapp_vector import (
    VectorError, chunk_file, ingest, inspect, load_config, new_database_profile,
    open_database, register_database_profile, search_text, search_vectors,
    select_profile, set_main_db, source_files, verify,
)


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_DIR / "cli_vector.json"
OLLAMA_CONFIG_PATH = PROJECT_DIR / "lib" / "ollama.json"


def positive_integer(value: str) -> int:
    """Parse a strictly positive command-line integer."""

    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the local vector-database command line."""

    parser = argparse.ArgumentParser(description="Manage named local RAG databases using SQLite, FTS5, and sqlite-vec.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="vector configuration (default: %(default)s)")
    parser.add_argument("--db", metavar="PROFILE|FILE.db", help="override configured main_db")
    parser.add_argument("--set-wiki", metavar="PROFILE|FILE.db", help="save this profile as main_db, then exit")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = parser.add_subparsers(dest="command", title="commands")
    commands.add_parser("init", help="create the selected database and its relational/FTS schema")

    ingest_parser = commands.add_parser("ingest", help="chunk and index changed files in the selected source group")
    ingest_parser.add_argument("--chunk-size", type=positive_integer, help="override configured chunk size in characters")
    ingest_parser.add_argument("--chunk-overlap", type=positive_integer, help="override configured overlap in characters")
    ingest_parser.add_argument("--dry-run", action="store_true", help="list selected files without writing or contacting Ollama")
    ingest_parser.add_argument("--no-embed", action="store_true", help="store sources and FTS chunks only; defer Ollama embeddings")
    ingest_parser.add_argument("--reindex", action="store_true", help="replace chunks even if their source hash is unchanged")

    new_wiki_parser = commands.add_parser("ingest-wiki", help="create and fill a new named wiki from rag_wiki/src/NAME")
    new_wiki_parser.add_argument("name", help="new wiki/source-group name, for example: bitcoin")
    new_wiki_parser.add_argument("--chunk-size", type=positive_integer, help="override configured chunk size in characters")
    new_wiki_parser.add_argument("--chunk-overlap", type=positive_integer, help="override configured overlap in characters")
    new_wiki_parser.add_argument("--reindex", action="store_true", help="replace chunks for every source when the wiki profile already exists")

    search_parser = commands.add_parser("search", help="search chunks in the selected database")
    search_parser.add_argument("query", help="text to find")
    search_parser.add_argument("-k", type=positive_integer, default=5, help="maximum results (default: %(default)s)")
    search_parser.add_argument("--mode", choices=("vector", "text"), default="vector", help="vector uses Ollama; text uses local FTS5")

    context_parser = commands.add_parser("context", help="write retrieved chunks as a file suitable for cli_tool.py / cli_ollama.py")
    context_parser.add_argument("query", help="question or topic to retrieve")
    context_parser.add_argument("--out", type=Path, required=True, help="context file to create inside the active project directory")
    context_parser.add_argument("-k", type=positive_integer, default=3, help="maximum chunks to include (default: %(default)s)")
    context_parser.add_argument("--mode", choices=("vector", "text"), default="text", help="text is local FTS5; vector uses Ollama")
    context_parser.add_argument("--max-chars", type=positive_integer, default=6000, help="maximum context characters (default: %(default)s)")
    commands.add_parser("inspect", help="show selected database statistics and embedding contract")
    commands.add_parser("verify", help="check schema and chunk/vector consistency")
    return parser


def _print(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif isinstance(value, dict):
        for key, item in value.items():
            print(f"{key}: {item}")
    else:
        print(value)


def _print_hits(hits: list[object], as_json: bool) -> None:
    values = [{"chunk_id": hit.chunk_id, "path": hit.path, "page": hit.page_number, "chunk": hit.chunk_index, "distance": hit.distance, "rank": hit.rank, "text": hit.text} for hit in hits]
    if as_json:
        _print(values, True)
    elif not values:
        print("No matching chunks.")
    else:
        for index, hit in enumerate(values, start=1):
            location = hit["path"] + (f" p.{hit['page']}" if hit["page"] else "")
            measure = f"distance={hit['distance']:.4f}" if hit["distance"] is not None else f"rank={hit['rank']:.4f}"
            print(f"[{index}] {location}, chunk {hit['chunk']}, {measure}\n{hit['text']}\n")


def _context_text(profile_name: str, query: str, hits: list[object], maximum_characters: int) -> str:
    """Return retrieved chunks with enough provenance for a later model answer."""

    header = [
        "# RAG context",
        "",
        f"- Database profile: `{profile_name}`",
        f"- Query: {query}",
        "- Use this as supporting material; source paths identify the retrieved document.",
    ]
    parts = ["\n".join(header)]
    used = len(parts[0])
    for number, hit in enumerate(hits, start=1):
        location = hit.path + (f", page {hit.page_number}" if hit.page_number else "")
        block = f"## Result {number}: {location} (chunk {hit.chunk_index})\n\n{hit.text.strip()}"
        separator = 2 if parts else 0
        if used + separator + len(block) > maximum_characters:
            remaining = maximum_characters - used - separator
            if remaining <= 0:
                break
            block = block[:remaining].rstrip() + "\n\n[context truncated]"
            parts.append(block)
            break
        parts.append(block)
        used += separator + len(block)
    if len(parts) == 1:
        parts.append("## No matching chunks\n\nThe selected database did not return a matching source.")
    return "\n\n".join(parts) + "\n"


def _context_path(path: Path, project_directory: Path) -> Path:
    """Resolve a context output without allowing it to escape the active project."""

    resolved = (project_directory / path).resolve()
    try:
        resolved.relative_to(project_directory.resolve())
    except ValueError as error:
        raise VectorError("--out must point inside the active project directory") from error
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """Run one local RAG storage command without invoking another CLI."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        config_path = arguments.config if arguments.config.is_absolute() else PROJECT_DIR / arguments.config
        if arguments.set_wiki:
            profile = set_main_db(config_path, PROJECT_DIR, arguments.set_wiki)
            _print({"main_db": profile.name, "database": str(profile.path), "source_group": profile.source_group}, arguments.json)
            return 0
        if arguments.command is None:
            parser.print_help()
            return 0
        config, profiles = load_config(config_path, PROJECT_DIR)
        source_root = PROJECT_DIR / config["source_root"]
        if arguments.command == "ingest-wiki":
            requested_profile = new_database_profile(config, PROJECT_DIR, arguments.name)
            profile = profiles.get(requested_profile.name, requested_profile)
            files = source_files(source_root, profile.source_group)
            if not files:
                raise VectorError(f"No supported .md, .txt, or .pdf sources found in {source_root / profile.source_group}.")
            chunk_size = arguments.chunk_size or config.get("chunk_size", 1200)
            chunk_overlap = arguments.chunk_overlap or config.get("chunk_overlap", 160)
            connection = open_database(profile.path)
            try:
                result = ingest(connection, source_root, profile.source_group, config["embedding_model"], None, chunk_size=chunk_size, chunk_overlap=chunk_overlap, reindex=arguments.reindex)
            finally:
                connection.close()
            selected = set_main_db(config_path, PROJECT_DIR, profile.name) if profile.name in profiles else register_database_profile(config_path, PROJECT_DIR, profile.name)
            _print({"main_db": selected.name, "database": str(selected.path), "source_group": selected.source_group, "profile_action": "updated" if profile.name in profiles else "created", "embedding_status": "pending", **result}, arguments.json)
            return 0
        profile = select_profile(profiles, arguments.db, config["main_db"])
        connection = open_database(profile.path)
        try:
            if arguments.command == "init":
                _print({"database": str(profile.path), "profile": profile.name, **inspect(connection)}, arguments.json)
            elif arguments.command == "inspect":
                _print({"database": str(profile.path), "profile": profile.name, "source_group": profile.source_group, **inspect(connection)}, arguments.json)
            elif arguments.command == "verify":
                problems = verify(connection)
                _print({"database": str(profile.path), "ok": not problems, "problems": problems}, arguments.json)
                return 0 if not problems else 1
            elif arguments.command == "ingest":
                chunk_size = arguments.chunk_size or config.get("chunk_size", 1200)
                chunk_overlap = arguments.chunk_overlap or config.get("chunk_overlap", 160)
                files = source_files(source_root, profile.source_group)
                if arguments.dry_run:
                    preview = [{"path": path.relative_to(source_root).as_posix(), "chunks": len(chunk_file(path, chunk_size, chunk_overlap))} for path in files]
                    _print({"profile": profile.name, "database": str(profile.path), "files": preview}, arguments.json)
                else:
                    embedder = None if arguments.no_embed else lambda texts: embed_texts(OLLAMA_CONFIG_PATH, config["embedding_model"], texts)
                    result = ingest(connection, source_root, profile.source_group, config["embedding_model"], embedder, chunk_size=chunk_size, chunk_overlap=chunk_overlap, reindex=arguments.reindex)
                    _print({"database": str(profile.path), **result}, arguments.json)
            elif arguments.command == "search":
                hits = search_text(connection, arguments.query, arguments.k) if arguments.mode == "text" else search_vectors(connection, embed_texts(OLLAMA_CONFIG_PATH, config["embedding_model"], [arguments.query])[0], arguments.k)
                _print_hits(hits, arguments.json)
            elif arguments.command == "context":
                hits = search_text(connection, arguments.query, arguments.k) if arguments.mode == "text" else search_vectors(connection, embed_texts(OLLAMA_CONFIG_PATH, config["embedding_model"], [arguments.query])[0], arguments.k)
                project_directory = get_project_directory(PROJECT_DIR, load_project_config(PROJECT_DIR))
                output_path = _context_path(arguments.out, project_directory)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(_context_text(profile.name, arguments.query, hits, arguments.max_chars), encoding="utf-8")
                _print({"database": str(profile.path), "project_directory": str(project_directory), "mode": arguments.mode, "query": arguments.query, "chunks": len(hits), "context_file": str(output_path)}, arguments.json)
        finally:
            connection.close()
        return 0
    except (OllamaEmbeddingError, VectorError) as error:
        print(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

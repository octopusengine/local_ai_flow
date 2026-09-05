"""Create and query named local RAG databases backed by SQLite and sqlite-vec."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

from lib.wrapp_ollama import OllamaEmbeddingError, embed_texts
from lib.wrapp_log import get_project_directory, load_project_config
from lib.wrapp_vector import (
    VectorError, chunk_file, ingest, inspect, load_config, new_database_profile,
    open_database, register_database_profile, search_text, search_vectors,
    validate_embedding_model, select_profile, set_main_db, source_files, verify, web_sources,
)
from rag_wiki.rag_swg import (
    _rag_svg_confidence, _rag_svg_distances, _svg_path, _svg_query_groups,
    _svg_query_terms, _write_rag_svg,
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


def nonnegative_integer(value: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if result < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return result


class _EmbeddingProgress:
    """Print restrained, ingest-wide progress for a potentially long ingest."""

    def __init__(self, *, enabled: bool) -> None:
        self.enabled = enabled
        self.path = ""
        self.total = 0
        self.completed = 0
        self.started_at = 0.0
        self.next_percentage = 20

    def start(self, label: str, total: int) -> None:
        self.path = label
        self.total = total
        self.completed = 0
        self.started_at = time.monotonic()
        self.next_percentage = 20

    def advance(self, increment: int) -> None:
        """Add completed chunks from the current Ollama request."""

        self.update(self.completed + increment)

    def update(self, completed: int) -> None:
        """Report after a 20-second grace period, then about every fifth."""

        if not self.enabled or not self.total:
            return
        self.completed = completed
        elapsed = time.monotonic() - self.started_at
        percentage = completed * 100 / self.total
        if elapsed < 20 or percentage < self.next_percentage:
            return
        rate = completed / elapsed
        remaining_seconds = (self.total - completed) / rate if rate else 0.0
        print(
            f"embedding: {self.path}: {completed}/{self.total} chunks "
            f"({percentage:.0f} %), elapsed {elapsed:.0f} s, ETA {remaining_seconds:.0f} s"
        )
        self.next_percentage = (int(percentage // 20) + 1) * 20


def _batched_embedder(model_name: str, batch_size: int, progress: _EmbeddingProgress):
    """Return an Ollama embedder that keeps requests and progress manageable."""

    def embed(texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            embeddings.extend(embed_texts(OLLAMA_CONFIG_PATH, model_name, batch))
            progress.advance(len(batch))
        return embeddings

    return embed


def _embedding_batch_size(arguments: argparse.Namespace, config: dict[str, object]) -> int:
    """Choose and validate the configured or explicitly requested batch size."""

    candidate = getattr(arguments, "embedding_batch_size", None)
    if candidate is None:
        candidate = config.get("embedding_batch_size", 16)
    if not isinstance(candidate, int) or isinstance(candidate, bool) or candidate <= 0:
        raise VectorError("embedding_batch_size must be a positive whole number.")
    return candidate


def _web_fetch_notice(source: object) -> None:
    """Show one sequential web connection before it is attempted."""

    print(f"web: connecting {source.name}: {source.url}")


def _web_result_notice(source: object, result: str) -> None:
    """Show the outcome of one web connection without stopping other pages."""

    print(f"web: {source.name}: {result}")


def _local_sources_notice(files: list[Path], source_root: Path) -> None:
    """Show a compact inventory of local material before ingesting it."""

    relative_paths = [path.relative_to(source_root).as_posix() for path in files]
    if len(relative_paths) <= 3:
        summary = ", ".join(relative_paths) or "none"
    else:
        summary = f"{', '.join(relative_paths[:3])}, ... (+{len(relative_paths) - 3})"
    print(f"local: source files ({len(relative_paths)}): {summary}")


def _local_result_notice(relative_path: str, result: str) -> None:
    """Show the ingest outcome of one local PDF, text, or Markdown source."""

    print(f"local: {relative_path}: {result}")


def build_parser() -> argparse.ArgumentParser:
    """Build the local vector-database command line."""

    parser = argparse.ArgumentParser(description="Manage named local RAG databases using SQLite, FTS5, and sqlite-vec.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="vector configuration (default: %(default)s)")
    parser.add_argument("--db", metavar="PROFILE|FILE.db", help="override configured main_db")
    parser.add_argument("--set-wiki", metavar="PROFILE|FILE.db", help="save this profile as main_db, then exit")
    parser.add_argument("--svg", metavar="QUERY", help="write an external SVG map for a vector query, then exit")
    parser.add_argument("--svg-k", type=positive_integer, default=5, help="chunks in the SVG map (default: %(default)s)")
    parser.add_argument("--svg-out", type=Path, default=Path("rag.svg"), help="SVG file inside the active project (default: %(default)s)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = parser.add_subparsers(dest="command", title="commands")
    commands.add_parser("init", help="create the selected database and its relational/FTS schema")

    ingest_parser = commands.add_parser("ingest", help="chunk and index changed files in the selected source group")
    ingest_parser.add_argument("--chunk-size", type=positive_integer, help="override configured chunk size in characters")
    ingest_parser.add_argument("--chunk-overlap", type=nonnegative_integer, help="override configured overlap in characters")
    ingest_parser.add_argument("--dry-run", action="store_true", help="list selected files without writing or contacting Ollama")
    ingest_parser.add_argument("--no-embed", action="store_true", help="store sources and FTS chunks only; defer Ollama embeddings")
    ingest_parser.add_argument("--no-web", action="store_true", help="ignore the optional web_src.json manifest in the selected source group")
    ingest_parser.add_argument("--reindex", action="store_true", help="replace chunks even if their source hash is unchanged")
    ingest_parser.add_argument("--prune", action="store_true", help="remove sources no longer present; preserve failed web fetches")
    ingest_parser.add_argument("--overwrite", action="store_true", help="build and verify a replacement database before publishing it atomically")
    ingest_parser.add_argument("--embedding-batch-size", type=positive_integer, help="chunks per Ollama embedding request (default: embedding_batch_size in config)")

    new_wiki_parser = commands.add_parser("ingest-wiki", help="create and fill a new named wiki from rag_wiki/src/NAME")
    new_wiki_parser.add_argument("name", help="new wiki/source-group name, for example: bitcoin")
    new_wiki_parser.add_argument("--chunk-size", type=positive_integer, help="override configured chunk size in characters")
    new_wiki_parser.add_argument("--chunk-overlap", type=nonnegative_integer, help="override configured overlap in characters")
    new_wiki_parser.add_argument("--embed", action="store_true", help="create vector embeddings immediately with the configured Ollama model")
    new_wiki_parser.add_argument("--no-web", action="store_true", help="ignore the optional web_src.json manifest in the new source group")
    new_wiki_parser.add_argument("--embedding-batch-size", type=positive_integer, help="chunks per Ollama embedding request (default: embedding_batch_size in config)")
    new_wiki_parser.add_argument("--reindex", action="store_true", help="replace chunks for every source when the wiki profile already exists")
    new_wiki_parser.add_argument("--prune", action="store_true", help="remove sources no longer present; preserve failed web fetches")
    new_wiki_parser.add_argument("--overwrite", action="store_true", help="build and verify a replacement database before publishing it atomically")

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
        config, profiles = load_config(config_path, PROJECT_DIR)
        if arguments.svg is not None:
            query = arguments.svg.strip()
            if not query:
                raise VectorError("--svg needs a non-empty query.")
            profile = select_profile(profiles, arguments.db, config["main_db"])
            words = _svg_query_terms(query)
            groups = _svg_query_groups(query)
            node_labels = [*words, *groups]
            connection = open_database(profile.path)
            try:
                model = validate_embedding_model(connection, config["embedding_model"])
                embeddings = embed_texts(OLLAMA_CONFIG_PATH, model, [query, *node_labels])
                hits = search_vectors(connection, embeddings[0], arguments.svg_k)
                distances = _rag_svg_distances(connection, [hit.chunk_id for hit in hits], node_labels, embeddings[1:])
                confidence = _rag_svg_confidence(connection, embeddings[0], hits)
            finally:
                connection.close()
            project_directory = get_project_directory(PROJECT_DIR, load_project_config(PROJECT_DIR))
            output_path = _svg_path(arguments.svg_out, project_directory)
            _write_rag_svg(profile.name, query, hits, distances, output_path, groups=groups, confidence=confidence)
            _print({
                "database": str(profile.path),
                "profile": profile.name,
                "query": query,
                "chunks": len(hits),
                "svg_file": str(output_path),
            }, arguments.json)
            return 0
        if arguments.command is None:
            parser.print_help()
            return 0
        source_root = PROJECT_DIR / config["source_root"]
        if arguments.command == "ingest-wiki":
            requested_profile = new_database_profile(config, PROJECT_DIR, arguments.name)
            profile = profiles.get(requested_profile.name, requested_profile)
            files = source_files(source_root, profile.source_group)
            configured_web_sources = [] if arguments.no_web else web_sources(source_root, profile.source_group, config["web_src_file"])
            if not files and not configured_web_sources and not (arguments.prune or arguments.overwrite):
                raise VectorError(f"No supported .md, .txt, .pdf, or declared web sources found in {source_root / profile.source_group}.")
            if not arguments.json:
                _local_sources_notice(files, source_root)
            chunk_size = arguments.chunk_size or config.get("chunk_size", 1200)
            chunk_overlap = arguments.chunk_overlap if arguments.chunk_overlap is not None else config.get("chunk_overlap", 160)
            progress = _EmbeddingProgress(enabled=not arguments.json)
            embedder = None if not arguments.embed else _batched_embedder(
                config["embedding_model"], _embedding_batch_size(arguments, config), progress,
            )
            connection = open_database(profile.path)
            try:
                result = ingest(
                    connection,
                    source_root,
                    profile.source_group,
                    config["embedding_model"],
                    embedder,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    reindex=arguments.reindex or arguments.overwrite,
                    prune=arguments.prune,
                    overwrite=arguments.overwrite,
                    on_embedding_start=None if embedder is None else progress.start,
                    on_local_result=None if arguments.json else _local_result_notice,
                    web_src_file=None if arguments.no_web else config["web_src_file"],
                    on_web_fetch=None if arguments.json or arguments.no_web else _web_fetch_notice,
                    on_web_result=None if arguments.json or arguments.no_web else _web_result_notice,
                )
                embedding_status = inspect(connection)["embedding_status"]
            finally:
                connection.close()
            selected = set_main_db(config_path, PROJECT_DIR, profile.name) if profile.name in profiles else register_database_profile(config_path, PROJECT_DIR, profile.name)
            _print({"main_db": selected.name, "database": str(selected.path), "source_group": selected.source_group, "profile_action": "updated" if profile.name in profiles else "created", "embedding_status": embedding_status, **result}, arguments.json)
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
                chunk_overlap = arguments.chunk_overlap if arguments.chunk_overlap is not None else config.get("chunk_overlap", 160)
                files = source_files(source_root, profile.source_group)
                configured_web_sources = [] if arguments.no_web else web_sources(source_root, profile.source_group, config["web_src_file"])
                if arguments.dry_run:
                    preview = [{"path": path.relative_to(source_root).as_posix(), "chunks": len(chunk_file(path, chunk_size, chunk_overlap))} for path in files]
                    _print({"profile": profile.name, "database": str(profile.path), "local_files": preview, "web_sources": [{"name": source.name, "url": source.url} for source in configured_web_sources]}, arguments.json)
                else:
                    if not arguments.json:
                        _local_sources_notice(files, source_root)
                    progress = _EmbeddingProgress(enabled=not arguments.json)
                    embedder = None if arguments.no_embed else _batched_embedder(
                        config["embedding_model"], _embedding_batch_size(arguments, config), progress,
                    )
                    result = ingest(
                        connection,
                        source_root,
                        profile.source_group,
                        config["embedding_model"],
                        embedder,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        reindex=arguments.reindex or arguments.overwrite,
                        prune=arguments.prune,
                        overwrite=arguments.overwrite,
                        on_embedding_start=None if arguments.no_embed else progress.start,
                        on_local_result=None if arguments.json else _local_result_notice,
                        web_src_file=None if arguments.no_web else config["web_src_file"],
                        on_web_fetch=None if arguments.json or arguments.no_web else _web_fetch_notice,
                        on_web_result=None if arguments.json or arguments.no_web else _web_result_notice,
                    )
                    _print({"database": str(profile.path), **result}, arguments.json)
            elif arguments.command == "search":
                hits = search_text(connection, arguments.query, arguments.k) if arguments.mode == "text" else search_vectors(connection, embed_texts(OLLAMA_CONFIG_PATH, validate_embedding_model(connection, config["embedding_model"]), [arguments.query])[0], arguments.k)
                _print_hits(hits, arguments.json)
            elif arguments.command == "context":
                hits = search_text(connection, arguments.query, arguments.k) if arguments.mode == "text" else search_vectors(connection, embed_texts(OLLAMA_CONFIG_PATH, validate_embedding_model(connection, config["embedding_model"]), [arguments.query])[0], arguments.k)
                project_directory = get_project_directory(PROJECT_DIR, load_project_config(PROJECT_DIR))
                output_path = _context_path(arguments.out, project_directory)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(_context_text(profile.name, arguments.query, hits, arguments.max_chars), encoding="utf-8")
                _print({"database": str(profile.path), "project_directory": str(project_directory), "mode": arguments.mode, "query": arguments.query, "chunks": len(hits), "context_file": str(output_path)}, arguments.json)
        finally:
            connection.close()
        return 0
    except (OllamaEmbeddingError, VectorError, sqlite3.Error, OSError) as error:
        print(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

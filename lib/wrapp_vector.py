"""Local SQLite, FTS5, and sqlite-vec storage for project RAG databases."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib.wrapp_web import WebFetchError, fetch_url_text, html_to_text

try:
    import sqlite_vec
except ImportError:  # pragma: no cover - exercised only in incomplete installs
    sqlite_vec = None


__version__ = "0.1"
SUPPORTED_SUFFIXES = {".md", ".pdf", ".txt"}
SCHEMA_VERSION = "1"
PROFILE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
WEB_SOURCE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
WEB_USER_AGENT = "ollama-api-rag/0.1 (+local knowledge-base ingest)"
WEB_TIMEOUT_SECONDS = 20


class VectorError(RuntimeError):
    """Raised for invalid vector configuration, content, or storage state."""


@dataclass(frozen=True)
class DatabaseProfile:
    """One named knowledge base selected from ``cli_vector.json``."""

    name: str
    path: Path
    source_group: str


@dataclass(frozen=True)
class Chunk:
    """One chunk ready to be embedded and stored."""

    text: str
    chunk_index: int
    char_start: int
    char_end: int
    page_number: int | None


@dataclass(frozen=True)
class SearchHit:
    """A retrieved chunk with source provenance."""

    chunk_id: int
    path: str
    page_number: int | None
    chunk_index: int
    text: str
    distance: float | None = None
    rank: float | None = None


@dataclass(frozen=True)
class WebSource:
    """One named HTTP(S) page declared in a source group's manifest."""

    name: str
    url: str


def _catalog_path(raw: dict[str, Any], project_root: Path) -> Path:
    """Resolve the externally stored database catalog inside the project."""

    catalog_setting = Path(raw["databases_config"])
    if catalog_setting.is_absolute():
        raise VectorError("databases_config must be relative to the project root.")
    catalog_path = (project_root / catalog_setting).resolve()
    try:
        catalog_path.relative_to(project_root.resolve())
    except ValueError as error:
        raise VectorError("databases_config must stay inside the project root.") from error
    return catalog_path


def _load_catalog(raw: dict[str, Any], project_root: Path) -> tuple[Path, dict[str, Any]]:
    """Return the catalog path and its validated JSON object."""

    catalog_path = _catalog_path(raw, project_root)
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VectorError(f"Cannot read database catalog {catalog_path}: {error}") from error
    if not isinstance(catalog, dict) or not isinstance(catalog.get("databases"), dict) or not catalog["databases"]:
        raise VectorError("Database catalog must contain a non-empty 'databases' JSON object.")
    return catalog_path, catalog


def load_config(path: Path, project_root: Path) -> tuple[dict[str, Any], dict[str, DatabaseProfile]]:
    """Load and validate the small, project-local vector configuration."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VectorError(f"Cannot read vector configuration {path}: {error}") from error
    if not isinstance(raw, dict):
        raise VectorError("Vector configuration must be a JSON object.")

    for key in ("source_root", "data_dir", "main_db", "embedding_model", "databases_config"):
        if key not in raw:
            raise VectorError(f"Vector configuration is missing {key!r}.")
    if not all(isinstance(raw[key], str) and raw[key] for key in ("source_root", "data_dir", "main_db", "embedding_model", "databases_config")):
        raise VectorError("source_root, data_dir, main_db, embedding_model, and databases_config must be non-empty text.")
    web_src_file = raw.get("web_src_file", "web_src.json")
    if not isinstance(web_src_file, str) or not web_src_file.strip():
        raise VectorError("web_src_file must be non-empty text when configured.")
    raw["web_src_file"] = web_src_file.strip()

    _, catalog = _load_catalog(raw, project_root)

    data_dir = (project_root / raw["data_dir"]).resolve()
    profiles: dict[str, DatabaseProfile] = {}
    for name, value in catalog["databases"].items():
        if not isinstance(name, str) or not name or not isinstance(value, dict):
            raise VectorError("Every database profile needs a non-empty name and an object value.")
        file_name = value.get("file")
        source_group = value.get("source_group")
        if not isinstance(file_name, str) or Path(file_name).name != file_name or not file_name.endswith(".db"):
            raise VectorError(f"Database {name!r} must specify a local .db file name.")
        if not isinstance(source_group, str) or not source_group:
            raise VectorError(f"Database {name!r} must specify source_group.")
        profiles[name] = DatabaseProfile(name, data_dir / file_name, source_group)
    if raw["main_db"] not in profiles:
        raise VectorError("main_db must name one entry in the database catalog.")
    return raw, profiles


def select_profile(profiles: dict[str, DatabaseProfile], selected: str | None, default: str) -> DatabaseProfile:
    """Select by profile name or configured database file name."""

    requested = selected or default
    if requested in profiles:
        return profiles[requested]
    for profile in profiles.values():
        if profile.path.name == requested or profile.path.stem == requested:
            return profile
    raise VectorError(f"Unknown database profile: {requested!r}.")


def set_main_db(config_path: Path, project_root: Path, selected: str) -> DatabaseProfile:
    """Persist one selected profile as ``main_db`` in the vector configuration."""

    raw, profiles = load_config(config_path, project_root)
    profile = select_profile(profiles, selected, raw["main_db"])
    raw["main_db"] = profile.name
    config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return profile


def new_database_profile(raw: dict[str, Any], project_root: Path, name: str) -> DatabaseProfile:
    """Build the conventional profile ``name -> wiki_name.db`` without writing it."""

    normalized = name.strip().casefold()
    if not PROFILE_NAME_PATTERN.fullmatch(normalized):
        raise VectorError("New wiki name must use lowercase letters, digits, and underscores, and start with a letter.")
    data_dir = (project_root / raw["data_dir"]).resolve()
    return DatabaseProfile(normalized, data_dir / f"wiki_{normalized}.db", normalized)


def register_database_profile(config_path: Path, project_root: Path, name: str) -> DatabaseProfile:
    """Add a finished conventional profile to the catalog and make it active."""

    raw, profiles = load_config(config_path, project_root)
    profile = new_database_profile(raw, project_root, name)
    if profile.name in profiles:
        raise VectorError(f"Database profile already exists: {profile.name!r}.")
    catalog_path, catalog = _load_catalog(raw, project_root)
    catalog["databases"][profile.name] = {"file": profile.path.name, "source_group": profile.source_group}
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raw["main_db"] = profile.name
    config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return profile


def open_database(path: Path) -> sqlite3.Connection:
    """Open a database and load the sqlite-vec extension into this connection."""

    if sqlite_vec is None:
        raise VectorError("sqlite-vec is not installed. Run: python -m pip install sqlite-vec")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
    except sqlite3.Error as error:
        connection.close()
        raise VectorError(f"Could not load sqlite-vec for {path}: {error}") from error
    finally:
        try:
            connection.enable_load_extension(False)
        except sqlite3.Error:
            pass
    ensure_schema(connection)
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Create relational and full-text tables; the vector dimension comes later."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS vector_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            relative_path TEXT NOT NULL UNIQUE,
            source_hash TEXT NOT NULL,
            source_group TEXT NOT NULL,
            source_type TEXT NOT NULL,
            indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            page_number INTEGER,
            UNIQUE(source_id, chunk_index)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content, content='chunks', content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS chunks_after_insert AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_after_delete AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_after_update AFTER UPDATE OF content ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES ('delete', old.id, old.content);
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END;
        """
    )
    if "index_config" not in {row[1] for row in connection.execute("PRAGMA table_info(sources)")}:
        connection.execute("ALTER TABLE sources ADD COLUMN index_config TEXT")
    _set_meta(connection, "schema_version", SCHEMA_VERSION)
    connection.commit()


def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO vector_meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _meta(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM vector_meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else None


def _has_vector_table(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chunk_vectors'"
    ).fetchone() is not None


def reset_database(connection: sqlite3.Connection) -> None:
    """Remove every indexed source and vector contract before a full rebuild."""

    with connection:
        if _has_vector_table(connection):
            connection.execute("DROP TABLE chunk_vectors")
        connection.execute("DELETE FROM sources")
        connection.execute(
            "DELETE FROM vector_meta WHERE key IN ('embedding_model', 'embedding_dimensions', 'embedding_status')"
        )
        _set_meta(connection, "schema_version", SCHEMA_VERSION)


def _ensure_vector_table(connection: sqlite3.Connection, dimensions: int, embedding_model: str) -> None:
    if dimensions <= 0:
        raise VectorError("Embedding dimension must be positive.")
    current_dimensions = _meta(connection, "embedding_dimensions")
    current_model = _meta(connection, "embedding_model")
    if current_dimensions is not None and int(current_dimensions) != dimensions:
        raise VectorError("Embedding dimension differs from the existing database; use a new database or reindex it.")
    if current_model is not None and current_model != embedding_model:
        raise VectorError("Embedding model differs from the existing database; use a new database or reindex it.")
    if current_dimensions is None:
        connection.execute(f"CREATE VIRTUAL TABLE chunk_vectors USING vec0(embedding float[{dimensions}])")
        _set_meta(connection, "embedding_dimensions", str(dimensions))
        _set_meta(connection, "embedding_model", embedding_model)


def source_files(source_root: Path, source_group: str) -> list[Path]:
    """Return supported source files from one configured source group."""

    group_path = source_root / source_group
    if not group_path.is_dir():
        raise VectorError(f"Configured source group does not exist: {group_path}")
    return sorted(path for path in group_path.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES)


def web_sources(source_root: Path, source_group: str, manifest_name: str) -> list[WebSource]:
    """Read the optional named HTTP(S) source manifest for one wiki group."""

    candidate = Path(manifest_name)
    if candidate.is_absolute() or candidate.parent != Path(".") or candidate.suffix.casefold() != ".json":
        raise VectorError("web_src_file must name a .json file directly inside each source group.")
    manifest_path = source_root / source_group / candidate
    if not manifest_path.exists():
        return []
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise VectorError(f"Cannot read web source manifest {manifest_path}: {error}") from error
    if not isinstance(raw, dict):
        raise VectorError(f"Web source manifest {manifest_path} must be a JSON object of name-to-URL entries.")
    sources: list[WebSource] = []
    for name, url in raw.items():
        if not isinstance(name, str) or not WEB_SOURCE_NAME_PATTERN.fullmatch(name):
            raise VectorError(f"Web source name {name!r} must use lowercase letters, digits, and underscores.")
        if not isinstance(url, str) or not url.strip() or not re.fullmatch(r"https?://\S+", url):
            raise VectorError(f"Web source {name!r} must contain an absolute http(s) URL.")
        sources.append(WebSource(name, url.strip()))
    return sources


def _web_source_text(source: WebSource) -> str:
    """Fetch and turn one declared HTML page into clean, attributable body text."""

    try:
        document = fetch_url_text(
            source.url,
            timeout_seconds=WEB_TIMEOUT_SECONDS,
            user_agent=WEB_USER_AGENT,
        )
        visible_text = html_to_text(document)
    except WebFetchError as error:
        raise VectorError(str(error)) from error
    if not visible_text:
        raise VectorError("page did not contain visible text")
    # Name and URL are already retained in ``sources.relative_path`` and shown
    # with every retrieval result.  Do not include them in the embedding: URLs
    # and repeated site names otherwise make boilerplate chunks rank too well.
    return visible_text


def _fragments(path: Path) -> Iterable[tuple[str, int | None]]:
    if path.suffix.casefold() != ".pdf":
        yield path.read_text(encoding="utf-8-sig", errors="replace"), None
        return

    # ``pdfminer.six`` was used by the older PDF utility in ``inspirace_pdf``.
    # Its layout parser is often more reliable than pypdf for documents with
    # embedded fonts and ligatures.  Keep pypdf as a functional fallback for
    # existing installations until the optional dependency is installed.
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer, LAParams
    except ImportError:
        yield from _pypdf_fragments(path)
        return
    try:
        layout_parameters = LAParams(
            char_margin=3.0,
            line_margin=0.5,
            word_margin=0.1,
            all_texts=True,
        )
        for index, page_layout in enumerate(extract_pages(str(path), laparams=layout_parameters), start=1):
            text = "".join(
                element.get_text()
                for element in page_layout
                if isinstance(element, LTTextContainer)
            )
            yield _normalise_pdf_text(text), index
    except Exception as error:
        raise VectorError(f"Could not extract text from PDF {path}: {error}") from error


def _pypdf_fragments(path: Path) -> Iterable[tuple[str, int | None]]:
    """Extract a PDF with the lightweight fallback already used by the CLI."""

    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover - dependency error is user-facing
        raise VectorError("PDF ingestion requires pypdf or pdfminer.six. Run: python -m pip install pypdf") from error
    try:
        reader = PdfReader(str(path))
        for index, page in enumerate(reader.pages, start=1):
            yield _normalise_pdf_text(page.extract_text() or ""), index
    except Exception as error:
        raise VectorError(f"Could not extract text from PDF {path}: {error}") from error


def _normalise_pdf_text(text: str) -> str:
    """Repair common PDF text artefacts before chunking and embedding.

    The transformations intentionally mirror the proven converter in
    ``inspirace_pdf``: normalize ligatures, remove soft hyphens and join words
    split by a line-ending hyphen.  We do not guess at ordinary spaces, because
    aggressive repairs can merge two genuinely separate Czech words.
    """

    # Some PDF font encodings put a real space immediately before a ligature.
    # Repair it *before* NFKC expands ``ﬁ`` to ``fi`` so ordinary words such as
    # "a fikce" are never accidentally merged.
    for ligature, replacement in (("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff")):
        text = re.sub(
            rf"(\w{{3,}})\s+{ligature}(?=\w)",
            lambda match: f"{match.group(1)}{replacement}",
            text,
        )
    normalized = unicodedata.normalize("NFKC", text)
    replacements = {
        "\x00": "",
        "\x04": "fi",
        "\x05": "fl",
        "\x0b": "ff",
        "\x0c": "fi",
        "\u00ad": "",
        "\u00a0": " ",
    }
    for bad, good in replacements.items():
        normalized = normalized.replace(bad, good)
    normalized = re.sub(r"(\w+)(?:-|\u00ad)\s*\n\s*(\w+)", r"\1\2", normalized)
    return re.sub(r"\n{3,}", "\n\n", normalized)


def chunk_file(path: Path, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Split one source by page and paragraph-friendly character windows."""

    return _chunk_fragments(_fragments(path), chunk_size, chunk_overlap)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Split one virtual plain-text source, such as a fetched web page."""

    return _chunk_fragments(((text, None),), chunk_size, chunk_overlap)


def _chunk_character_count(chunks: list[Chunk]) -> int:
    """Return extracted source characters once, without counting chunk overlap."""

    page_ends: dict[int | None, int] = {}
    for chunk in chunks:
        page_ends[chunk.page_number] = max(page_ends.get(chunk.page_number, 0), chunk.char_end)
    return sum(page_ends.values())


def _chunk_fragments(
    fragments: Iterable[tuple[str, int | None]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Split text fragments by page and paragraph-friendly character windows."""

    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise VectorError("chunk_size must be positive and chunk_overlap must be smaller than chunk_size.")
    chunks: list[Chunk] = []
    for text, page_number in fragments:
        normalized = text.strip()
        start = 0
        while start < len(normalized):
            end = min(start + chunk_size, len(normalized))
            if end < len(normalized):
                boundary = max(normalized.rfind("\n\n", start + 1, end), normalized.rfind("\n", start + 1, end))
                if boundary > start + chunk_size // 2:
                    end = boundary
            content = normalized[start:end].strip()
            if content:
                chunks.append(Chunk(content, len(chunks), start, end, page_number))
            if end == len(normalized):
                break
            start = max(end - chunk_overlap, start + 1)
    return chunks


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_embedding_status(connection: sqlite3.Connection) -> None:
    has_vectors = _has_vector_table(connection)
    sql = "SELECT count(*) FROM chunks"
    if has_vectors:
        sql += " WHERE id NOT IN (SELECT rowid FROM chunk_vectors)"
    missing = connection.execute(sql).fetchone()[0]
    _set_meta(connection, "embedding_status", "pending" if missing or not has_vectors else "indexed")


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest(
    connection: sqlite3.Connection,
    source_root: Path,
    source_group: str,
    embedding_model: str,
    embed: Callable[[list[str]], list[list[float]]] | None,
    *,
    chunk_size: int,
    chunk_overlap: int,
    reindex: bool = False,
    prune: bool = False,
    overwrite: bool = False,
    on_embedding_start: Callable[[str, int], None] | None = None,
    on_local_result: Callable[[str, str], None] | None = None,
    web_src_file: str | None = None,
    on_web_fetch: Callable[[WebSource], None] | None = None,
    on_web_result: Callable[[WebSource, str], None] | None = None,
) -> dict[str, int]:
    """Embed changed local files and optional sequential web pages in one group."""

    if overwrite:
        if connection.in_transaction:
            raise VectorError("Commit or roll back the active transaction before rebuilding.")
        # Build and validate independently. SQLite backup publishes the complete
        # database in a destination transaction, preserving it on build failure.
        with tempfile.TemporaryDirectory(prefix="rag-rebuild-") as directory:
            staged = open_database(Path(directory) / "index.db")
            try:
                result = ingest(
                    staged, source_root, source_group, embedding_model, embed,
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                    on_embedding_start=on_embedding_start, on_local_result=on_local_result,
                    web_src_file=web_src_file, on_web_fetch=on_web_fetch, on_web_result=on_web_result,
                )
                problems = verify(staged)
                if result["web_failed"] or problems:
                    raise VectorError(f"Rebuild not published: web failures={result['web_failed']}; {problems}")
                staged.backup(connection)
                return result
            finally:
                staged.close()

    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise VectorError("chunk_size must be positive and chunk_overlap must be smaller than chunk_size.")
    if embed is not None and _meta(connection, "embedding_model") is not None:
        validate_embedding_model(connection, embedding_model)
    index_config = json.dumps([1, chunk_size, chunk_overlap])
    seen: set[str] = set()
    backfill: set[str] = set()
    counts = {"local_files": 0, "web_pages": 0, "web_failed": 0, "chunks": 0, "skipped": 0, "removed": 0}

    def unchanged(existing: sqlite3.Row | None, checksum: str) -> bool:
        return bool(existing and existing["source_hash"] == checksum
                    and existing["index_config"] == index_config and not reindex)

    def missing_chunks(source_id: int) -> list[Chunk]:
        condition = "AND id NOT IN (SELECT rowid FROM chunk_vectors)" if _has_vector_table(connection) else ""
        return [Chunk(row["content"], row["chunk_index"], row["char_start"], row["char_end"], row["page_number"])
                for row in connection.execute(f"SELECT * FROM chunks WHERE source_id = ? {condition} ORDER BY chunk_index", (source_id,))]

    prepared: list[tuple[str, str, str, sqlite3.Row | None, list[Chunk]]] = []
    for path in source_files(source_root, source_group):
        relative_path = path.relative_to(source_root).as_posix()
        seen.add(relative_path)
        checksum = _source_hash(path)
        existing = connection.execute("SELECT * FROM sources WHERE relative_path = ?", (relative_path,)).fetchone()
        pending = missing_chunks(existing["id"]) if unchanged(existing, checksum) and embed is not None else []
        if unchanged(existing, checksum) and not pending:
            counts["skipped"] += 1
            if on_local_result is not None:
                on_local_result(relative_path, "unchanged; skipped")
            continue
        chunks = pending if pending else chunk_file(path, chunk_size, chunk_overlap)
        if pending:
            backfill.add(relative_path)
        if not chunks and not existing:
            counts["skipped"] += 1
            if on_local_result is not None:
                on_local_result(relative_path, "no text; skipped")
            continue
        prepared.append((relative_path, checksum, path.suffix.casefold().lstrip("."), existing, chunks))
        if on_local_result is not None:
            on_local_result(relative_path, f"loaded {_chunk_character_count(chunks):,} characters")

    if web_src_file is not None:
        for source in web_sources(source_root, source_group, web_src_file):
            relative_path = f"{source_group}/web/{source.name} ({source.url})"
            seen.add(relative_path)  # A fetch failure must never prune the old page.
            if on_web_fetch is not None:
                on_web_fetch(source)
            try:
                text = _web_source_text(source)
            except VectorError as error:
                counts["web_failed"] += 1
                if on_web_result is not None:
                    on_web_result(source, f"failed: {error}")
                continue
            checksum = _text_hash(text)
            existing = connection.execute("SELECT * FROM sources WHERE relative_path = ?", (relative_path,)).fetchone()
            pending = missing_chunks(existing["id"]) if unchanged(existing, checksum) and embed is not None else []
            if unchanged(existing, checksum) and not pending:
                counts["skipped"] += 1
                if on_web_result is not None:
                    on_web_result(source, "unchanged; skipped")
                continue
            chunks = pending if pending else chunk_text(text, chunk_size, chunk_overlap)
            if pending:
                backfill.add(relative_path)
            if not chunks and not existing:
                counts["skipped"] += 1
                if on_web_result is not None:
                    on_web_result(source, "no text; skipped")
                continue
            prepared.append((relative_path, checksum, "web", existing, chunks))
            counts["web_pages"] += 1
            if on_web_result is not None:
                on_web_result(source, f"loaded {len(text):,} characters")

    if embed is not None and on_embedding_start is not None and prepared:
        on_embedding_start(source_group, sum(len(chunks) for _relative_path, _checksum, _source_type, _existing, chunks in prepared))

    for relative_path, checksum, source_type, existing, chunks in prepared:
        embeddings: list[list[float]] | None = None
        if embed is not None and chunks:
            embeddings = embed([chunk.text for chunk in chunks])
            if len(embeddings) != len(chunks) or not embeddings or not isinstance(embeddings[0], list):
                raise VectorError(f"Embedding provider returned invalid results for {relative_path}.")
            dimensions = len(embeddings[0])
            if any(len(vector) != dimensions for vector in embeddings):
                raise VectorError(f"Embedding provider returned inconsistent dimensions for {relative_path}.")
        with connection:
            if embeddings is not None:
                _ensure_vector_table(connection, dimensions, embedding_model)
            if relative_path in backfill:
                assert embeddings is not None and existing is not None
                for chunk, vector in zip(chunks, embeddings):
                    chunk_id = connection.execute("SELECT id FROM chunks WHERE source_id = ? AND chunk_index = ?", (existing["id"], chunk.chunk_index)).fetchone()[0]
                    connection.execute("INSERT INTO chunk_vectors(rowid, embedding) VALUES (?, ?)", (chunk_id, sqlite_vec.serialize_float32(vector)))
                _refresh_embedding_status(connection)
                counts["chunks"] += len(chunks)
                if source_type != "web":
                    counts["local_files"] += 1
                continue
            if existing:
                source_id = int(existing["id"])
                if _has_vector_table(connection):
                    connection.execute("DELETE FROM chunk_vectors WHERE rowid IN (SELECT id FROM chunks WHERE source_id = ?)", (source_id,))
                connection.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
                connection.execute(
                    "UPDATE sources SET source_hash = ?, source_group = ?, source_type = ?, indexed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (checksum, source_group, source_type, source_id),
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO sources(relative_path, source_hash, source_group, source_type) VALUES (?, ?, ?, ?)",
                    (relative_path, checksum, source_group, source_type),
                )
                source_id = int(cursor.lastrowid)
            connection.execute("UPDATE sources SET index_config = ? WHERE id = ?", (index_config, source_id))
            for chunk_index, chunk in enumerate(chunks):
                cursor = connection.execute(
                    "INSERT INTO chunks(source_id, chunk_index, content, char_start, char_end, page_number) VALUES (?, ?, ?, ?, ?, ?)",
                    (source_id, chunk.chunk_index, chunk.text, chunk.char_start, chunk.char_end, chunk.page_number),
                )
                if embeddings is not None:
                    connection.execute(
                        "INSERT INTO chunk_vectors(rowid, embedding) VALUES (?, ?)",
                        (int(cursor.lastrowid), sqlite_vec.serialize_float32(embeddings[chunk_index])),
                    )
            _refresh_embedding_status(connection)
        if source_type != "web":
            counts["local_files"] += 1
        counts["chunks"] += len(chunks)
    with connection:
        if prune:
            for row in connection.execute("SELECT id, relative_path, source_type FROM sources WHERE source_group = ?", (source_group,)).fetchall():
                if row["relative_path"] in seen or (row["source_type"] == "web" and web_src_file is None):
                    continue
                if _has_vector_table(connection):
                    connection.execute("DELETE FROM chunk_vectors WHERE rowid IN (SELECT id FROM chunks WHERE source_id = ?)", (row["id"],))
                connection.execute("DELETE FROM sources WHERE id = ?", (row["id"],))
                counts["removed"] += 1
        _refresh_embedding_status(connection)
    return counts


def validate_embedding_model(connection: sqlite3.Connection, model: str) -> str:
    """Reject queries from an incompatible embedding space before contacting Ollama."""
    stored = _meta(connection, "embedding_model")
    if stored is None:
        raise VectorError("Database has no embeddings; run ingest with embeddings first.")
    if stored != model:
        raise VectorError(f"Embedding model mismatch: database uses {stored!r}, configuration uses {model!r}. Use the stored model or --overwrite to rebuild.")
    return stored


def search_vectors(connection: sqlite3.Connection, query_embedding: list[float], limit: int) -> list[SearchHit]:
    """Return nearest chunks, with the source fields needed for citation."""

    if limit <= 0:
        raise VectorError("Search limit must be positive.")
    if _meta(connection, "embedding_dimensions") is None:
        return []
    rows = connection.execute(
        """
        SELECT chunks.id, sources.relative_path, chunks.page_number, chunks.chunk_index,
               chunks.content, chunk_vectors.distance
        FROM chunk_vectors
        JOIN chunks ON chunks.id = chunk_vectors.rowid
        JOIN sources ON sources.id = chunks.source_id
        WHERE chunk_vectors.embedding MATCH ? AND k = ?
        ORDER BY chunk_vectors.distance
        """,
        (sqlite_vec.serialize_float32(query_embedding), limit),
    ).fetchall()
    return [SearchHit(int(row["id"]), row["relative_path"], row["page_number"], int(row["chunk_index"]), row["content"], float(row["distance"])) for row in rows]


def search_text(connection: sqlite3.Connection, query: str, limit: int) -> list[SearchHit]:
    """Return FTS5 matches without contacting an embedding model."""

    if limit <= 0:
        raise VectorError("Search limit must be positive.")
    rows = connection.execute(
        """
        SELECT chunks.id, sources.relative_path, chunks.page_number, chunks.chunk_index,
               chunks.content, bm25(chunks_fts) AS rank
        FROM chunks_fts
        JOIN chunks ON chunks.id = chunks_fts.rowid
        JOIN sources ON sources.id = chunks.source_id
        WHERE chunks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    return [SearchHit(int(row["id"]), row["relative_path"], row["page_number"], int(row["chunk_index"]), row["content"], rank=float(row["rank"])) for row in rows]


def inspect(connection: sqlite3.Connection) -> dict[str, object]:
    """Return compact, serializable database statistics."""

    return {
        "sources": int(connection.execute("SELECT count(*) FROM sources").fetchone()[0]),
        "chunks": int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0]),
        "embedding_model": _meta(connection, "embedding_model"),
        "embedding_dimensions": _meta(connection, "embedding_dimensions"),
        "embedding_status": _meta(connection, "embedding_status") or "pending",
        "schema_version": _meta(connection, "schema_version"),
    }


def verify(connection: sqlite3.Connection) -> list[str]:
    """Return invariant failures; an empty list means the storage is consistent."""

    problems: list[str] = []
    vector_table = _has_vector_table(connection)
    chunk_count = int(connection.execute("SELECT count(*) FROM chunks").fetchone()[0])
    if chunk_count and not vector_table and _meta(connection, "embedding_status") != "pending":
        problems.append("Chunks exist but the vector table is missing.")
    if vector_table:
        vector_count = int(connection.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0])
        if vector_count != chunk_count:
            problems.append(f"Chunk/vector count differs: {chunk_count}/{vector_count}.")
    if _meta(connection, "schema_version") != SCHEMA_VERSION:
        problems.append("Unexpected schema version.")
    return problems

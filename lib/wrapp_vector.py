"""Local SQLite, FTS5, and sqlite-vec storage for project RAG databases."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import sqlite_vec
except ImportError:  # pragma: no cover - exercised only in incomplete installs
    sqlite_vec = None


__version__ = "0.1"
SUPPORTED_SUFFIXES = {".md", ".pdf", ".txt"}
SCHEMA_VERSION = "1"
PROFILE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


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
    _set_meta(connection, "embedding_status", "indexed")


def source_files(source_root: Path, source_group: str) -> list[Path]:
    """Return supported source files from one configured source group."""

    group_path = source_root / source_group
    if not group_path.is_dir():
        raise VectorError(f"Configured source group does not exist: {group_path}")
    return sorted(path for path in group_path.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES)


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

    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise VectorError("chunk_size must be positive and chunk_overlap must be smaller than chunk_size.")
    chunks: list[Chunk] = []
    for text, page_number in _fragments(path):
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
    on_embedding_start: Callable[[str, int], None] | None = None,
) -> dict[str, int]:
    """Embed changed files in one source group and upsert their chunks."""

    counts = {"files": 0, "chunks": 0, "skipped": 0}
    prepared: list[tuple[Path, str, str, sqlite3.Row | None, list[Chunk]]] = []
    for path in source_files(source_root, source_group):
        relative_path = path.relative_to(source_root).as_posix()
        checksum = _source_hash(path)
        existing = connection.execute("SELECT id, source_hash FROM sources WHERE relative_path = ?", (relative_path,)).fetchone()
        if existing and existing["source_hash"] == checksum and not reindex:
            counts["skipped"] += 1
            continue
        chunks = chunk_file(path, chunk_size, chunk_overlap)
        if not chunks:
            counts["skipped"] += 1
            continue
        prepared.append((path, relative_path, checksum, existing, chunks))

    if embed is not None and on_embedding_start is not None and prepared:
        on_embedding_start(source_group, sum(len(chunks) for _path, _relative_path, _checksum, _existing, chunks in prepared))

    for path, relative_path, checksum, existing, chunks in prepared:
        embeddings: list[list[float]] | None = None
        if embed is not None:
            embeddings = embed([chunk.text for chunk in chunks])
            if len(embeddings) != len(chunks) or not embeddings or not isinstance(embeddings[0], list):
                raise VectorError(f"Embedding provider returned invalid results for {relative_path}.")
            dimensions = len(embeddings[0])
            if any(len(vector) != dimensions for vector in embeddings):
                raise VectorError(f"Embedding provider returned inconsistent dimensions for {relative_path}.")
            _ensure_vector_table(connection, dimensions, embedding_model)
        with connection:
            if existing:
                source_id = int(existing["id"])
                if _has_vector_table(connection):
                    connection.execute("DELETE FROM chunk_vectors WHERE rowid IN (SELECT id FROM chunks WHERE source_id = ?)", (source_id,))
                connection.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
                connection.execute(
                    "UPDATE sources SET source_hash = ?, source_group = ?, source_type = ?, indexed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (checksum, source_group, path.suffix.casefold().lstrip("."), source_id),
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO sources(relative_path, source_hash, source_group, source_type) VALUES (?, ?, ?, ?)",
                    (relative_path, checksum, source_group, path.suffix.casefold().lstrip(".")),
                )
                source_id = int(cursor.lastrowid)
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
            if embeddings is None:
                _set_meta(connection, "embedding_status", "pending")
        counts["files"] += 1
        counts["chunks"] += len(chunks)
    return counts


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

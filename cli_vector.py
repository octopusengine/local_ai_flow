"""Create and query named local RAG databases backed by SQLite and sqlite-vec."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Sequence
from html import escape as html_escape
from pathlib import Path

from lib.wrapp_ollama import OllamaEmbeddingError, embed_texts
from lib.wrapp_log import get_project_directory, load_project_config
from lib.wrapp_vector import (
    VectorError, chunk_file, ingest, inspect, load_config, new_database_profile,
    open_database, register_database_profile, search_text, search_vectors,
    reset_database, select_profile, set_main_db, source_files, verify, web_sources,
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
    ingest_parser.add_argument("--chunk-overlap", type=positive_integer, help="override configured overlap in characters")
    ingest_parser.add_argument("--dry-run", action="store_true", help="list selected files without writing or contacting Ollama")
    ingest_parser.add_argument("--no-embed", action="store_true", help="store sources and FTS chunks only; defer Ollama embeddings")
    ingest_parser.add_argument("--no-web", action="store_true", help="ignore the optional web_src.json manifest in the selected source group")
    ingest_parser.add_argument("--reindex", action="store_true", help="replace chunks even if their source hash is unchanged")
    ingest_parser.add_argument("--overwrite", action="store_true", help="delete every indexed source in the selected database, then rebuild it")
    ingest_parser.add_argument("--embedding-batch-size", type=positive_integer, help="chunks per Ollama embedding request (default: embedding_batch_size in config)")

    new_wiki_parser = commands.add_parser("ingest-wiki", help="create and fill a new named wiki from rag_wiki/src/NAME")
    new_wiki_parser.add_argument("name", help="new wiki/source-group name, for example: bitcoin")
    new_wiki_parser.add_argument("--chunk-size", type=positive_integer, help="override configured chunk size in characters")
    new_wiki_parser.add_argument("--chunk-overlap", type=positive_integer, help="override configured overlap in characters")
    new_wiki_parser.add_argument("--embed", action="store_true", help="create vector embeddings immediately with the configured Ollama model")
    new_wiki_parser.add_argument("--no-web", action="store_true", help="ignore the optional web_src.json manifest in the new source group")
    new_wiki_parser.add_argument("--embedding-batch-size", type=positive_integer, help="chunks per Ollama embedding request (default: embedding_batch_size in config)")
    new_wiki_parser.add_argument("--reindex", action="store_true", help="replace chunks for every source when the wiki profile already exists")
    new_wiki_parser.add_argument("--overwrite", action="store_true", help="delete every indexed source in the wiki database, then rebuild it")

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


def _svg_query_terms(query: str) -> list[str]:
    """Extract every distinct word from an external SVG diagnostic prompt."""

    terms: list[str] = []
    seen: set[str] = set()
    for word in re.findall(r"[^\W_]+", query, re.UNICODE):
        normalized = word.casefold()
        if len(word) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(word)
    return terms or [query.strip()]


def _svg_query_groups(query: str) -> list[str]:
    """Return multi-word comma groups that deserve their own semantic nodes."""

    groups: list[str] = []
    seen: set[str] = set()
    for field in query.split(","):
        group = field.strip().removeprefix("#").strip().strip("() ")
        normalized = group.casefold()
        if len(_svg_query_terms(group)) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        groups.append(group)
    return groups


def _svg_path(path: Path, project_directory: Path) -> Path:
    """Resolve an SVG diagnostic file inside the active project directory."""

    resolved = (project_directory / path).resolve()
    try:
        resolved.relative_to(project_directory.resolve())
    except ValueError as error:
        raise VectorError("--svg-out must point inside the active project directory") from error
    return resolved


def _rag_svg_distances(
    connection: object,
    chunk_ids: list[int],
    labels: list[str],
    embeddings: list[list[float]],
) -> dict[int, dict[str, float]]:
    """Return individual labelled-vector distances for the external map."""

    if not chunk_ids:
        return {}
    try:
        import sqlite_vec
    except ImportError as error:  # pragma: no cover - guarded by open_database normally
        raise VectorError("sqlite-vec is not installed.") from error
    placeholders = ", ".join("?" for _chunk_id in chunk_ids)
    result = {chunk_id: {} for chunk_id in chunk_ids}
    for label, embedding in zip(labels, embeddings):
        rows = connection.execute(
            f"SELECT rowid, vec_distance_l2(embedding, ?) AS distance FROM chunk_vectors WHERE rowid IN ({placeholders})",
            (sqlite_vec.serialize_float32(embedding), *chunk_ids),
        ).fetchall()
        for row in rows:
            result[int(row["rowid"])][label] = float(row["distance"])
    return result


def _rag_svg_confidence(connection: object, query_embedding: list[float], hits: list[object]) -> dict[str, float | int] | None:
    """Measure the first retrieval result against every vector in this wiki."""

    if not hits or hits[0].distance is None:
        return None
    try:
        import sqlite_vec
    except ImportError as error:  # pragma: no cover - guarded by open_database normally
        raise VectorError("sqlite-vec is not installed.") from error
    rows = connection.execute(
        "SELECT vec_distance_l2(embedding, ?) AS distance FROM chunk_vectors",
        (sqlite_vec.serialize_float32(query_embedding),),
    ).fetchall()
    all_distances = sorted(float(row["distance"]) for row in rows)
    if not all_distances:
        return None
    first_distance = float(hits[0].distance)
    rank = next((index for index, value in enumerate(all_distances, start=1) if value >= first_distance - 1e-6), len(all_distances))
    gap = None if len(hits) < 2 or hits[1].distance is None else float(hits[1].distance) - first_distance
    result: dict[str, float | int] = {"rank": rank, "total": len(all_distances), "top_percent": rank * 100 / len(all_distances)}
    if gap is not None:
        result["gap"] = gap
    return result


def _rag_svg_layout(
    nodes: list[str],
    hits: list[object],
    distances: dict[int, dict[str, float]],
    width: int,
    height: int,
    *,
    outside_nodes: set[str] | None = None,
) -> tuple[dict[str, tuple[float, float]], dict[int, tuple[float, float]], float, float, dict[str, float]]:
    """Use a constrained 2D stress layout for node-to-chunk vector distances."""

    import math

    centre_x, centre_y = width * 0.45, height * 0.54
    radius_x, radius_y = 220.0, min(250.0, height * 0.30)
    node_positions = {
        node: (
            centre_x + radius_x * math.cos(-math.pi / 2 + index * 2 * math.pi / max(len(nodes), 1)),
            centre_y + radius_y * math.sin(-math.pi / 2 + index * 2 * math.pi / max(len(nodes), 1)),
        )
        for index, node in enumerate(nodes)
    }
    values = [distance for by_term in distances.values() for distance in by_term.values()]
    smallest, largest = (min(values), max(values)) if values else (0.0, 1.0)

    def desired_length(value: float) -> float:
        ratio = 0.5 if largest == smallest else (value - smallest) / (largest - smallest)
        return 110.0 + ratio * 270.0

    mobile_nodes = {node: [*position] for node, position in node_positions.items()}
    chunk_positions: dict[int, list[float]] = {}
    for index, hit in enumerate(hits):
        weighted_positions = [
            (mobile_nodes[node], 1.0 / max(distances.get(hit.chunk_id, {}).get(node, largest), 0.01))
            for node in nodes
        ]
        total_weight = sum(weight for _position, weight in weighted_positions) or 1.0
        x = sum(position[0] * weight for position, weight in weighted_positions) / total_weight
        y = sum(position[1] * weight for position, weight in weighted_positions) / total_weight
        angle = index * 2 * math.pi / max(len(hits), 1)
        chunk_positions[hit.chunk_id] = [x + 130 * math.cos(angle), y + 130 * math.sin(angle)]

    node_radius = {node: 82.0 if " " in node else 46.0 for node in nodes}
    chunk_radius = 25.0
    outside_nodes = outside_nodes or set()
    # Both sides of every edge move. This approximates the transformed L2
    # lengths far better than fixing the query words at decorative positions.
    for _step in range(900):
        node_changes = {node: [0.0, 0.0] for node in mobile_nodes}
        chunk_changes = {chunk_id: [0.0, 0.0] for chunk_id in chunk_positions}
        for hit in hits:
            chunk_position = chunk_positions[hit.chunk_id]
            for node, node_position in mobile_nodes.items():
                value = distances.get(hit.chunk_id, {}).get(node)
                if value is None:
                    continue
                dx, dy = node_position[0] - chunk_position[0], node_position[1] - chunk_position[1]
                current = max(math.hypot(dx, dy), 0.001)
                pull = (current - desired_length(value)) * 0.028
                node_changes[node][0] -= dx / current * pull
                node_changes[node][1] -= dy / current * pull
                chunk_changes[hit.chunk_id][0] += dx / current * pull
                chunk_changes[hit.chunk_id][1] += dy / current * pull
        entities: list[tuple[str, str | int, list[float], float]] = [
            ("node", node, position, node_radius[node]) for node, position in mobile_nodes.items()
        ] + [
            ("chunk", chunk_id, position, chunk_radius) for chunk_id, position in chunk_positions.items()
        ]
        for left_index, (left_kind, left_key, left_position, left_radius) in enumerate(entities):
            for right_kind, right_key, right_position, right_radius in entities[left_index + 1:]:
                dx, dy = left_position[0] - right_position[0], left_position[1] - right_position[1]
                current = max(math.hypot(dx, dy), 0.001)
                clearance = left_radius + right_radius + 16.0
                if current >= clearance:
                    continue
                # Collision avoidance has priority over a perfect edge fit.
                # A map with a slightly longer line is still readable; two
                # overlapping numbered chunks are not.
                push = (clearance - current) * 0.32
                left_changes = node_changes if left_kind == "node" else chunk_changes
                right_changes = node_changes if right_kind == "node" else chunk_changes
                left_changes[left_key][0] += dx / current * push
                left_changes[left_key][1] += dy / current * push
                right_changes[right_key][0] -= dx / current * push
                right_changes[right_key][1] -= dy / current * push
        for node, change in node_changes.items():
            position = mobile_nodes[node]
            change_length = max(math.hypot(*change), 1.0)
            scale = min(1.0, 12.0 / change_length)
            radius = node_radius[node]
            position[0] = min(width - radius - 25, max(radius + 25, position[0] + change[0] * scale))
            position[1] = min(height - radius - 30, max(radius + 115, position[1] + change[1] * scale))
        for chunk_id, change in chunk_changes.items():
            position = chunk_positions[chunk_id]
            change_length = max(math.hypot(*change), 1.0)
            scale = min(1.0, 12.0 / change_length)
            position[0] = min(width - chunk_radius - 25, max(chunk_radius + 25, position[0] + change[0] * scale))
            position[1] = min(height - chunk_radius - 30, max(chunk_radius + 115, position[1] + change[1] * scale))
    # Create a relevance boundary around the retained semantic core. Distant
    # query groups are moved outside it before the final collision pass.
    core_positions = [
        position for node, position in mobile_nodes.items() if node not in outside_nodes
    ] + list(chunk_positions.values())
    centre_x = sum(position[0] for position in core_positions) / len(core_positions)
    centre_y = sum(position[1] for position in core_positions) / len(core_positions)
    boundary_radius = max(math.hypot(position[0] - centre_x, position[1] - centre_y) for position in core_positions) + 20.0
    for index, node in enumerate(sorted(outside_nodes)):
        if node not in mobile_nodes:
            continue
        position = mobile_nodes[node]
        dx, dy = position[0] - centre_x, position[1] - centre_y
        current = math.hypot(dx, dy)
        if current < 0.001:
            angle = index * 2 * math.pi / max(len(outside_nodes), 1)
            dx, dy, current = math.cos(angle), math.sin(angle), 1.0
        minimum = boundary_radius + node_radius[node] + 18.0
        if current < minimum:
            position[0] = centre_x + dx / current * minimum
            position[1] = centre_y + dy / current * minimum
    # Finish with a hard, geometry-only separation pass. It accepts a small
    # stress error in exchange for never drawing two nodes on top of each other.
    for _step in range(120):
        moved = False
        entities = [
            ("node", node, position, node_radius[node]) for node, position in mobile_nodes.items()
        ] + [
            ("chunk", chunk_id, position, chunk_radius) for chunk_id, position in chunk_positions.items()
        ]
        for left_index, (left_kind, _left_key, left_position, left_radius) in enumerate(entities):
            for right_kind, _right_key, right_position, right_radius in entities[left_index + 1:]:
                dx, dy = left_position[0] - right_position[0], left_position[1] - right_position[1]
                current = max(math.hypot(dx, dy), 0.001)
                clearance = left_radius + right_radius + 16.0
                if current >= clearance - 0.2:
                    continue
                push = (clearance - current) / 2
                left_position[0] += dx / current * push
                left_position[1] += dy / current * push
                right_position[0] -= dx / current * push
                right_position[1] -= dy / current * push
                moved = True
        if not moved:
            break
    errors = [
        abs(math.dist(mobile_nodes[node], chunk_positions[hit.chunk_id]) - desired_length(value))
        for hit in hits for node, value in distances.get(hit.chunk_id, {}).items()
        if node in mobile_nodes
    ]
    fit = {
        "mean_absolute_error": sum(errors) / len(errors) if errors else 0.0,
        "rms_error": math.sqrt(sum(error * error for error in errors) / len(errors)) if errors else 0.0,
        "target_min": desired_length(smallest),
        "target_max": desired_length(largest),
        "boundary_x": centre_x,
        "boundary_y": centre_y,
        "boundary_radius": boundary_radius,
    }
    return ({node: tuple(position) for node, position in mobile_nodes.items()}, {chunk_id: tuple(position) for chunk_id, position in chunk_positions.items()}, smallest, largest, fit)


def _rag_svg_distant_nodes(
    words: list[str],
    groups: list[str],
    hits: list[object],
    distances: dict[int, dict[str, float]],
) -> tuple[set[str], set[str]]:
    """Mark every clearly distant comma group and its words, falling back to words."""

    if not hits:
        return set(), set()

    def averages(labels: list[str]) -> dict[str, float]:
        return {
            label: sum(distances.get(hit.chunk_id, {}).get(label, 0.0) for hit in hits) / len(hits)
            for label in labels
        }

    def distant_labels(labels: list[str]) -> set[str]:
        scores = averages(labels)
        closest, furthest = min(scores.values()), max(scores.values())
        # Do not force a grey outlier. A label must be materially farther than
        # the best group, and several labels may cross the same cutoff.
        cutoff = closest + max(0.045, (furthest - closest) * 0.65)
        return {label for label, score in scores.items() if score >= cutoff and score > closest}

    if groups:
        distant_groups = distant_labels(groups)
        distant_words = {
            word for group in distant_groups for word in _svg_query_terms(group)
            if word in words
        }
        return distant_words, distant_groups
    if len(words) < 3:
        return set(), set()
    return distant_labels(words), set()


def _write_rag_svg(
    profile_name: str,
    query: str,
    hits: list[object],
    distances: dict[int, dict[str, float]],
    output_path: Path,
    *,
    groups: list[str] | None = None,
    confidence: dict[str, float | int] | None = None,
) -> None:
    """Render a 2D external diagnostic map from term-to-chunk vector distances."""

    words = _svg_query_terms(query)
    groups = _svg_query_groups(query) if groups is None else groups
    nodes = [*words, *groups]
    distant_words, distant_groups = _rag_svg_distant_nodes(words, groups, hits, distances)
    graph_width, width = 960, 1500
    height = max(760, 300 + max(len(nodes), len(hits)) * 105)
    term_positions, chunk_positions, smallest, largest, fit = _rag_svg_layout(
        nodes,
        hits,
        distances,
        graph_width,
        height,
        outside_nodes=distant_words | distant_groups,
    )
    hit_numbers = {hit.chunk_id: number for number, hit in enumerate(hits, start=1)}

    def ratio(value: float) -> float:
        return 0.5 if largest == smallest else (value - smallest) / (largest - smallest)

    boundary = (
        f'<circle cx="{fit["boundary_x"]:.1f}" cy="{fit["boundary_y"]:.1f}" r="{fit["boundary_radius"]:.1f}" '
        'fill="#f1f3f5" fill-opacity="0.38" stroke="#9aa2ad" stroke-width="1.5" stroke-dasharray="7 6"/>'
        if distant_words or distant_groups else ""
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfcfe"/>',
        boundary,
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#17233e}.title{font-size:22px;font-weight:700}.label{font-size:14px;font-weight:650}.small{font-size:10px;fill:#44536b}.word{stroke-width:2}.group{stroke-width:2}.chunk{stroke-width:2}</style>',
        '<text class="title" x="42" y="43">RAG vector retrieval — 2D diagnostic map</text>',
        f'<text class="small" x="42" y="69">wiki: {html_escape(profile_name)} · query: {html_escape(query)} · shorter edge = smaller individual word-to-chunk L2 distance</text>',
        f'<text class="small" x="42" y="91">Solid green = individual words; dashed violet = comma-separated semantic groups; grey = relatively distant groups and words. Edge fit: ±{fit["mean_absolute_error"]:.0f}px mean.</text>',
        f'<line x1="980" y1="115" x2="980" y2="{height - 30}" stroke="#d7dde8" stroke-width="1"/>',
        '<text class="label" x="1015" y="138">Chunk legend</text>',
        '<text class="small" x="1015" y="158"># · source / preview · whole-query distance</text>',
    ]
    for hit_index, hit in enumerate(hits):
        target_x, target_y = chunk_positions[hit.chunk_id]
        for term_index, (term, (source_x, source_y)) in enumerate(term_positions.items()):
            value = distances.get(hit.chunk_id, {}).get(term)
            if value is None:
                continue
            relative = ratio(value)
            red, green = int(48 + relative * 160), int(150 - relative * 55)
            is_group = term in groups
            is_distant_word = term in distant_words
            is_distant_group = term in distant_groups
            stroke = "#8a929d" if is_distant_group else ("#8b6fb5" if is_group else f"rgb({red},{green},145)")
            dash = ' stroke-dasharray="6 5"' if is_group else ""
            opacity = "0.38" if (is_distant_word or is_distant_group) else ("0.48" if is_group else "0.68")
            # Make the genuinely close relations immediately visible.  The
            # square keeps ordinary mid-range edges thin and reserves the
            # visual weight for the nearest part of the ranking.
            edge_width = 1.0 + (1 - relative) ** 2 * 4.6
            parts.append(
                f'<line x1="{source_x:.1f}" y1="{source_y:.1f}" x2="{target_x:.1f}" y2="{target_y:.1f}" '
                f'stroke="{stroke}" stroke-width="{edge_width:.1f}" opacity="{opacity}"{dash}/>'
            )
            if is_group:
                continue
            line_x, line_y = target_x - source_x, target_y - source_y
            line_length = max((line_x * line_x + line_y * line_y) ** 0.5, 0.001)
            normal_x, normal_y = -line_y / line_length, line_x / line_length
            direction = -1 if (term_index + hit_index) % 2 else 1
            label_offset = 17 + ((term_index * 2 + hit_index) % 3) * 9
            midpoint_x = (source_x + target_x) / 2 + direction * normal_x * label_offset
            midpoint_y = (source_y + target_y) / 2 + direction * normal_y * label_offset
            parts.append(
                f'<text class="small" text-anchor="middle" x="{midpoint_x:.1f}" y="{midpoint_y:.1f}">{value:.3f}</text>'
            )
    for term, (x, y) in term_positions.items():
        if term in groups:
            fill, stroke = ("#f1f3f5", "#8a929d") if term in distant_groups else ("#f0ebf8", "#8b6fb5")
            parts.append(f'<rect class="group" x="{x - 82:.1f}" y="{y - 25:.1f}" width="164" height="50" rx="16" fill="{fill}" stroke="{stroke}"/>')
        elif term in distant_words:
            parts.append(f'<circle class="word" cx="{x:.1f}" cy="{y:.1f}" r="46" fill="#f1f3f5" stroke="#8a929d"/>')
        else:
            parts.append(f'<circle class="word" cx="{x:.1f}" cy="{y:.1f}" r="46" fill="#e8f4f3" stroke="#138a82"/>')
        parts.append(f'<text class="label" text-anchor="middle" x="{x:.1f}" y="{y + 5:.1f}">{html_escape(term)}</text>')
    confidence_lines = ["not available"]
    if confidence is not None:
        confidence_lines = [
            f'nearest chunk: #{int(confidence["rank"])} of {int(confidence["total"])} · top {float(confidence["top_percent"]):.1f}%',
            f'gap #1 → #2: +{float(confidence["gap"]):.4f}' if "gap" in confidence else "gap #1 → #2: not available",
        ]
    parts.extend([
        '<rect x="1005" y="172" width="455" height="58" rx="10" fill="#f7f9fc" stroke="#d7dde8"/>',
        '<text class="label" x="1020" y="193">Retrieval confidence</text>',
        f'<text class="small" x="1020" y="210">{confidence_lines[0]}</text>',
        f'<text class="small" x="1020" y="224">{confidence_lines[1] if len(confidence_lines) > 1 else ""}</text>',
        f'<text class="small" x="1020" y="238">edge scale: {smallest:.3f}–{largest:.3f} → {fit["target_min"]:.0f}–{fit["target_max"]:.0f}px</text>',
    ])
    for hit in hits:
        x, y = chunk_positions[hit.chunk_id]
        parts.append(f'<circle class="chunk" cx="{x:.1f}" cy="{y:.1f}" r="25" fill="#fff5e6" stroke="#ce7b00"/>')
        parts.append(f'<text class="label" text-anchor="middle" x="{x:.1f}" y="{y + 5:.1f}">{hit_numbers[hit.chunk_id]}</text>')
    for number, hit in enumerate(hits, start=1):
        top = 260 + (number - 1) * 92
        source = hit.path.split(' (', 1)[0]
        if len(source) > 47:
            source = source[:44].rstrip() + "…"
        preview = " ".join(hit.text.split())
        if len(preview) > 68:
            preview = preview[:65].rstrip() + "…"
        whole_distance = f"{hit.distance:.4f}" if hit.distance is not None else "n/a"
        parts.extend([
            f'<rect x="1005" y="{top}" width="455" height="76" rx="10" fill="#ffffff" stroke="#d7dde8"/>',
            f'<circle cx="1031" cy="{top + 25}" r="14" fill="#fff5e6" stroke="#ce7b00"/>',
            f'<text class="label" text-anchor="middle" x="1031" y="{top + 30}">{number}</text>',
            f'<text class="label" x="1055" y="{top + 23}">chunk {hit.chunk_index} · {html_escape(source)}</text>',
            f'<text class="small" x="1055" y="{top + 42}">{html_escape(preview)}</text>',
            f'<text class="small" x="1055" y="{top + 62}">whole query distance: {whole_distance}</text>',
        ])
    parts.append('</svg>')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


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
            embeddings = embed_texts(OLLAMA_CONFIG_PATH, config["embedding_model"], [query, *node_labels])
            connection = open_database(profile.path)
            try:
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
            if not files and not configured_web_sources:
                raise VectorError(f"No supported .md, .txt, .pdf, or declared web sources found in {source_root / profile.source_group}.")
            if not arguments.json:
                _local_sources_notice(files, source_root)
            chunk_size = arguments.chunk_size or config.get("chunk_size", 1200)
            chunk_overlap = arguments.chunk_overlap or config.get("chunk_overlap", 160)
            progress = _EmbeddingProgress(enabled=not arguments.json)
            embedder = None if not arguments.embed else _batched_embedder(
                config["embedding_model"], _embedding_batch_size(arguments, config), progress,
            )
            connection = open_database(profile.path)
            try:
                if arguments.overwrite:
                    reset_database(connection)
                result = ingest(
                    connection,
                    source_root,
                    profile.source_group,
                    config["embedding_model"],
                    embedder,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    reindex=arguments.reindex or arguments.overwrite,
                    on_embedding_start=None if embedder is None else progress.start,
                    on_local_result=None if arguments.json else _local_result_notice,
                    web_src_file=None if arguments.no_web else config["web_src_file"],
                    on_web_fetch=None if arguments.json or arguments.no_web else _web_fetch_notice,
                    on_web_result=None if arguments.json or arguments.no_web else _web_result_notice,
                )
            finally:
                connection.close()
            selected = set_main_db(config_path, PROJECT_DIR, profile.name) if profile.name in profiles else register_database_profile(config_path, PROJECT_DIR, profile.name)
            _print({"main_db": selected.name, "database": str(selected.path), "source_group": selected.source_group, "profile_action": "updated" if profile.name in profiles else "created", "embedding_status": "indexed" if embedder is not None else "pending", **result}, arguments.json)
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
                    if arguments.overwrite:
                        reset_database(connection)
                    result = ingest(
                        connection,
                        source_root,
                        profile.source_group,
                        config["embedding_model"],
                        embedder,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        reindex=arguments.reindex or arguments.overwrite,
                        on_embedding_start=None if arguments.no_embed else progress.start,
                        on_local_result=None if arguments.json else _local_result_notice,
                        web_src_file=None if arguments.no_web else config["web_src_file"],
                        on_web_fetch=None if arguments.json or arguments.no_web else _web_fetch_notice,
                        on_web_result=None if arguments.json or arguments.no_web else _web_result_notice,
                    )
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

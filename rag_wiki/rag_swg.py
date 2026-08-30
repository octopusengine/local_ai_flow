"""Render external RAG semantic-word graph (SWG) SVG diagnostics."""

from __future__ import annotations

import math
import re
from html import escape as html_escape
from pathlib import Path

from lib.wrapp_vector import VectorError


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

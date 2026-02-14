"""Convert query results into Cytoscape-compatible graph elements."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go  # type: ignore[import-untyped]

from codex_graph.dashboard.styles import language_color


def files_to_elements(rows: list[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    """Turn file rows into Cytoscape node elements."""
    elements: list[dict[str, Any]] = []
    for file_id, full_path, suffix, content_hash in rows:
        elements.append(
            {
                "data": {
                    "id": file_id,
                    "label": full_path.rsplit("/", 1)[-1],
                    "full_path": full_path,
                    "suffix": suffix,
                    "content_hash": content_hash,
                    "kind": "file",
                }
            }
        )
    return elements


def nodes_to_elements(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Turn AST node rows into Cytoscape node elements."""
    elements: list[dict[str, Any]] = []
    for row in rows:
        span_key = str(row[0]).strip('"')
        node_type = str(row[1]).strip('"')
        elements.append(
            {
                "data": {
                    "id": span_key,
                    "label": node_type,
                    "kind": "ast_node",
                }
            }
        )
    return elements


def node_types_to_elements(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Turn single-column node-type rows into Cytoscape node elements."""
    elements: list[dict[str, Any]] = []
    for row in rows:
        node_type = str(row[0]).strip('"')
        elements.append(
            {
                "data": {
                    "id": node_type,
                    "label": node_type,
                    "kind": "ast_node",
                }
            }
        )
    return elements


def children_to_elements(parent_span_key: str, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Turn child rows into Cytoscape node + edge elements."""
    elements: list[dict[str, Any]] = []
    elements.append(
        {
            "data": {
                "id": parent_span_key,
                "label": "parent",
                "kind": "ast_node",
            }
        }
    )
    for row in rows:
        child_span_key = str(row[0]).strip('"')
        child_type = str(row[1]).strip('"')
        child_index = str(row[2]).strip('"')
        elements.append(
            {
                "data": {
                    "id": child_span_key,
                    "label": f"{child_type} [{child_index}]",
                    "kind": "ast_node",
                }
            }
        )
        elements.append(
            {
                "data": {
                    "source": parent_span_key,
                    "target": child_span_key,
                    "label": child_index,
                }
            }
        )
    return elements


def files_to_overview_elements(
    file_rows: list[tuple[str, str, str, int]],
    shared_shape_rows: list[tuple[str, str, int]],
) -> list[dict[str, Any]]:
    """Build Cytoscape elements for the overview files graph.

    Nodes are sized by AST node count and colored by language.
    Edges connect files that share shape_hash values.
    """
    elements: list[dict[str, Any]] = []
    path_to_id: dict[str, str] = {}
    for file_uuid, path, lang, count in file_rows:
        path_to_id[path] = file_uuid
        elements.append(
            {
                "data": {
                    "id": file_uuid,
                    "label": path.rsplit("/", 1)[-1],
                    "full_path": path,
                    "language": lang,
                    "node_count": count,
                    "color": language_color(lang),
                    "kind": "file",
                }
            }
        )
    for path_a, path_b, shared_count in shared_shape_rows:
        id_a = path_to_id.get(path_a)
        id_b = path_to_id.get(path_b)
        if id_a and id_b:
            elements.append(
                {
                    "data": {
                        "source": id_a,
                        "target": id_b,
                        "label": f"{shared_count} shared",
                    }
                }
            )
    return elements


def node_type_counts_to_figure(rows: list[tuple[str, int]]) -> go.Figure:
    """Return a Plotly horizontal bar chart of node type frequencies."""
    if not rows:
        fig = go.Figure()
        fig.update_layout(title="No data", height=300)
        return fig
    # Reverse so highest count is at top
    types = [r[0] for r in reversed(rows)]
    counts = [r[1] for r in reversed(rows)]
    fig = go.Figure(go.Bar(x=counts, y=types, orientation="h", marker_color="#2196F3"))
    fig.update_layout(
        title="AST Node Type Distribution",
        xaxis_title="Count",
        yaxis_title="Node Type",
        height=max(300, len(types) * 25 + 100),
        margin={"l": 200, "r": 20, "t": 40, "b": 40},
    )
    return fig


def explorer_merge_elements(
    existing: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge new Cytoscape elements into existing ones, deduplicating by ID."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for el in existing:
        data = el.get("data", {})
        el_id = data.get("id") or f"{data.get('source', '')}_{data.get('target', '')}"
        if el_id not in seen:
            seen.add(el_id)
            merged.append(el)
    for el in new:
        data = el.get("data", {})
        el_id = data.get("id") or f"{data.get('source', '')}_{data.get('target', '')}"
        if el_id not in seen:
            seen.add(el_id)
            merged.append(el)
    return merged

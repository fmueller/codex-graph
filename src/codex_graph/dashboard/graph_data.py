"""Convert query results into Cytoscape-compatible graph elements."""

from __future__ import annotations

from typing import Any


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
        span_key = str(row[0])
        node_type = str(row[1])
        elements.append(
            {
                "data": {
                    "id": span_key,
                    "label": f"{node_type}",
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
        child_span_key = str(row[0])
        child_type = str(row[1])
        child_index = str(row[2])
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

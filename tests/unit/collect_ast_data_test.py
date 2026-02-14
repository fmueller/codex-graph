"""Unit tests for _collect_ast_data — the collect phase of batch ingest."""

from codex_graph.db.postgres import _collect_ast_data
from codex_graph.models import AstNode, Position


def _pos(row: int = 0, col: int = 0) -> Position:
    return Position(row=row, column=col)


def test_single_leaf_node() -> None:
    """A single leaf node should produce one node entry, no edges, one occurrence."""
    node = AstNode(
        file_uuid="f1",
        type="identifier",
        start_byte=0,
        end_byte=3,
        start_point=_pos(0, 0),
        end_point=_pos(0, 3),
    )
    source = b"foo"

    nodes, edges, occurrences = _collect_ast_data(node, "f1", source)

    assert len(nodes) == 1
    assert nodes[0]["type"] == "identifier"
    assert nodes[0]["span_key"] == "f1:identifier:0:3"
    assert nodes[0]["shape_hash"]  # non-empty hash
    assert len(edges) == 0
    assert len(occurrences) == 1
    assert occurrences[0] == (0, 0, 3)  # (node_index, start_byte, end_byte)


def test_parent_with_two_children() -> None:
    """A parent with two children produces 3 nodes, 2 edges, 3 occurrences."""
    child_a = AstNode(
        file_uuid="f1",
        type="identifier",
        start_byte=4,
        end_byte=5,
        start_point=_pos(0, 4),
        end_point=_pos(0, 5),
    )
    child_b = AstNode(
        file_uuid="f1",
        type="integer",
        start_byte=8,
        end_byte=9,
        start_point=_pos(0, 8),
        end_point=_pos(0, 9),
    )
    parent = AstNode(
        file_uuid="f1",
        type="assignment",
        start_byte=0,
        end_byte=10,
        start_point=_pos(0, 0),
        end_point=_pos(0, 10),
        children=[child_a, child_b],
    )
    source = b"x    =   1"

    nodes, edges, occurrences = _collect_ast_data(parent, "f1", source)

    assert len(nodes) == 3
    # Children are collected before parents (post-order traversal)
    assert nodes[0]["type"] == "identifier"
    assert nodes[1]["type"] == "integer"
    assert nodes[2]["type"] == "assignment"

    assert len(edges) == 2
    parent_idx = 2
    # edges are (parent_index, child_index, child_order)
    assert edges[0] == (parent_idx, 0, 0)
    assert edges[1] == (parent_idx, 1, 1)

    assert len(occurrences) == 3


def test_indices_are_consistent() -> None:
    """Edge indices should reference valid positions in the node list."""
    child = AstNode(
        file_uuid="f1",
        type="identifier",
        start_byte=0,
        end_byte=1,
        start_point=_pos(),
        end_point=_pos(),
    )
    root = AstNode(
        file_uuid="f1",
        type="module",
        start_byte=0,
        end_byte=2,
        start_point=_pos(),
        end_point=_pos(),
        children=[child],
    )
    source = b"x\n"

    nodes, edges, occurrences = _collect_ast_data(root, "f1", source)

    for parent_idx, child_idx, _ in edges:
        assert 0 <= parent_idx < len(nodes)
        assert 0 <= child_idx < len(nodes)

    for node_idx, _, _ in occurrences:
        assert 0 <= node_idx < len(nodes)

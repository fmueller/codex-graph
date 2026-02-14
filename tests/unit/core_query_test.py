"""Unit tests for core query builders."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from codex_graph.core.query import query_file_root_nodes


@pytest.mark.asyncio
async def test_query_file_root_nodes_applies_node_type_filter() -> None:
    db = AsyncMock()
    db.fetch_cypher.return_value = []

    await query_file_root_nodes(db, "/tmp/sample.py", node_type="function_definition")

    cypher_arg = db.fetch_cypher.call_args[0][0]
    assert "parent IS NULL" in cypher_arg
    assert "n.type = 'function_definition'" in cypher_arg
    assert db.fetch_cypher.call_args[1]["columns"] == 4


@pytest.mark.asyncio
async def test_query_file_root_nodes_without_node_type_filter() -> None:
    db = AsyncMock()
    db.fetch_cypher.return_value = []

    await query_file_root_nodes(db, "/tmp/sample.py")

    cypher_arg = db.fetch_cypher.call_args[0][0]
    assert "parent IS NULL" in cypher_arg
    assert "n.type =" not in cypher_arg
    assert db.fetch_cypher.call_args[1]["columns"] == 4

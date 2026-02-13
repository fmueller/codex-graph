"""Integration tests for query functions against a real AGE database."""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from codex_graph.core.ingest import run_ingest
from codex_graph.core.query import query_children, query_cypher, query_files, query_node_types, query_nodes
from codex_graph.db import PostgresGraphDatabase

SAMPLE_PYTHON = """\
def greet(name: str) -> str:
    return f"Hello, {name}!"
"""


@pytest_asyncio.fixture
async def ingested_file(db: PostgresGraphDatabase) -> tuple[str, str]:
    """Ingest a sample Python file and return (file_uuid, tmp_path)."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        tmp_path = f.name

    file_uuid, _ = await run_ingest(db, path=tmp_path)
    return file_uuid, tmp_path


@pytest.mark.asyncio
async def test_query_files(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_files returns at least the ingested file."""
    _, tmp_path = ingested_file
    try:
        rows = await query_files(db)
        assert len(rows) > 0
        full_paths = [row[1] for row in rows]
        resolved = str(Path(tmp_path).resolve())
        assert resolved in full_paths
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_node_types(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_node_types returns expected AST node types."""
    _, tmp_path = ingested_file
    try:
        rows = await query_node_types(db)
        types = [str(row[0]).strip('"') for row in rows]
        assert "module" in types
        assert "function_definition" in types
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_nodes_by_type(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_nodes with type=function_definition returns results."""
    _, tmp_path = ingested_file
    try:
        rows = await query_nodes(db, node_type="function_definition")
        assert len(rows) > 0
        node_types = [str(row[1]).strip('"') for row in rows]
        assert all(t == "function_definition" for t in node_types)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_children(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_children returns child nodes for a known parent."""
    _, tmp_path = ingested_file
    try:
        # Find the module node's span_key (root of the AST)
        module_rows = await query_nodes(db, node_type="module")
        assert len(module_rows) > 0
        span_key = str(module_rows[0][0]).strip('"')

        children = await query_children(db, span_key=span_key)
        assert len(children) > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_cypher_passthrough(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_cypher with a raw Cypher query works end-to-end."""
    _, tmp_path = ingested_file
    try:
        rows = await query_cypher(db, "MATCH (n:AstNode) RETURN count(n)")
        assert len(rows) == 1
        count = int(str(rows[0][0]).strip('"'))
        assert count > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)

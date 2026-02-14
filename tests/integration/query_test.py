"""Integration tests for query functions against a real AGE database."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from typer.testing import CliRunner

from codex_graph.cli.app import app
from codex_graph.core.ingest import run_ingest
from codex_graph.core.query import (
    query_children,
    query_cypher,
    query_file_node_counts,
    query_file_root_nodes,
    query_files,
    query_language_distribution,
    query_node_type_counts,
    query_node_types,
    query_nodes,
    query_statistics,
)
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
async def test_query_cypher_multi_column(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """Multi-column Cypher queries auto-detect column count."""
    _, tmp_path = ingested_file
    try:
        rows = await query_cypher(db, "MATCH (n:AstNode) RETURN n.type, count(n)")
        assert len(rows) > 0
        assert len(rows[0]) == 2
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


@pytest.mark.asyncio
async def test_query_statistics(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_statistics returns positive counts after ingest."""
    _, tmp_path = ingested_file
    try:
        stats = await query_statistics(db)
        assert stats["files"] > 0
        assert stats["ast_nodes"] > 0
        assert stats["parent_of_edges"] > 0
        assert stats["occurs_in_edges"] > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_language_distribution(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_language_distribution returns language counts."""
    _, tmp_path = ingested_file
    try:
        rows = await query_language_distribution(db)
        assert len(rows) > 0
        languages = [lang for lang, _ in rows]
        assert "python" in languages
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_node_type_counts(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_node_type_counts returns types with counts."""
    _, tmp_path = ingested_file
    try:
        rows = await query_node_type_counts(db)
        assert len(rows) > 0
        types = [t for t, _ in rows]
        assert "function_definition" in types
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_file_node_counts(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_file_node_counts returns file paths with node counts."""
    _, tmp_path = ingested_file
    try:
        rows = await query_file_node_counts(db)
        assert len(rows) > 0
        _, path, lang, count = rows[0]
        assert count > 0
        assert lang == "python"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_file_root_nodes(db: PostgresGraphDatabase, ingested_file: tuple[str, str]) -> None:
    """query_file_root_nodes returns top-level nodes for a file."""
    _, tmp_path = ingested_file
    try:
        # Ingest now stores a canonical absolute path in FileVersion.path.
        rows = await query_file_root_nodes(db, str(Path(tmp_path).resolve()))
        assert len(rows) > 0
        # The root node should be a module node
        node_type = str(rows[0][1]).strip('"')
        assert node_type == "module"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_query_file_root_nodes_with_relative_ingest_path(db: PostgresGraphDatabase) -> None:
    """query_file_root_nodes works when ingest path is provided as a relative path."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        abs_path = Path(f.name).resolve()

    rel_path = os.path.relpath(abs_path, Path.cwd())
    try:
        await run_ingest(db, path=rel_path)
        rows = await query_file_root_nodes(db, str(abs_path))
        assert len(rows) > 0
        node_type = str(rows[0][1]).strip('"')
        assert node_type == "module"
    finally:
        abs_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pool_event_loads_age_without_ensure_ready(
    _run_migrations: None,
    test_db_url: str,
    ingested_file: tuple[str, str],
) -> None:
    """A fresh engine from get_engine() can run Cypher without calling ensure_ready().

    This proves the pool-level 'connect' event listener correctly loads AGE
    and sets the search_path on every new connection.
    """
    _, tmp_path = ingested_file
    try:
        with patch.dict(os.environ, {"DATABASE_URL": test_db_url}):
            from codex_graph.db.engine import get_engine

            engine = get_engine()
        fresh_db = PostgresGraphDatabase(engine)
        # Intentionally skip ensure_ready() — the pool event should suffice.
        rows = await query_cypher(fresh_db, "MATCH (n:AstNode) RETURN count(n)")
        assert len(rows) == 1
        count = int(str(rows[0][0]).strip('"'))
        assert count > 0
        await engine.dispose()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_cli_cypher_multi_column(
    ingested_file: tuple[str, str],
    test_db_url: str,
) -> None:
    """CLI 'query cypher' auto-detects column count for multi-column RETURN."""
    from sqlalchemy.ext.asyncio import create_async_engine

    _, tmp_path = ingested_file
    try:
        runner = CliRunner()

        def _fresh_db() -> PostgresGraphDatabase:
            return PostgresGraphDatabase(create_async_engine(test_db_url, future=True))

        with patch("codex_graph.cli.query._get_database", side_effect=_fresh_db):
            result = runner.invoke(
                app,
                ["query", "cypher", "MATCH (n:AstNode) RETURN n.type, count(n)"],
            )
        assert result.exit_code == 0, result.output
        assert "0 rows" not in result.output
    finally:
        Path(tmp_path).unlink(missing_ok=True)

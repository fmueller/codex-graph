"""Integration tests for the ingest pipeline against a real AGE database."""

import tempfile
from pathlib import Path

import pytest

from codex_graph.core.ingest import run_ingest
from codex_graph.core.query import query_cypher, query_files
from codex_graph.db import PostgresGraphDatabase

SAMPLE_PYTHON = '''\
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"


class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b
'''


@pytest.mark.asyncio
async def test_ingest_persists_file(db: PostgresGraphDatabase) -> None:
    """Ingesting a file creates a row in the files table."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        tmp_path = f.name

    try:
        file_uuid, lang = await run_ingest(db, path=tmp_path)
        assert lang == "python"
        assert file_uuid

        files = await query_files(db)
        full_paths = [row[1] for row in files]
        resolved = str(Path(tmp_path).resolve())
        assert resolved in full_paths
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_creates_ast_nodes(db: PostgresGraphDatabase) -> None:
    """Ingesting a Python file creates AstNode vertices in the AGE graph."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        tmp_path = f.name

    try:
        await run_ingest(db, path=tmp_path)

        rows = await query_cypher(db, "MATCH (n:AstNode) RETURN count(n)")
        count = int(str(rows[0][0]).strip('"'))
        assert count > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_creates_parent_of_edges(db: PostgresGraphDatabase) -> None:
    """Ingesting a file creates PARENT_OF edges between AST nodes."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        tmp_path = f.name

    try:
        await run_ingest(db, path=tmp_path)

        rows = await query_cypher(db, "MATCH ()-[e:PARENT_OF]->() RETURN count(e)")
        count = int(str(rows[0][0]).strip('"'))
        assert count > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_creates_occurs_in_edges(db: PostgresGraphDatabase) -> None:
    """Ingesting a file creates OCCURS_IN edges linking nodes to FileVersion."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        tmp_path = f.name

    try:
        await run_ingest(db, path=tmp_path)

        rows = await query_cypher(db, "MATCH ()-[e:OCCURS_IN]->() RETURN count(e)")
        count = int(str(rows[0][0]).strip('"'))
        assert count > 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_deduplicates_same_file(db: PostgresGraphDatabase) -> None:
    """Ingesting the same file twice returns the same file UUID (content-hash dedup)."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE_PYTHON)
        f.flush()
        tmp_path = f.name

    try:
        uuid1, _ = await run_ingest(db, path=tmp_path)
        uuid2, _ = await run_ingest(db, path=tmp_path)
        assert uuid1 == uuid2
    finally:
        Path(tmp_path).unlink(missing_ok=True)

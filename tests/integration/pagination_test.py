"""Integration tests for cursor-based pagination against a real PostgreSQL+AGE database."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from codex_graph.core.ingest import run_ingest
from codex_graph.db.postgres import PostgresGraphDatabase


@pytest_asyncio.fixture
async def ingested_files(db: PostgresGraphDatabase, tmp_path: Path) -> list[str]:
    """Ingest three small Python files and return their UUIDs."""
    uuids: list[str] = []
    for i, code in enumerate(["x = 1", "y = 2", "z = 3"]):
        fpath = tmp_path / f"file_{i}.py"
        fpath.write_text(code, encoding="utf-8")
        file_uuid, _ = await run_ingest(db, path=str(fpath))
        uuids.append(file_uuid)
    return uuids


@pytest.mark.asyncio
async def test_list_files_cursor_no_cursor(db: PostgresGraphDatabase, ingested_files: list[str]) -> None:
    """Without a cursor, returns all files ordered by full_path."""
    rows = await db.list_files_cursor(limit=50)
    assert len(rows) >= 3
    paths = [r[1] for r in rows]
    assert paths == sorted(paths)


@pytest.mark.asyncio
async def test_list_files_cursor_after(db: PostgresGraphDatabase, ingested_files: list[str]) -> None:
    """page[after] returns files after the given cursor position."""
    all_rows = await db.list_files_cursor(limit=50)
    assert len(all_rows) >= 3

    # Use the first file as cursor
    first = all_rows[0]
    after_rows = await db.list_files_cursor(limit=50, after_path=first[1], after_id=first[0])
    assert len(after_rows) == len(all_rows) - 1
    # First result should not be the same as our cursor
    assert after_rows[0][0] != first[0]


@pytest.mark.asyncio
async def test_list_files_cursor_before(db: PostgresGraphDatabase, ingested_files: list[str]) -> None:
    """page[before] returns files before the given cursor position."""
    all_rows = await db.list_files_cursor(limit=50)
    assert len(all_rows) >= 3

    # Use the last file as cursor
    last = all_rows[-1]
    before_rows = await db.list_files_cursor(limit=50, before_path=last[1], before_id=last[0])
    assert len(before_rows) == len(all_rows) - 1
    assert before_rows[-1][0] != last[0]


@pytest.mark.asyncio
async def test_list_files_cursor_full_pagination(db: PostgresGraphDatabase, ingested_files: list[str]) -> None:
    """Iterate through all pages using cursors and verify all files seen exactly once."""
    seen_ids: list[str] = []
    after_path: str | None = None
    after_id: str | None = None

    for _ in range(10):  # safety limit
        rows = await db.list_files_cursor(limit=2, after_path=after_path, after_id=after_id)
        if not rows:
            break
        for r in rows:
            seen_ids.append(r[0])
        last = rows[-1]
        after_path = last[1]
        after_id = last[0]

    # All ingested files should appear exactly once
    for uid in ingested_files:
        assert uid in seen_ids
    assert len(seen_ids) == len(set(seen_ids)), "Duplicate entries found during pagination"


@pytest.mark.asyncio
async def test_list_files_cursor_limit(db: PostgresGraphDatabase, ingested_files: list[str]) -> None:
    """Limit parameter constrains the number of rows returned."""
    rows = await db.list_files_cursor(limit=1)
    assert len(rows) == 1

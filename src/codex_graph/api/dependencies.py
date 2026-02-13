from __future__ import annotations

from collections.abc import AsyncIterator

from codex_graph.core.ports.database import GraphDatabase
from codex_graph.db.engine import get_engine
from codex_graph.db.postgres import PostgresGraphDatabase

_db: PostgresGraphDatabase | None = None


async def get_database() -> AsyncIterator[GraphDatabase]:
    """Yield a ``GraphDatabase`` instance, creating it lazily on first call."""
    global _db  # noqa: PLW0603
    if _db is None:
        _db = PostgresGraphDatabase(get_engine())
    yield _db


async def shutdown_database() -> None:
    global _db  # noqa: PLW0603
    if _db is not None:
        await _db.dispose()
        _db = None

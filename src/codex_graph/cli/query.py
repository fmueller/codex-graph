import asyncio
from collections.abc import Sequence
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import (
    query_children as _query_children,
)
from codex_graph.core.query import (
    query_cypher as _query_cypher,
)
from codex_graph.core.query import (
    query_files as _query_files,
)
from codex_graph.core.query import (
    query_node_types as _query_node_types,
)
from codex_graph.core.query import (
    query_nodes as _query_nodes,
)

query_app = typer.Typer(help="Query the ingested graph.")
console = Console()


def _render_table(headers: Sequence[str], rows: Sequence[tuple[Any, ...]]) -> None:
    table = Table(show_lines=False)
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*(str(v) for v in row))
    console.print(table)
    console.print(f"({len(rows)} rows)")


def _get_database() -> "GraphDatabase":
    from codex_graph.db.engine import get_engine
    from codex_graph.db.postgres import PostgresGraphDatabase

    return PostgresGraphDatabase(get_engine())


@query_app.command("files")
def files(
    limit: Annotated[int, typer.Option(help="Max rows to return.")] = 50,
) -> None:
    """List ingested files."""
    db = _get_database()

    async def _run() -> None:
        try:
            rows = await _query_files(db, limit)
            _render_table(["id", "full_path", "suffix", "content_hash"], rows)
        finally:
            await db.dispose()

    asyncio.run(_run())


@query_app.command("node-types")
def node_types(
    file: Annotated[str | None, typer.Option(help="Filter by file path.")] = None,
    limit: Annotated[int, typer.Option(help="Max rows to return.")] = 50,
) -> None:
    """List distinct AST node types."""
    db = _get_database()

    async def _run() -> None:
        try:
            await db.ensure_ready()
            rows = await _query_node_types(db, file, limit)
            _render_table(["type"], rows)
        finally:
            await db.dispose()

    asyncio.run(_run())


@query_app.command("nodes")
def nodes(
    type: Annotated[str, typer.Option("--type", help="AST node type to search for.")],
    file: Annotated[str | None, typer.Option(help="Filter by file path.")] = None,
    limit: Annotated[int, typer.Option(help="Max rows to return.")] = 50,
) -> None:
    """Find AST nodes by type."""
    db = _get_database()

    async def _run() -> None:
        try:
            await db.ensure_ready()
            rows = await _query_nodes(db, type, file, limit)
            _render_table(["span_key", "type", "start_byte", "end_byte"], rows)
        finally:
            await db.dispose()

    asyncio.run(_run())


@query_app.command("children")
def children(
    span_key: Annotated[str, typer.Option("--span-key", help="Span key of the parent node.")],
    limit: Annotated[int, typer.Option(help="Max rows to return.")] = 50,
) -> None:
    """List ordered children of a node."""
    db = _get_database()

    async def _run() -> None:
        try:
            await db.ensure_ready()
            rows = await _query_children(db, span_key, limit)
            _render_table(["span_key", "type", "child_index"], rows)
        finally:
            await db.dispose()

    asyncio.run(_run())


@query_app.command("cypher")
def cypher(
    query_string: Annotated[str, typer.Argument(help="Cypher query to execute.")],
    columns: Annotated[int, typer.Option(help="Number of RETURN columns in the query.")] = 1,
) -> None:
    """Run a raw Cypher query."""
    db = _get_database()

    async def _run() -> None:
        try:
            await db.ensure_ready()
            rows = await _query_cypher(db, query_string, columns)
            if rows:
                headers = [f"col{i}" for i in range(len(rows[0]))]
                _render_table(headers, rows)
            else:
                console.print("(0 rows)")
        finally:
            await db.dispose()

    asyncio.run(_run())

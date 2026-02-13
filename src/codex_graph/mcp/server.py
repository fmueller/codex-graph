"""FastMCP server exposing codex-graph tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from codex_graph.core.ingest import run_ingest
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


def create_mcp_server(db: GraphDatabase) -> FastMCP:
    """Create a FastMCP server wired to the given database."""

    mcp = FastMCP("codex-graph", instructions="Parse, store, and query code ASTs in a graph database.")

    @mcp.tool()
    async def ingest(path: str | None = None, code: str | None = None, language: str | None = None) -> str:
        """Ingest a code file or snippet into the graph database."""
        if path is None and code is None:
            return "Error: either 'path' or 'code' must be provided."
        await db.ensure_ready()
        file_uuid, resolved_language = await run_ingest(db, path=path, code=code, language=language)
        return f"Ingested file {file_uuid} (language: {resolved_language})"

    @mcp.tool()
    async def list_files(limit: int = 50) -> list[dict[str, str]]:
        """List ingested files."""
        await db.ensure_ready()
        rows = await _query_files(db, limit)
        return [{"id": r[0], "full_path": r[1], "suffix": r[2], "content_hash": r[3]} for r in rows]

    @mcp.tool()
    async def node_types(file: str | None = None, limit: int = 50) -> list[str]:
        """List distinct AST node types."""
        await db.ensure_ready()
        rows = await _query_node_types(db, file, limit)
        return [str(r[0]) for r in rows]

    @mcp.tool()
    async def find_nodes(type: str, file: str | None = None, limit: int = 50) -> list[dict[str, str]]:
        """Find AST nodes by type."""
        await db.ensure_ready()
        rows = await _query_nodes(db, type, file, limit)
        return [
            {"span_key": str(r[0]), "type": str(r[1]), "start_byte": str(r[2]), "end_byte": str(r[3])} for r in rows
        ]

    @mcp.tool()
    async def children(span_key: str, limit: int = 50) -> list[dict[str, str]]:
        """List ordered children of a node."""
        await db.ensure_ready()
        rows = await _query_children(db, span_key, limit)
        return [{"span_key": str(r[0]), "type": str(r[1]), "child_index": str(r[2])} for r in rows]

    @mcp.tool()
    async def cypher(query: str, columns: int | None = None) -> list[list[Any]]:
        """Run a raw Cypher query."""
        await db.ensure_ready()
        rows = await _query_cypher(db, query, columns)
        return [list(row) for row in rows]

    return mcp

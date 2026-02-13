"""Tests for the MCP server tool definitions."""

from __future__ import annotations

import inspect

from codex_graph.db.memory import InMemoryGraphDatabase
from codex_graph.mcp.server import create_mcp_server


class TestMcpServerCreation:
    def test_creates_server(self) -> None:
        db = InMemoryGraphDatabase()
        server = create_mcp_server(db)
        assert server is not None
        assert server.name == "codex-graph"

    def test_server_has_tools(self) -> None:
        db = InMemoryGraphDatabase()
        server = create_mcp_server(db)
        tool_names = {t.name for t in server._tool_manager._tools.values()}
        assert "ingest" in tool_names
        assert "list_files" in tool_names
        assert "node_types" in tool_names
        assert "find_nodes" in tool_names
        assert "children" in tool_names
        assert "cypher" in tool_names

    def test_cypher_tool_columns_defaults_to_none(self) -> None:
        """The MCP cypher tool should auto-detect columns (default None)."""
        db = InMemoryGraphDatabase()
        server = create_mcp_server(db)
        cypher_tool = server._tool_manager._tools["cypher"]
        fn = cypher_tool.fn  # type: ignore[attr-defined]
        sig = inspect.signature(fn)
        assert sig.parameters["columns"].default is None

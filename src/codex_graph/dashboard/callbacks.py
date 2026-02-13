"""Dash callback registrations."""

from __future__ import annotations

import asyncio
from typing import Any

from dash import Dash, Input, Output, State

from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import query_files as _query_files
from codex_graph.core.query import query_node_types as _query_node_types
from codex_graph.dashboard.graph_data import files_to_elements, nodes_to_elements


def register_callbacks(app: Dash, db: GraphDatabase) -> None:
    @app.callback(
        Output("graph", "elements"),
        Input("run-btn", "n_clicks"),
        State("query-type", "value"),
        prevent_initial_call=True,
    )
    def update_graph(n_clicks: int, query_type: str) -> list[dict[str, Any]]:
        loop = asyncio.new_event_loop()
        try:
            if query_type == "files":
                rows = loop.run_until_complete(_query_files(db, 50))
                return files_to_elements(rows)
            elif query_type == "node_types":
                rows = loop.run_until_complete(_query_node_types(db, None, 50))
                return nodes_to_elements(rows)
            return []
        finally:
            loop.close()

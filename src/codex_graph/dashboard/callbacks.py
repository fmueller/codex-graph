"""Dash callback registrations."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

from dash import Dash, Input, Output, State

from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import query_files as _query_files
from codex_graph.core.query import query_node_types as _query_node_types
from codex_graph.dashboard.graph_data import files_to_elements, node_types_to_elements


def register_callbacks(app: Dash, db_factory: Callable[[], GraphDatabase]) -> None:
    _loop = asyncio.new_event_loop()
    _db = db_factory()
    threading.Thread(target=_loop.run_forever, daemon=True, name="dash-async").start()

    def _run_async(coro: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout=30)

    # Ensure AGE extension + graph exist (same as API/MCP/CLI).
    _run_async(_db.ensure_ready())

    @app.callback(
        Output("graph", "elements"),
        Input("run-btn", "n_clicks"),
        State("query-type", "value"),
    )
    def update_graph(n_clicks: int, query_type: str) -> list[dict[str, Any]]:
        if query_type == "files":
            rows = _run_async(_query_files(_db, 50))
            return files_to_elements(rows)
        elif query_type == "node_types":
            rows = _run_async(_query_node_types(_db, None, 50))
            return node_types_to_elements(rows)
        return []

"""Dash callback registrations."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

from dash import Dash, Input, Output, State, dash_table, html

from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import (
    query_children as _query_children,
)
from codex_graph.core.query import (
    query_cypher as _query_cypher,
)
from codex_graph.core.query import (
    query_file_node_counts as _query_file_node_counts,
)
from codex_graph.core.query import (
    query_file_root_nodes as _query_file_root_nodes,
)
from codex_graph.core.query import (
    query_language_distribution as _query_language_distribution,
)
from codex_graph.core.query import (
    query_node_detail as _query_node_detail,
)
from codex_graph.core.query import (
    query_node_type_counts as _query_node_type_counts,
)
from codex_graph.core.query import (
    query_node_types as _query_node_types,
)
from codex_graph.core.query import (
    query_shared_shapes as _query_shared_shapes,
)
from codex_graph.core.query import (
    query_statistics as _query_statistics,
)
from codex_graph.dashboard.graph_data import (
    children_to_elements,
    explorer_merge_elements,
    files_to_overview_elements,
    node_type_counts_to_figure,
    nodes_to_elements,
)
from codex_graph.dashboard.styles import language_color

_log = logging.getLogger(__name__)


def register_callbacks(app: Dash, db_factory: Callable[[], GraphDatabase]) -> None:
    _loop = asyncio.new_event_loop()
    _db = db_factory()
    threading.Thread(target=_loop.run_forever, daemon=True, name="dash-async").start()

    def _run_async(coro: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout=30)

    # Ensure AGE extension + graph exist (same as API/MCP/CLI).
    _run_async(_db.ensure_ready())

    # ── Overview: stats cards ──────────────────────────────────────
    # Triggered by dcc.Store("page-load") which fires reliably on render.

    @app.callback(
        [
            Output("stat-files", "children"),
            Output("stat-nodes", "children"),
            Output("stat-parent-edges", "children"),
            Output("stat-occurs-edges", "children"),
            Output("language-badges", "children"),
            Output("dashboard-error", "children"),
        ],
        Input("page-load", "data"),
    )
    def load_stats(_: Any) -> tuple[str, str, str, str, list[Any], str]:
        try:
            stats = _run_async(_query_statistics(_db))
            lang_dist = _run_async(_query_language_distribution(_db))
        except Exception as exc:
            _log.exception("load_stats failed")
            return ("Error", "Error", "Error", "Error", [], f"Failed to load statistics: {exc}")
        badges: list[Any] = [
            html.Span(
                f"{lang}: {cnt}",
                style={
                    "padding": "2px 8px",
                    "borderRadius": "12px",
                    "backgroundColor": language_color(lang),
                    "color": "#fff",
                    "fontSize": "11px",
                },
            )
            for lang, cnt in lang_dist
        ]
        return (
            str(stats["files"]),
            str(stats["ast_nodes"]),
            str(stats["parent_of_edges"]),
            str(stats["occurs_in_edges"]),
            badges,
            "",
        )

    # ── Overview: files graph ──────────────────────────────────────

    @app.callback(
        Output("overview-graph", "elements"),
        Input("page-load", "data"),
    )
    def load_overview_graph(_: Any) -> list[dict[str, Any]]:
        try:
            file_rows = _run_async(_query_file_node_counts(_db, 100))
            shared_rows = _run_async(_query_shared_shapes(_db, 50))
            return files_to_overview_elements(file_rows, shared_rows)
        except Exception:
            _log.exception("load_overview_graph failed")
            return []

    # ── Overview: node type chart ──────────────────────────────────

    @app.callback(
        Output("node-type-chart", "figure"),
        Input("page-load", "data"),
    )
    def load_node_type_chart(_: Any) -> Any:
        try:
            rows = _run_async(_query_node_type_counts(_db, 30))
            return node_type_counts_to_figure(rows)
        except Exception:
            _log.exception("load_node_type_chart failed")
            return node_type_counts_to_figure([])

    # ── Explorer: populate file dropdown ───────────────────────────

    @app.callback(
        Output("global-file-dropdown", "options"),
        Input("page-load", "data"),
    )
    def load_file_options(_: Any) -> list[dict[str, str]]:
        try:
            rows = _run_async(_query_file_node_counts(_db, 200))
            return [{"label": path.rsplit("/", 1)[-1], "value": path} for _, path, _, _ in rows]
        except Exception:
            _log.exception("load_file_options failed")
            return []

    # ── Explorer: populate node-type dropdown (filtered by file) ──

    @app.callback(
        Output("explorer-nodetype-dropdown", "options"),
        Input("global-file-dropdown", "value"),
    )
    def load_nodetype_options(file_path: str | None) -> list[dict[str, str]]:
        if not file_path:
            return []
        try:
            rows = _run_async(_query_node_types(_db, file_path, 200))
            return [{"label": str(r[0]).strip('"'), "value": str(r[0]).strip('"')} for r in rows]
        except Exception:
            _log.exception("load_nodetype_options failed")
            return []

    # ── Explorer: run query (file selection / node type filter) ───

    @app.callback(
        [Output("explorer-graph", "elements"), Output("explorer-status", "children")],
        [Input("global-file-dropdown", "value"), Input("explorer-nodetype-dropdown", "value")],
    )
    def run_explorer_query(
        file_path: str | None,
        node_type: str | None,
    ) -> tuple[list[dict[str, Any]], str]:
        if not file_path:
            return [], "Select a file to load graph nodes."
        try:
            rows = _run_async(_query_file_root_nodes(_db, file_path, 200, node_type=node_type))
        except Exception as exc:
            _log.exception("run_explorer_query failed")
            return [], f"Failed to load graph data: {exc}"
        if not rows:
            if node_type:
                return [], "No nodes match the selected file and node-type filter."
            return [], "No root AST nodes found for the selected file."
        new_elements = nodes_to_elements(rows)
        return new_elements, f"Loaded {len(rows)} node(s). Click a node to expand children."

    # ── Explorer: click node to expand children ───────────────────

    @app.callback(
        Output("explorer-graph", "elements", allow_duplicate=True),
        Input("explorer-graph", "tapNodeData"),
        State("explorer-graph", "elements"),
        prevent_initial_call=True,
    )
    def expand_node(
        node_data: dict[str, Any] | None,
        existing: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if not node_data:
            return existing or []
        span_key = node_data.get("id", "")
        if not span_key:
            return existing or []
        rows = _run_async(_query_children(_db, span_key, 50))
        if not rows:
            return existing or []
        new_elements = children_to_elements(span_key, rows)
        return explorer_merge_elements(existing or [], new_elements)

    # ── Explorer: node details panel ──────────────────────────────

    @app.callback(
        Output("node-details-content", "children"),
        Input("explorer-graph", "tapNodeData"),
        prevent_initial_call=True,
    )
    def show_node_details(node_data: dict[str, Any] | None) -> Any:
        if not node_data:
            return "Click a node to see details."
        span_key = node_data.get("id", "")
        if not span_key:
            return "No span_key found."
        try:
            rows = _run_async(_query_node_detail(_db, span_key))
        except Exception:
            _log.exception("show_node_details query failed")
            rows = []
        if not rows:
            return html.Dl(
                [
                    item
                    for k, v in node_data.items()
                    for item in (html.Dt(k, style={"fontWeight": "bold"}), html.Dd(str(v)))
                ]
            )
        row = rows[0]
        labels = [
            "span_key",
            "type",
            "start_line",
            "start_column",
            "end_line",
            "end_column",
            "start_byte",
            "end_byte",
            "shape_hash",
            "file_uuid",
        ]
        return html.Dl(
            [
                item
                for i, label in enumerate(labels)
                if i < len(row)
                for item in (
                    html.Dt(label, style={"fontWeight": "bold"}),
                    html.Dd(str(row[i]).strip('"')),
                )
            ]
        )

    # ── Explorer: Cypher query execution ──────────────────────────

    @app.callback(
        Output("cypher-results", "children"),
        Input("cypher-run-btn", "n_clicks"),
        State("cypher-input", "value"),
        prevent_initial_call=True,
    )
    def run_cypher(n_clicks: int, query: str | None) -> Any:
        if not query or not query.strip():
            return "Enter a Cypher query and click Run."
        try:
            rows = _run_async(_query_cypher(_db, query.strip()))
        except Exception as exc:
            _log.exception("Cypher query failed")
            return html.Pre(f"Error: {exc}", style={"color": "red"})
        if not rows:
            return "No results."
        columns = [{"name": f"col_{i}", "id": f"col_{i}"} for i in range(len(rows[0]))]
        data = [{f"col_{i}": str(v) for i, v in enumerate(row)} for row in rows]
        return dash_table.DataTable(  # type: ignore[attr-defined]
            columns=columns,
            data=data,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "4px 8px", "fontSize": "12px"},
            page_size=20,
        )

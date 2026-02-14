"""Dash application factory."""

from __future__ import annotations

from collections.abc import Callable

import dash_cytoscape as cyto  # type: ignore[import-untyped]
from dash import Dash

from codex_graph.core.ports.database import GraphDatabase
from codex_graph.dashboard.callbacks import register_callbacks
from codex_graph.dashboard.layout import build_layout

cyto.load_extra_layouts()


def create_dashboard(db_factory: Callable[[], GraphDatabase]) -> Dash:
    app = Dash(__name__, suppress_callback_exceptions=True)
    app.layout = build_layout()
    register_callbacks(app, db_factory)
    return app

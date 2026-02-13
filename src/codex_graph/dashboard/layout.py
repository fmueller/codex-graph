"""Dash layout definition."""

from __future__ import annotations

import dash_cytoscape as cyto  # type: ignore[import-untyped]
from dash import dcc, html


def build_layout() -> html.Div:
    return html.Div(
        [
            html.H1("Codex Graph Dashboard"),
            html.P(
                "Visualise files and AST node types stored in the graph database.",
                style={"color": "#666", "marginTop": "-10px", "marginBottom": "20px"},
            ),
            html.Div(
                [
                    html.Label("Query type:"),
                    dcc.Dropdown(
                        id="query-type",
                        options=["files", "node_types"],
                        value="files",
                        style={"width": "200px"},
                    ),
                    html.Button("Run", id="run-btn", n_clicks=0),
                ],
                style={"display": "flex", "gap": "12px", "alignItems": "center", "marginBottom": "20px"},
            ),
            dcc.Loading(
                cyto.Cytoscape(
                    id="graph",
                    elements=[],
                    layout={"name": "cose"},
                    style={"width": "100%", "height": "600px"},
                    stylesheet=[
                        {
                            "selector": "node",
                            "style": {
                                "label": "data(label)",
                                "font-size": "10px",
                            },
                        },
                        {
                            "selector": "edge",
                            "style": {
                                "curve-style": "bezier",
                                "target-arrow-shape": "triangle",
                                "label": "data(label)",
                                "font-size": "8px",
                            },
                        },
                        {
                            "selector": "[kind = 'file']",
                            "style": {
                                "background-color": "#4CAF50",
                                "shape": "rectangle",
                            },
                        },
                        {
                            "selector": "[kind = 'ast_node']",
                            "style": {
                                "background-color": "#2196F3",
                            },
                        },
                    ],
                ),
                type="circle",
            ),
        ],
        style={"padding": "20px"},
    )

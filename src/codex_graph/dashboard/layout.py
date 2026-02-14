"""Dash layout definition with Overview and Graph Explorer tabs."""

from __future__ import annotations

import dash_cytoscape as cyto  # type: ignore[import-untyped]
from dash import dcc, html

from codex_graph.dashboard.styles import EXPLORER_STYLESHEET, OVERVIEW_STYLESHEET


def _stat_card(card_id: str, title: str) -> html.Div:
    """Return a stat card placeholder."""
    return html.Div(
        [
            html.H4(title, style={"margin": "0", "color": "#666", "fontSize": "12px"}),
            html.Div("--", id=card_id, style={"fontSize": "24px", "fontWeight": "bold"}),
        ],
        style={
            "padding": "12px 20px",
            "border": "1px solid #ddd",
            "borderRadius": "8px",
            "minWidth": "120px",
            "textAlign": "center",
        },
    )


def _build_overview_tab() -> html.Div:
    return html.Div(
        [
            # Stats bar
            html.Div(
                [
                    _stat_card("stat-files", "Files"),
                    _stat_card("stat-nodes", "AST Nodes"),
                    _stat_card("stat-parent-edges", "PARENT_OF"),
                    _stat_card("stat-occurs-edges", "OCCURS_IN"),
                    html.Div(id="language-badges", style={"display": "flex", "gap": "6px", "flexWrap": "wrap"}),
                ],
                style={
                    "display": "flex",
                    "gap": "16px",
                    "alignItems": "center",
                    "marginBottom": "20px",
                    "flexWrap": "wrap",
                },
            ),
            # Files graph (sized by node count, colored by language)
            html.H3("Files (sized by AST node count)", style={"marginBottom": "8px"}),
            cyto.Cytoscape(
                id="overview-graph",
                elements=[],
                layout={"name": "cose", "animate": False, "randomize": True, "fit": True},
                style={"width": "100%", "height": "500px", "border": "1px solid #ddd", "borderRadius": "8px"},
                stylesheet=OVERVIEW_STYLESHEET,
            ),
            # Node type bar chart
            html.H3("Node Type Distribution", style={"marginTop": "24px", "marginBottom": "8px"}),
            dcc.Graph(id="node-type-chart", figure={}),
        ]
    )


def _build_explorer_tab() -> html.Div:
    return html.Div(
        [
            html.P(
                "Select a file from the global selector to load the graph. Cypher is optional (advanced).",
                style={"color": "#666", "marginTop": "0", "marginBottom": "12px"},
            ),
            # Explorer controls
            html.Div(
                [
                    dcc.Dropdown(
                        id="explorer-nodetype-dropdown",
                        placeholder="Filter by node type...",
                        style={"width": "320px"},
                        clearable=True,
                    ),
                ],
                style={"display": "flex", "gap": "12px", "alignItems": "center", "marginBottom": "16px"},
            ),
            html.Div(
                id="explorer-status",
                children="Select a file to load graph nodes.",
                style={"marginBottom": "10px", "color": "#555", "fontSize": "13px"},
            ),
            # Main content: graph + details panel
            html.Div(
                [
                    # Cytoscape graph
                    cyto.Cytoscape(
                        id="explorer-graph",
                        elements=[],
                        layout={
                            "name": "dagre",
                            "rankDir": "TB",
                            "animate": False,
                            "nodeSep": 50,
                            "rankSep": 80,
                            "fit": True,
                        },
                        style={
                            "width": "100%",
                            "height": "500px",
                            "border": "1px solid #ddd",
                            "borderRadius": "8px",
                        },
                        stylesheet=EXPLORER_STYLESHEET,
                    ),
                    # Node details panel
                    html.Div(
                        [
                            html.H4("Node Details", style={"marginTop": "0"}),
                            html.Div(id="node-details-content", children="Click a node to see details."),
                        ],
                        style={
                            "minWidth": "280px",
                            "maxWidth": "320px",
                            "padding": "12px",
                            "border": "1px solid #ddd",
                            "borderRadius": "8px",
                            "overflowY": "auto",
                            "maxHeight": "500px",
                        },
                    ),
                ],
                style={"display": "flex", "gap": "16px"},
            ),
            # Cypher results area
            html.Details(
                [
                    html.Summary("Advanced Query (Cypher)", style={"cursor": "pointer", "fontWeight": "bold"}),
                    html.Div(
                        [
                            dcc.Input(
                                id="cypher-input",
                                type="text",
                                placeholder="MATCH (n:AstNode) RETURN n.type, count(n)",
                                style={"width": "360px", "padding": "6px"},
                            ),
                            html.Button("Run Cypher", id="cypher-run-btn", n_clicks=0),
                        ],
                        style={"display": "flex", "gap": "10px", "alignItems": "center", "marginTop": "8px"},
                    ),
                    html.Div(
                        id="cypher-results",
                        children=[],
                        style={"marginTop": "10px"},
                    ),
                ],
                style={"marginTop": "16px"},
            ),
        ]
    )


def build_layout() -> html.Div:
    """Return the top-level Dash layout with tabs.

    Both tab contents are rendered in the initial DOM so all component IDs
    exist from page load and callbacks can fire immediately.
    A hidden dcc.Store fires the initial data-loading callbacks reliably.
    """
    return html.Div(
        [
            dcc.Store(id="page-load", data="ready"),
            html.H1("Codex Graph Dashboard"),
            html.P(
                "Visualise files and AST node types stored in the graph database.",
                style={"color": "#666", "marginTop": "-10px", "marginBottom": "20px"},
            ),
            html.Div(id="dashboard-error", style={"color": "red"}),
            html.Div(
                [
                    html.Label("Graph Scope:", style={"fontWeight": "bold", "marginRight": "8px"}),
                    dcc.Dropdown(
                        id="global-file-dropdown",
                        placeholder="Select a file for graph exploration...",
                        style={"width": "440px"},
                        clearable=True,
                    ),
                    html.Span(
                        "Overview shows global aggregates; Explorer uses this file scope.",
                        style={"fontSize": "12px", "color": "#555"},
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "10px",
                    "marginBottom": "16px",
                    "padding": "8px 12px",
                    "border": "1px solid #ddd",
                    "borderRadius": "8px",
                    "backgroundColor": "#f9f9f9",
                },
            ),
            dcc.Tabs(
                id="main-tabs",
                value="overview",
                children=[
                    dcc.Tab(label="Overview", value="overview", children=[_build_overview_tab()]),
                    dcc.Tab(label="Graph Explorer", value="explorer", children=[_build_explorer_tab()]),
                ],
            ),
        ],
        style={"padding": "20px", "fontFamily": "system-ui, sans-serif"},
    )

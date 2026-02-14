"""Dashboard Cytoscape stylesheets and language color mappings."""

from __future__ import annotations

from typing import Any

from codex_graph.core.languages import _EXTENSION_LANGUAGE_MAP

LANGUAGE_COLORS: dict[str, str] = {
    "python": "#3572A5",
    "javascript": "#F1E05A",
    "typescript": "#3178C6",
    "tsx": "#3178C6",
    "go": "#00ADD8",
    "rust": "#DEA584",
    "java": "#B07219",
    "ruby": "#701516",
    "c": "#555555",
    "cpp": "#F34B7D",
    "csharp": "#178600",
    "css": "#563D7C",
    "html": "#E34C26",
    "json": "#292929",
    "markdown": "#083FA1",
    "toml": "#9C4221",
    "yaml": "#CB171E",
}

_DEFAULT_COLOR = "#888888"


def language_color(language: str) -> str:
    """Return hex color for a language name."""
    return LANGUAGE_COLORS.get(language, _DEFAULT_COLOR)


def suffix_to_language_color(suffix: str) -> str:
    """Map file extension (e.g. '.py') to a hex color."""
    lang = _EXTENSION_LANGUAGE_MAP.get(suffix, "")
    return language_color(lang)


OVERVIEW_STYLESHEET: list[dict[str, Any]] = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "font-size": "10px",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "data(color)",
            "width": "mapData(node_count, 1, 500, 30, 120)",
            "height": "mapData(node_count, 1, 500, 30, 120)",
        },
    },
    {
        "selector": "node:selected",
        "style": {
            "border-width": 3,
            "border-color": "#FF5722",
        },
    },
    {
        "selector": ".highlighted",
        "style": {
            "border-width": 4,
            "border-color": "#FF5722",
        },
    },
    {
        "selector": "edge",
        "style": {
            "curve-style": "bezier",
            "label": "data(label)",
            "font-size": "8px",
            "line-color": "#ccc",
            "target-arrow-color": "#ccc",
            "target-arrow-shape": "triangle",
            "width": 2,
        },
    },
]

EXPLORER_STYLESHEET: list[dict[str, Any]] = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "font-size": "10px",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "#2196F3",
            "width": 40,
            "height": 40,
        },
    },
    {
        "selector": "node:selected",
        "style": {
            "border-width": 3,
            "border-color": "#FF5722",
        },
    },
    {
        "selector": "edge",
        "style": {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "label": "data(label)",
            "font-size": "8px",
            "line-color": "#90CAF9",
            "target-arrow-color": "#90CAF9",
            "width": 2,
        },
    },
]

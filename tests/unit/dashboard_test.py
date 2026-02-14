"""Tests for the dashboard graph_data module and app creation."""

from __future__ import annotations

from unittest.mock import patch

from codex_graph.core.query import _agtype_int
from codex_graph.dashboard.graph_data import (
    children_to_elements,
    explorer_merge_elements,
    files_to_elements,
    files_to_overview_elements,
    node_type_counts_to_figure,
    node_types_to_elements,
    nodes_to_elements,
)
from codex_graph.dashboard.styles import language_color, suffix_to_language_color


class TestFilesToElements:
    def test_empty(self) -> None:
        assert files_to_elements([]) == []

    def test_single_file(self) -> None:
        rows = [("uuid-1", "/src/main.py", ".py", "abc123")]
        elements = files_to_elements(rows)
        assert len(elements) == 1
        data = elements[0]["data"]
        assert data["id"] == "uuid-1"
        assert data["label"] == "main.py"
        assert data["kind"] == "file"

    def test_multiple_files(self) -> None:
        rows = [
            ("uuid-1", "/src/main.py", ".py", "abc123"),
            ("uuid-2", "/src/utils.py", ".py", "def456"),
        ]
        elements = files_to_elements(rows)
        assert len(elements) == 2


class TestNodesToElements:
    def test_empty(self) -> None:
        assert nodes_to_elements([]) == []

    def test_single_node(self) -> None:
        rows = [("main.py::func::0:10", "function_definition", "0", "10")]
        elements = nodes_to_elements(rows)
        assert len(elements) == 1
        data = elements[0]["data"]
        assert data["id"] == "main.py::func::0:10"
        assert data["kind"] == "ast_node"


class TestNodeTypesToElements:
    def test_empty(self) -> None:
        assert node_types_to_elements([]) == []

    def test_single_type(self) -> None:
        rows = [('"function_definition"',)]
        elements = node_types_to_elements(rows)
        assert len(elements) == 1
        assert elements[0]["data"]["id"] == "function_definition"
        assert elements[0]["data"]["label"] == "function_definition"
        assert elements[0]["data"]["kind"] == "ast_node"

    def test_multiple_types(self) -> None:
        rows = [('"module"',), ('"function_definition"',), ('"identifier"',)]
        elements = node_types_to_elements(rows)
        assert len(elements) == 3
        labels = [e["data"]["label"] for e in elements]
        assert "module" in labels
        assert "function_definition" in labels
        assert "identifier" in labels


class TestChildrenToElements:
    def test_empty_children(self) -> None:
        elements = children_to_elements("parent::0:100", [])
        assert len(elements) == 1  # just the parent node
        assert elements[0]["data"]["id"] == "parent::0:100"

    def test_with_children(self) -> None:
        rows = [
            ("child1::0:50", "identifier", "0"),
            ("child2::50:100", "expression", "1"),
        ]
        elements = children_to_elements("parent::0:100", rows)
        # 1 parent + 2 children + 2 edges = 5
        assert len(elements) == 5
        edge_elements = [e for e in elements if "source" in e["data"]]
        assert len(edge_elements) == 2


class TestFilesToOverviewElements:
    def test_empty(self) -> None:
        assert files_to_overview_elements([], []) == []

    def test_nodes_sized_and_colored(self) -> None:
        file_rows = [("uuid-1", "/src/main.py", "python", 42)]
        elements = files_to_overview_elements(file_rows, [])
        assert len(elements) == 1
        data = elements[0]["data"]
        assert data["node_count"] == 42
        assert data["color"] == "#3572A5"  # python color
        assert data["language"] == "python"

    def test_shared_shape_edges(self) -> None:
        file_rows = [
            ("uuid-1", "/src/a.py", "python", 10),
            ("uuid-2", "/src/b.py", "python", 20),
        ]
        shared_rows = [("/src/a.py", "/src/b.py", 3)]
        elements = files_to_overview_elements(file_rows, shared_rows)
        edges = [e for e in elements if "source" in e["data"]]
        assert len(edges) == 1
        assert edges[0]["data"]["label"] == "3 shared"

    def test_shared_edge_skipped_for_unknown_path(self) -> None:
        file_rows = [("uuid-1", "/src/a.py", "python", 10)]
        shared_rows = [("/src/a.py", "/src/unknown.py", 1)]
        elements = files_to_overview_elements(file_rows, shared_rows)
        edges = [e for e in elements if "source" in e["data"]]
        assert len(edges) == 0


class TestNodeTypeCountsToFigure:
    def test_empty_returns_figure(self) -> None:
        fig = node_type_counts_to_figure([])
        assert fig is not None
        assert fig.layout.title.text == "No data"

    def test_returns_bar_chart(self) -> None:
        rows = [("function_definition", 10), ("identifier", 50)]
        fig = node_type_counts_to_figure(rows)
        assert len(fig.data) == 1
        assert fig.data[0].orientation == "h"


class TestExplorerMergeElements:
    def test_deduplicates_by_id(self) -> None:
        existing = [{"data": {"id": "a", "label": "A"}}]
        new = [{"data": {"id": "a", "label": "A"}}, {"data": {"id": "b", "label": "B"}}]
        merged = explorer_merge_elements(existing, new)
        assert len(merged) == 2
        ids = {e["data"]["id"] for e in merged}
        assert ids == {"a", "b"}

    def test_deduplicates_edges(self) -> None:
        existing = [{"data": {"source": "a", "target": "b"}}]
        new = [{"data": {"source": "a", "target": "b"}}, {"data": {"source": "a", "target": "c"}}]
        merged = explorer_merge_elements(existing, new)
        assert len(merged) == 2

    def test_empty_inputs(self) -> None:
        assert explorer_merge_elements([], []) == []


class TestStyles:
    def test_known_language_color(self) -> None:
        assert language_color("python") == "#3572A5"

    def test_unknown_language_color(self) -> None:
        assert language_color("unknown_lang") == "#888888"

    def test_suffix_to_language_color(self) -> None:
        assert suffix_to_language_color(".py") == "#3572A5"

    def test_suffix_unknown(self) -> None:
        assert suffix_to_language_color(".xyz") == "#888888"


class TestAgtypeInt:
    def test_plain_int(self) -> None:
        assert _agtype_int(42) == 42

    def test_quoted_int(self) -> None:
        assert _agtype_int('"42"') == 42

    def test_string_int(self) -> None:
        assert _agtype_int("7") == 7

    def test_empty_string(self) -> None:
        assert _agtype_int('""') == 0

    def test_zero(self) -> None:
        assert _agtype_int(0) == 0


class TestEnginePoolEvent:
    def test_connect_event_registered(self) -> None:
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db"}):
            from codex_graph.db.engine import get_engine

            engine = get_engine()
            has_listeners = bool(engine.sync_engine.pool.dispatch.connect)
            assert has_listeners
            engine.sync_engine.dispose()


class TestDashboardAppCreation:
    def test_creates_app(self) -> None:
        from codex_graph.dashboard.app import create_dashboard
        from codex_graph.db.memory import InMemoryGraphDatabase

        app = create_dashboard(lambda: InMemoryGraphDatabase())
        assert app is not None

    def test_explorer_uses_global_file_and_node_type_inputs(self) -> None:
        from codex_graph.dashboard.app import create_dashboard
        from codex_graph.db.memory import InMemoryGraphDatabase

        app = create_dashboard(lambda: InMemoryGraphDatabase())
        callback = app.callback_map["..explorer-graph.elements...explorer-status.children.."]
        inputs = {(item["id"], item["property"]) for item in callback["inputs"]}
        assert ("global-file-dropdown", "value") in inputs
        assert ("explorer-nodetype-dropdown", "value") in inputs
        assert all(item[0] != "explorer-run-btn" for item in inputs)

    def test_cypher_callback_uses_dedicated_run_button(self) -> None:
        from codex_graph.dashboard.app import create_dashboard
        from codex_graph.db.memory import InMemoryGraphDatabase

        app = create_dashboard(lambda: InMemoryGraphDatabase())
        callback = app.callback_map["cypher-results.children"]
        inputs = [(item["id"], item["property"]) for item in callback["inputs"]]
        assert inputs == [("cypher-run-btn", "n_clicks")]

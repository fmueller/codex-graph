"""Tests for the dashboard graph_data module and app creation."""

from __future__ import annotations

from codex_graph.dashboard.graph_data import children_to_elements, files_to_elements, nodes_to_elements


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


class TestDashboardAppCreation:
    def test_creates_app(self) -> None:
        from codex_graph.dashboard.app import create_dashboard
        from codex_graph.db.memory import InMemoryGraphDatabase

        db = InMemoryGraphDatabase()
        app = create_dashboard(db)
        assert app is not None

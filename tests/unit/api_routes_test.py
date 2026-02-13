"""Tests for the FastAPI routes using an in-memory database."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from codex_graph.api.app import create_app
from codex_graph.api.dependencies import get_database
from codex_graph.core.ports.database import GraphDatabase
from codex_graph.db.memory import InMemoryGraphDatabase


@pytest.fixture
def db() -> InMemoryGraphDatabase:
    return InMemoryGraphDatabase()


@pytest.fixture
def client(db: InMemoryGraphDatabase) -> TestClient:
    app = create_app()

    async def _override() -> AsyncIterator[GraphDatabase]:
        yield cast(GraphDatabase, db)

    app.dependency_overrides[get_database] = _override
    return TestClient(app)


class TestHealthRoute:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestIngestRoute:
    def test_ingest_requires_path_or_code(self, client: TestClient) -> None:
        resp = client.post("/ingest", json={})
        assert resp.status_code == 422

    def test_ingest_with_code(self, client: TestClient) -> None:
        resp = client.post("/ingest", json={"code": "x = 1", "language": "python"})
        assert resp.status_code == 200
        data = resp.json()
        assert "file_uuid" in data
        assert data["language"] == "python"

    def test_ingest_with_path(self, client: TestClient, tmp_path: object) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("y = 2\n")
            f.flush()
            fpath = f.name

        try:
            resp = client.post("/ingest", json={"path": fpath})
            assert resp.status_code == 200
            data = resp.json()
            assert data["language"] == "python"
        finally:
            Path(fpath).unlink(missing_ok=True)


class TestQueryFilesRoute:
    def test_files_empty(self, client: TestClient) -> None:
        resp = client.get("/query/files")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_files_after_ingest(self, client: TestClient) -> None:
        client.post("/ingest", json={"code": "a = 1", "language": "python"})
        resp = client.get("/query/files")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert "full_path" in rows[0]


class TestQueryNodeTypesRoute:
    def test_node_types_empty(self, client: TestClient) -> None:
        resp = client.get("/query/node-types")
        assert resp.status_code == 200
        assert resp.json() == []


class TestQueryNodesRoute:
    def test_nodes_requires_type(self, client: TestClient) -> None:
        resp = client.get("/query/nodes")
        assert resp.status_code == 422

    def test_nodes_empty(self, client: TestClient) -> None:
        resp = client.get("/query/nodes", params={"type": "function_definition"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestQueryChildrenRoute:
    def test_children_requires_span_key(self, client: TestClient) -> None:
        resp = client.get("/query/children")
        assert resp.status_code == 422

    def test_children_empty(self, client: TestClient) -> None:
        resp = client.get("/query/children", params={"span_key": "test::foo::0:0"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestCypherRoute:
    def test_cypher_returns_rows(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "MATCH (n) RETURN n LIMIT 1", "columns": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data

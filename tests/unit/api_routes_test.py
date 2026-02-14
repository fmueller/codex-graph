"""Tests for the FastAPI routes using an in-memory database."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from codex_graph.api.app import create_app
from codex_graph.api.dependencies import get_database
from codex_graph.api.pagination import InvalidCursorError, decode_cursor, encode_cursor
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


def _ingest(client: TestClient, code: str = "x = 1", language: str = "python") -> dict[str, Any]:
    """Helper: POST /files with a JSON:API create envelope."""
    resp = client.post(
        "/files",
        json={
            "data": {
                "type": "files",
                "attributes": {"code": code, "language": language},
            },
        },
    )
    assert resp.status_code == 201, resp.text
    result: dict[str, Any] = resp.json()
    return result


class TestRootRoute:
    def test_root_returns_discovery(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["jsonapi"]["version"] == "1.0"
        assert "files" in body["links"]
        assert "ast-nodes" in body["links"]


class TestLivenessRoute:
    def test_liveness_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/healthz/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestFilesResource:
    def test_files_list_empty(self, client: TestClient) -> None:
        resp = client.get("/files")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["jsonapi"]["version"] == "1.0"

    def test_create_file_requires_path_or_code(self, client: TestClient) -> None:
        resp = client.post(
            "/files",
            json={
                "data": {
                    "type": "files",
                    "attributes": {},
                },
            },
        )
        # Should fail because neither path nor code is provided
        assert resp.status_code in (400, 422)

    def test_create_file_with_code(self, client: TestClient) -> None:
        body = _ingest(client)
        data = body["data"]
        assert data["type"] == "files"
        assert "id" in data
        assert data["attributes"]["language"] == "python"

    def test_create_file_with_path(self, client: TestClient) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("y = 2\n")
            f.flush()
            fpath = f.name

        try:
            resp = client.post(
                "/files",
                json={
                    "data": {
                        "type": "files",
                        "attributes": {"path": fpath},
                    },
                },
            )
            assert resp.status_code == 201
            data = resp.json()["data"]
            assert data["attributes"]["language"] == "python"
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_files_list_after_ingest(self, client: TestClient) -> None:
        _ingest(client)
        resp = client.get("/files")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["type"] == "files"
        assert "full_path" in body["data"][0]["attributes"]


class TestAstNodesResource:
    def test_ast_nodes_list_empty(self, client: TestClient) -> None:
        resp = client.get("/ast-nodes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_ast_nodes_list_with_filter(self, client: TestClient) -> None:
        resp = client.get("/ast-nodes", params={"filter[type]": "function_definition"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []


class TestStatisticsRoute:
    def test_statistics_returns_flat_json(self, client: TestClient) -> None:
        resp = client.get("/statistics")
        assert resp.status_code == 200
        body = resp.json()
        assert "counts" in body
        assert "languages" in body
        assert "node_types" in body
        assert "meta" not in body


class TestCypherRoute:
    def test_cypher_returns_rows(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "MATCH (n) RETURN n LIMIT 1", "columns": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data


class TestCursorPagination:
    def test_encode_decode_cursor_roundtrip(self) -> None:
        cursor = encode_cursor("/some/path.py", "abc-123")
        sort_val, id_val = decode_cursor(cursor)
        assert sort_val == "/some/path.py"
        assert id_val == "abc-123"

    def test_files_default_pagination_no_stale_meta(self, client: TestClient) -> None:
        resp = client.get("/files")
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" not in body

    def test_files_pagination_links_null_when_no_data(self, client: TestClient) -> None:
        resp = client.get("/files")
        body = resp.json()
        links = body.get("links", {})
        assert links.get("next") is None
        assert links.get("prev") is None

    def test_files_page_size_limits_results(self, client: TestClient) -> None:
        # Ingest 3 files
        _ingest(client, code="a = 1")
        _ingest(client, code="b = 2")
        _ingest(client, code="c = 3")

        resp = client.get("/files", params={"page[size]": "2"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        # First page with more: next present, prev null
        assert body["links"]["next"] is not None
        assert body["links"]["prev"] is None

    def test_files_page_after_returns_next_page(self, client: TestClient) -> None:
        _ingest(client, code="a = 1")
        _ingest(client, code="b = 2")
        _ingest(client, code="c = 3")

        # Get first page
        resp1 = client.get("/files", params={"page[size]": "2"})
        body1 = resp1.json()
        assert len(body1["data"]) == 2
        next_link = body1["links"]["next"]
        assert next_link is not None
        assert body1["links"]["prev"] is None  # first page has no prev

        # Follow cursor to next page (last page)
        resp2 = client.get(next_link)
        body2 = resp2.json()
        assert len(body2["data"]) == 1
        assert body2["links"]["next"] is None  # no more forward
        assert body2["links"]["prev"] is not None  # can go back

        # Verify no overlap between pages
        ids1 = {d["id"] for d in body1["data"]}
        ids2 = {d["id"] for d in body2["data"]}
        assert ids1.isdisjoint(ids2)

    def test_files_page_before_returns_prev_page(self, client: TestClient) -> None:
        _ingest(client, code="a = 1")
        _ingest(client, code="b = 2")
        _ingest(client, code="c = 3")

        # Get first page
        resp1 = client.get("/files", params={"page[size]": "2"})
        body1 = resp1.json()
        next_link = body1["links"]["next"]

        # Get second page
        resp2 = client.get(next_link)
        body2 = resp2.json()
        prev_link = body2["links"]["prev"]
        assert prev_link is not None

        # Go back via prev link (backward navigation)
        resp3 = client.get(prev_link)
        body3 = resp3.json()
        assert len(body3["data"]) == 2
        # Backward page: next should be present (items exist past the before cursor)
        assert body3["links"]["next"] is not None

    def test_files_cursor_past_end_returns_empty(self, client: TestClient) -> None:
        _ingest(client, code="a = 1")

        # Create a cursor past the end
        cursor = encode_cursor("\xff" * 100, "\xff" * 100)
        resp = client.get("/files", params={"page[size]": "10", "page[after]": cursor})
        body = resp.json()
        assert body["data"] == []
        assert body["links"]["next"] is None
        assert body["links"]["prev"] is None
        assert "meta" not in body

    def test_ast_nodes_default_pagination_no_stale_meta(self, client: TestClient) -> None:
        resp = client.get("/ast-nodes")
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" not in body

    def test_files_invalid_cursor_returns_error(self, client: TestClient) -> None:
        resp = client.get("/files", params={"page[after]": "not-a-valid-cursor!!!"})
        assert resp.status_code == 400

    def test_files_non_numeric_page_size_returns_error(self, client: TestClient) -> None:
        _ingest(client, code="a = 1")
        resp = client.get("/files", params={"page[size]": "abc"})
        # Framework rejects non-numeric page size before our handler
        assert resp.status_code in (400, 422)


class TestFileGetById:
    def test_get_file_by_id(self, client: TestClient) -> None:
        body = _ingest(client)
        file_id = body["data"]["id"]

        resp = client.get(f"/files/{file_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == file_id
        assert data["type"] == "files"
        assert data["attributes"]["language"] == "python"
        assert "full_path" in data["attributes"]

    def test_get_file_not_found(self, client: TestClient) -> None:
        resp = client.get("/files/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestAstNodeGetById:
    def test_get_ast_node_by_id(self, client: TestClient, db: InMemoryGraphDatabase) -> None:
        _ingest(client, code="x = 1")

        # Retrieve a span_key from the in-memory DB
        assert len(db.ast_nodes) > 0
        sample_node = next(iter(db.ast_nodes.values()))
        span_key = sample_node.span_key

        resp = client.get(f"/ast-nodes/{span_key}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == span_key
        assert data["type"] == "ast-nodes"
        assert "start_byte" in data["attributes"]

    def test_get_ast_node_not_found(self, client: TestClient) -> None:
        resp = client.get("/ast-nodes/nonexistent-span-key")
        assert resp.status_code == 404


class TestReadinessRoute:
    def test_readiness_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/healthz/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] == "up"


class TestCypherReadOnlyGuard:
    def test_cypher_rejects_create(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "CREATE (n:Foo) RETURN n"})
        assert resp.status_code == 400

    def test_cypher_rejects_delete(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "MATCH (n) DELETE n"})
        assert resp.status_code == 400

    def test_cypher_rejects_set(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "MATCH (n) SET n.x = 1 RETURN n"})
        assert resp.status_code == 400

    def test_cypher_rejects_merge(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "MERGE (n:Foo) RETURN n"})
        assert resp.status_code == 400

    def test_cypher_allows_match(self, client: TestClient) -> None:
        resp = client.post("/query/cypher", json={"query": "MATCH (n) RETURN n LIMIT 1", "columns": 1})
        assert resp.status_code == 200


class TestDecodeCursorError:
    def test_decode_cursor_malformed_raises(self) -> None:
        with pytest.raises(InvalidCursorError):
            decode_cursor("not-valid-base64!!!")

    def test_decode_cursor_missing_keys_raises(self) -> None:
        import base64
        import json

        bad_payload = base64.urlsafe_b64encode(json.dumps({"x": 1}).encode()).decode()
        with pytest.raises(InvalidCursorError):
            decode_cursor(bad_payload)

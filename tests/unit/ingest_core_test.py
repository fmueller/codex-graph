"""Unit tests for core ingest orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from codex_graph.core.ingest import run_ingest
from codex_graph.models import FileAst


class _DummyDatabase:
    def __init__(self) -> None:
        self.persist_file_path: str | None = None
        self.persist_file_ast_path: str | None = None
        self.persist_file_ast_value: Any = None

    async def persist_file(self, path: str) -> str:
        self.persist_file_path = path
        return "file-uuid"

    async def persist_file_ast(self, fa: FileAst, file_path: str) -> None:
        self.persist_file_ast_path = file_path
        self.persist_file_ast_value = fa

    async def ensure_ready(self) -> None:
        return None

    async def fetch_cypher(self, cypher: str, columns: int | None = None) -> list[tuple[Any, ...]]:
        return []

    async def list_files(self, limit: int = 50) -> list[tuple[str, str, str, str]]:
        return []

    async def list_files_cursor(
        self,
        limit: int = 50,
        after_path: str | None = None,
        after_id: str | None = None,
        before_path: str | None = None,
        before_id: str | None = None,
    ) -> list[tuple[str, str, str, str]]:
        return []

    async def get_file_by_id(self, file_uuid: str) -> tuple[str, str, str, str] | None:
        return None

    async def get_language_for_file(self, file_uuid: str) -> str:
        return ""

    async def get_languages_for_files(self, file_uuids: list[str]) -> dict[str, str]:
        return {}

    async def get_node_details(self, span_keys: list[str]) -> dict[str, tuple[Any, ...]]:
        return {}

    async def ping(self) -> bool:
        return True

    async def dispose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_ingest_resolves_path_before_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "pkg" / "sample.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("x = 1\n", encoding="utf-8")

    rel_path = os.path.relpath(file_path, Path.cwd())
    db = _DummyDatabase()
    fake_ast = object()

    monkeypatch.setattr("codex_graph.core.ingest.resolve_language", lambda *_: "python")
    monkeypatch.setattr("codex_graph.core.ingest.extract_ast_from_file", lambda *_: fake_ast)

    file_uuid, language = await run_ingest(db, path=rel_path)

    expected = str(file_path.resolve())
    assert file_uuid == "file-uuid"
    assert language == "python"
    assert db.persist_file_path == expected
    assert db.persist_file_ast_path == expected
    assert db.persist_file_ast_value is fake_ast

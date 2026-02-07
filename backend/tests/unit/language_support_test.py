"""Unit tests for language detection and normalization."""

from pathlib import Path

import pytest

from codex_graph.main import (
    _detect_language_from_path,
    _extract_ast_from_source,
    _normalize_language,
    _resolve_language,
)


def test_detects_language_from_extension() -> None:
    cases = {
        "main.py": "python",
        "main.go": "go",
        "main.ts": "typescript",
        "main.tsx": "tsx",
        "main.js": "javascript",
        "main.java": "java",
        "main.html": "html",
        "main.css": "css",
        "main.md": "markdown",
        "main.yaml": "yaml",
        "main.json": "json",
        "main.toml": "toml",
        "main.rs": "rust",
        "main.rb": "ruby",
        "main.c": "c",
        "main.cpp": "cpp",
        "main.cs": "csharp",
    }
    for filename, expected in cases.items():
        assert _detect_language_from_path(Path(filename)) == expected


def test_normalizes_language_aliases() -> None:
    cases = {
        "PY": "python",
        "py": "python",
        "JS": "javascript",
        "c++": "cpp",
        "c#": "csharp",
        "golang": "go",
        "rb": "ruby",
        "rs": "rust",
        "md": "markdown",
    }
    for alias, expected in cases.items():
        assert _normalize_language(alias) == expected


def test_resolve_language_requires_input() -> None:
    with pytest.raises(ValueError, match="Language must be provided"):
        _resolve_language(None, None)


def test_extracts_ast_from_source_with_language() -> None:
    file_uuid = "test-source-uuid"
    ast = _extract_ast_from_source(b"const x = 1;", file_uuid, "javascript")
    assert ast.language == "javascript"
    assert ast.ast.type == "program"

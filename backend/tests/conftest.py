"""Shared fixtures for tests."""

from pathlib import Path
from typing import Any

import pytest
from tree_sitter import Language, Parser, Query
from tree_sitter_language_pack import get_language, get_parser


@pytest.fixture
def queries_dir() -> Path:
    """Return the path to the queries directory."""
    return Path(__file__).parent.parent / "src" / "codex_graph" / "queries"


@pytest.fixture
def python_parser() -> Parser:
    """Return a tree-sitter parser for Python."""
    return get_parser("python")


@pytest.fixture
def go_parser() -> Parser:
    """Return a tree-sitter parser for Go."""
    return get_parser("go")


@pytest.fixture
def python_language() -> Language:
    """Return the tree-sitter Python language."""
    return get_language("python")


@pytest.fixture
def go_language() -> Language:
    """Return the tree-sitter Go language."""
    return get_language("go")


@pytest.fixture
def python_detailed_query(queries_dir: Path, python_language: Any) -> Query:
    """Load the Python detailed query."""
    query_text = (queries_dir / "python_detailed.scm").read_text()
    return Query(python_language, query_text)


@pytest.fixture
def python_high_level_query(queries_dir: Path, python_language: Any) -> Query:
    """Load the Python high-level query."""
    query_text = (queries_dir / "python_high_level.scm").read_text()
    return Query(python_language, query_text)


@pytest.fixture
def go_detailed_query(queries_dir: Path, go_language: Any) -> Query:
    """Load the Go detailed query."""
    query_text = (queries_dir / "go_detailed.scm").read_text()
    return Query(go_language, query_text)


@pytest.fixture
def go_high_level_query(queries_dir: Path, go_language: Any) -> Query:
    """Load the Go high-level query."""
    query_text = (queries_dir / "go_high_level.scm").read_text()
    return Query(go_language, query_text)

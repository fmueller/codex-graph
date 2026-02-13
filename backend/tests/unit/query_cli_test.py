"""Tests for the query CLI subcommands and helpers."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from codex_graph.main import _build_parser, _print_table, _run_query

# -- Step 1: CLI argument parsing tests --


def test_ingest_subcommand_parses_path() -> None:
    parser = _build_parser()
    args = parser.parse_args(["ingest", "foo.py"])
    assert args.command == "ingest"
    assert args.path == "foo.py"


def test_ingest_subcommand_parses_code_and_language() -> None:
    parser = _build_parser()
    args = parser.parse_args(["ingest", "--code", "x=1", "--language", "python"])
    assert args.command == "ingest"
    assert args.code == "x=1"
    assert args.language == "python"


def test_query_files_subcommand() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "files"])
    assert args.command == "query"
    assert args.query_command == "files"


def test_query_files_accepts_limit() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "files", "--limit", "10"])
    assert args.limit == 10


def test_query_node_types_subcommand() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "node-types"])
    assert args.command == "query"
    assert args.query_command == "node-types"


def test_query_node_types_accepts_file() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "node-types", "--file", "src/main.py"])
    assert args.file == "src/main.py"


def test_query_nodes_requires_type() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["query", "nodes"])


def test_query_nodes_parses_type() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "nodes", "--type", "function_definition"])
    assert args.command == "query"
    assert args.query_command == "nodes"
    assert args.type == "function_definition"


def test_query_children_requires_span_key() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["query", "children"])


def test_query_children_parses_span_key() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "children", "--span-key", "abc:def:0:10"])
    assert args.command == "query"
    assert args.query_command == "children"
    assert args.span_key == "abc:def:0:10"


def test_query_cypher_parses_query_string() -> None:
    parser = _build_parser()
    args = parser.parse_args(["query", "cypher", "MATCH (n) RETURN n"])
    assert args.command == "query"
    assert args.query_command == "cypher"
    assert args.query_string == "MATCH (n) RETURN n"


def test_no_subcommand_exits() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# -- Step 2: Table formatting tests --


def test_format_table_basic(capsys: pytest.CaptureFixture[str]) -> None:
    _print_table(["name", "age"], [("Alice", "30"), ("Bob", "25")])
    out = capsys.readouterr().out
    lines = out.strip().split("\n")
    # Header, separator, 2 data rows, footer
    assert len(lines) == 5
    assert "name" in lines[0]
    assert "age" in lines[0]
    assert "Alice" in lines[2]
    assert "(2 rows)" in lines[4]


def test_format_table_empty_rows(capsys: pytest.CaptureFixture[str]) -> None:
    _print_table(["id", "path"], [])
    out = capsys.readouterr().out
    assert "(0 rows)" in out


def test_format_table_truncates_long_values(capsys: pytest.CaptureFixture[str]) -> None:
    long_val = "x" * 200
    _print_table(["col"], [(long_val,)])
    out = capsys.readouterr().out
    # Should not contain the full 200 chars
    assert "..." in out
    assert long_val not in out


# -- Step 3: Query handler tests (mock db) --


def test_query_files_calls_list_files(capsys: pytest.CaptureFixture[str]) -> None:
    mock_db = AsyncMock()
    mock_db.list_files.return_value = [
        ("uuid-1", "/tmp/foo.py", ".py", "abc123"),
    ]

    parser = _build_parser()
    args = parser.parse_args(["query", "files", "--limit", "10"])

    asyncio.run(_run_query(args, mock_db))
    mock_db.list_files.assert_called_once_with(10)
    out = capsys.readouterr().out
    assert "uuid-1" in out
    assert "/tmp/foo.py" in out


def test_query_node_types_builds_correct_cypher(capsys: pytest.CaptureFixture[str]) -> None:
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [("function_definition",), ("class_definition",)]

    parser = _build_parser()
    args = parser.parse_args(["query", "node-types"])

    asyncio.run(_run_query(args, mock_db))
    cypher_arg = mock_db.fetch_cypher.call_args[0][0]
    assert "MATCH" in cypher_arg
    assert "AstNode" in cypher_arg
    assert "DISTINCT" in cypher_arg


def test_query_node_types_with_file_filter(capsys: pytest.CaptureFixture[str]) -> None:
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [("identifier",)]

    parser = _build_parser()
    args = parser.parse_args(["query", "node-types", "--file", "src/main.py"])

    asyncio.run(_run_query(args, mock_db))
    cypher_arg = mock_db.fetch_cypher.call_args[0][0]
    assert "OCCURS_IN" in cypher_arg
    assert "FileVersion" in cypher_arg
    assert "src/main.py" in cypher_arg


def test_query_nodes_by_type(capsys: pytest.CaptureFixture[str]) -> None:
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [
        ("span1", "function_definition", "0", "50"),
    ]

    parser = _build_parser()
    args = parser.parse_args(["query", "nodes", "--type", "function_definition"])

    asyncio.run(_run_query(args, mock_db))
    cypher_arg = mock_db.fetch_cypher.call_args[0][0]
    assert "function_definition" in cypher_arg
    assert "AstNode" in cypher_arg
    assert mock_db.fetch_cypher.call_args[1]["columns"] == 4


def test_query_children_by_span_key(capsys: pytest.CaptureFixture[str]) -> None:
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [
        ("child_span_1", "identifier", "0"),
    ]

    parser = _build_parser()
    args = parser.parse_args(["query", "children", "--span-key", "uuid:type:0:10"])

    asyncio.run(_run_query(args, mock_db))
    cypher_arg = mock_db.fetch_cypher.call_args[0][0]
    assert "PARENT_OF" in cypher_arg
    assert "uuid:type:0:10" in cypher_arg
    assert mock_db.fetch_cypher.call_args[1]["columns"] == 3


def test_query_cypher_passthrough(capsys: pytest.CaptureFixture[str]) -> None:
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [("hello",)]

    parser = _build_parser()
    args = parser.parse_args(["query", "cypher", "MATCH (n) RETURN n.type LIMIT 5"])

    asyncio.run(_run_query(args, mock_db))
    mock_db.fetch_cypher.assert_called_once_with("MATCH (n) RETURN n.type LIMIT 5", columns=1)


# -- Step 4: db.py method existence tests --


def test_postgres_db_has_fetch_cypher() -> None:
    from codex_graph.db import PostgresGraphDatabase

    assert hasattr(PostgresGraphDatabase, "fetch_cypher")
    assert callable(PostgresGraphDatabase.fetch_cypher)


def test_postgres_db_has_list_files() -> None:
    from codex_graph.db import PostgresGraphDatabase

    assert hasattr(PostgresGraphDatabase, "list_files")
    assert callable(PostgresGraphDatabase.list_files)


def test_postgres_db_has_ensure_ready() -> None:
    from codex_graph.db import PostgresGraphDatabase

    assert hasattr(PostgresGraphDatabase, "ensure_ready")
    assert callable(PostgresGraphDatabase.ensure_ready)

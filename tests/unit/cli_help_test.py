"""Tests that -h is accepted as a help flag on all CLI commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from codex_graph.cli.app import app

runner = CliRunner()


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["db"],
        ["db", "start"],
        ["query"],
        ["serve"],
    ],
    ids=["root", "db", "db-start", "query", "serve"],
)
def test_short_help_flag(args: list[str]) -> None:
    result = runner.invoke(app, [*args, "-h"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_query_cypher_passes_columns_none_by_default() -> None:
    """CLI 'query cypher' without --columns passes columns=None to core."""
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [("ok",)]

    with patch("codex_graph.cli.query._get_database", return_value=mock_db):
        result = runner.invoke(app, ["query", "cypher", "MATCH (n) RETURN n"])

    assert result.exit_code == 0
    mock_db.fetch_cypher.assert_called_once()
    _, kwargs = mock_db.fetch_cypher.call_args
    assert kwargs["columns"] is None


def test_query_cypher_passes_explicit_columns() -> None:
    """CLI 'query cypher --columns 3' passes columns=3 to core."""
    mock_db = AsyncMock()
    mock_db.fetch_cypher.return_value = [("a", "b", "c")]

    with patch("codex_graph.cli.query._get_database", return_value=mock_db):
        result = runner.invoke(app, ["query", "cypher", "MATCH (n) RETURN n.a, n.b, n.c", "--columns", "3"])

    assert result.exit_code == 0
    mock_db.fetch_cypher.assert_called_once()
    _, kwargs = mock_db.fetch_cypher.call_args
    assert kwargs["columns"] == 3

"""Tests that -h is accepted as a help flag on all CLI commands."""

from __future__ import annotations

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

"""Tests for the CLI db commands."""

from __future__ import annotations

from unittest.mock import patch

from codex_graph.cli.db import _container_state, _docker_available


class TestDockerAvailable:
    def test_returns_true_when_docker_found(self) -> None:
        with patch("codex_graph.cli.db.shutil.which", return_value="/usr/bin/docker"):
            assert _docker_available() is True

    def test_returns_false_when_docker_missing(self) -> None:
        with patch("codex_graph.cli.db.shutil.which", return_value=None):
            assert _docker_available() is False


class TestContainerState:
    def test_returns_none_when_not_found(self) -> None:
        with patch("codex_graph.cli.db.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            assert _container_state() is None

    def test_returns_running(self) -> None:
        with patch("codex_graph.cli.db.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "running\n"
            assert _container_state() == "running"

    def test_returns_exited(self) -> None:
        with patch("codex_graph.cli.db.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "exited\n"
            assert _container_state() == "exited"

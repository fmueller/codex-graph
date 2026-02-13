"""Shared fixtures and helpers for tests."""

import logging
import subprocess
import warnings
from pathlib import Path
from typing import Any

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
from tree_sitter import Language, Parser, Query
from tree_sitter_language_pack import get_language, get_parser

from alembic import command
from alembic.config import Config
from codex_graph.db import InMemoryGraphDatabase

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Auto-marker: tag tests as "unit" or "integration" based on directory
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        test_path = Path(str(item.fspath))
        rel = test_path.relative_to(_REPO_ROOT / "tests")
        parts = rel.parts
        if parts and parts[0] == "integration":
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


# ---------------------------------------------------------------------------
# AgeTestBase — helpers for integration tests that need the AGE container
# ---------------------------------------------------------------------------

_BUILT_IMAGE_TAG: str | None = None


class AgeTestBase:
    @staticmethod
    def build_database_image() -> str:
        global _BUILT_IMAGE_TAG  # noqa: PLW0603
        if _BUILT_IMAGE_TAG is not None:
            return _BUILT_IMAGE_TAG
        tag = "codex-graph-db-test:latest"
        logger.info("Building database image %s from %s …", tag, _REPO_ROOT / "docker" / "Dockerfile.database")
        subprocess.run(
            ["docker", "build", "-f", "docker/Dockerfile.database", "-t", tag, "."],
            cwd=str(_REPO_ROOT),
            check=True,
            capture_output=True,
        )
        _BUILT_IMAGE_TAG = tag
        return tag

    @staticmethod
    def create_container(image_tag: str) -> DockerContainer:
        return DockerContainer(image_tag).with_exposed_ports(5432).with_env("POSTGRES_PASSWORD", "postgres")

    @staticmethod
    def get_alembic_config() -> Config:
        ini_path = str(_REPO_ROOT / "alembic.ini")
        cfg = Config(ini_path)
        cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
        return cfg

    @staticmethod
    def run_migrations(connection_url: str) -> None:
        cfg = AgeTestBase.get_alembic_config()
        cfg.set_main_option("sqlalchemy.url", connection_url)
        command.upgrade(cfg, "head")

    @staticmethod
    def cleanup_migrations(connection_url: str) -> None:
        cfg = AgeTestBase.get_alembic_config()
        cfg.set_main_option("sqlalchemy.url", connection_url)
        command.downgrade(cfg, "base")

    @staticmethod
    def wait_for_postgres(container: DockerContainer) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            wait_for_logs(container, "database system is ready to accept connections", timeout=60)


# ---------------------------------------------------------------------------
# Shared unit-test fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture
def in_memory_db() -> InMemoryGraphDatabase:
    return InMemoryGraphDatabase()

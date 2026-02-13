"""Session-scoped fixtures for integration tests."""

from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.core.container import DockerContainer

from alembic.config import Config
from codex_graph.db import PostgresGraphDatabase
from tests.conftest import AgeTestBase


@pytest.fixture(scope="session")
def db_image() -> str:
    """Build the database Docker image once per session."""
    return AgeTestBase.build_database_image()


@pytest.fixture(scope="session")
def postgres_container(db_image: str) -> Generator[DockerContainer, None, None]:
    """Start the AGE+pgvector container for the session."""
    container = AgeTestBase.create_container(db_image)
    container.start()
    AgeTestBase.wait_for_postgres(container)
    yield container
    container.stop()


@pytest.fixture(scope="session")
def test_db_url(postgres_container: DockerContainer) -> str:
    """Async connection URL for the test database."""
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://postgres:postgres@{host}:{port}/postgres"


@pytest.fixture(scope="session")
def alembic_config(test_db_url: str) -> Config:
    """Alembic config pointed at the test database."""
    cfg = AgeTestBase.get_alembic_config()
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    return cfg


@pytest.fixture(scope="session")
def _run_migrations(alembic_config: Config, test_db_url: str) -> Generator[None, None, None]:
    """Run migrations once per session, cleanup on teardown."""
    AgeTestBase.run_migrations(test_db_url)
    yield
    AgeTestBase.cleanup_migrations(test_db_url)


@pytest_asyncio.fixture
async def database(_run_migrations: None, test_db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Per-test engine so each event loop gets its own connection pool."""
    engine = create_async_engine(test_db_url, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(database: AsyncEngine) -> AsyncGenerator[PostgresGraphDatabase, None]:
    """Per-test PostgresGraphDatabase instance."""
    instance = PostgresGraphDatabase(database)
    await instance.ensure_ready()
    yield instance

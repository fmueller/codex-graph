import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def get_engine() -> AsyncEngine:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    )
    return create_async_engine(db_url, future=True)

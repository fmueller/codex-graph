import contextlib
import os
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def get_engine() -> AsyncEngine:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    )
    engine = create_async_engine(db_url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _load_age(dbapi_conn: Any, connection_record: Any) -> None:
        cur = dbapi_conn.cursor()
        with contextlib.suppress(Exception):
            cur.execute("LOAD 'age'")
        cur.execute('SET search_path = public, ag_catalog, "$user"')
        cur.close()

    return engine

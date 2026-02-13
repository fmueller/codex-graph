from fastapi import FastAPI

from codex_graph.api.lifespan import lifespan
from codex_graph.api.routes.health import router as health_router
from codex_graph.api.routes.ingest import router as ingest_router
from codex_graph.api.routes.query import router as query_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Codex Graph API",
        description="Parse, store, and query code ASTs in a graph database.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    return app

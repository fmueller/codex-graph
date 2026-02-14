from __future__ import annotations

from fastapi import FastAPI
from fastapi_jsonapi import ApplicationBuilder
from fastapi_jsonapi.views import Operation

from codex_graph.api.lifespan import lifespan
from codex_graph.api.middleware import CursorPaginationMiddleware
from codex_graph.api.models import AstNodeModel, FileModel
from codex_graph.api.routes.cypher import router as cypher_router
from codex_graph.api.routes.health import router as health_router
from codex_graph.api.routes.root import router as root_router
from codex_graph.api.routes.statistics import router as statistics_router
from codex_graph.api.schemas import AstNodeSchema, FileCreateSchema, FileSchema
from codex_graph.api.views import AstNodeView, FileView


def create_app() -> FastAPI:
    app = FastAPI(
        title="Codex Graph API",
        description="Parse, store, and query code ASTs in a graph database.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # JSON:API resources via FastAPI-JSONAPI
    builder = ApplicationBuilder(app)
    builder.add_resource(
        path="/files",
        tags=["files"],
        view=FileView,
        model=FileModel,
        schema=FileSchema,
        schema_in_post=FileCreateSchema,
        resource_type="files",
        ending_slash=False,
        operations=[Operation.GET_LIST, Operation.GET, Operation.CREATE],
    )
    builder.add_resource(
        path="/ast-nodes",
        tags=["ast-nodes"],
        view=AstNodeView,
        model=AstNodeModel,
        schema=AstNodeSchema,
        resource_type="ast-nodes",
        ending_slash=False,
        operations=[Operation.GET_LIST, Operation.GET],
    )
    builder.initialize()

    # Cursor-based pagination link injection
    app.add_middleware(CursorPaginationMiddleware)

    # Custom (non-JSON:API) endpoints
    app.include_router(root_router, include_in_schema=False)
    app.include_router(health_router, include_in_schema=False)
    app.include_router(cypher_router)
    app.include_router(statistics_router)

    return app

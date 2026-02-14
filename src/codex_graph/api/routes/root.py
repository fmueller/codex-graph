from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root() -> dict[str, Any]:
    """Root discovery endpoint — API directory for programmatic and human clients."""
    return {
        "jsonapi": {"version": "1.0"},
        "meta": {
            "title": "Codex Graph API",
            "description": "Parse, store, and query code ASTs in a graph database.",
            "version": "0.1.0",
        },
        "links": {
            "self": "/",
            "files": "/files",
            "ast-nodes": "/ast-nodes",
            "statistics": "/statistics",
            "cypher": "/query/cypher",
            "openapi": "/openapi.json",
            "docs": "/docs",
        },
    }

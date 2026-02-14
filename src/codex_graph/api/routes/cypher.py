from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from codex_graph.api.dependencies import get_database
from codex_graph.api.schemas import CypherRequest, CypherResponse
from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import query_cypher as _query_cypher

router = APIRouter(prefix="/query", tags=["query"])

_WRITE_PATTERN = re.compile(r"\b(CREATE|SET|DELETE|DETACH|MERGE|REMOVE|DROP|ALTER)\b", re.IGNORECASE)


@router.post("/cypher", response_model=CypherResponse)
async def cypher(
    body: CypherRequest,
    db: GraphDatabase = Depends(get_database),
) -> CypherResponse:
    """Execute a **read-only** Cypher query. Write operations are rejected."""
    if _WRITE_PATTERN.search(body.query):
        raise HTTPException(status_code=400, detail="Write operations are not allowed. This endpoint is read-only.")
    await db.ensure_ready()
    rows = await _query_cypher(db, body.query, body.columns)
    return CypherResponse(rows=[[str(v) for v in row] for row in rows])

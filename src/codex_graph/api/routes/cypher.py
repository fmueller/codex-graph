from __future__ import annotations

from fastapi import APIRouter, Depends

from codex_graph.api.dependencies import get_database
from codex_graph.api.schemas import CypherRequest, CypherResponse
from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import query_cypher as _query_cypher

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/cypher", response_model=CypherResponse)
async def cypher(
    body: CypherRequest,
    db: GraphDatabase = Depends(get_database),
) -> CypherResponse:
    await db.ensure_ready()
    rows = await _query_cypher(db, body.query, body.columns)
    return CypherResponse(rows=[[str(v) for v in row] for row in rows])

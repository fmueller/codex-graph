from fastapi import APIRouter, Depends, Query

from codex_graph.api.dependencies import get_database
from codex_graph.api.schemas import ChildRow, CypherRequest, CypherResponse, FileRow, NodeRow, NodeTypeRow
from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import (
    query_children as _query_children,
)
from codex_graph.core.query import (
    query_cypher as _query_cypher,
)
from codex_graph.core.query import (
    query_files as _query_files,
)
from codex_graph.core.query import (
    query_node_types as _query_node_types,
)
from codex_graph.core.query import (
    query_nodes as _query_nodes,
)

router = APIRouter(prefix="/query", tags=["query"])


@router.get("/files", response_model=list[FileRow])
async def files(
    limit: int = Query(50, ge=1),
    db: GraphDatabase = Depends(get_database),
) -> list[FileRow]:
    await db.ensure_ready()
    rows = await _query_files(db, limit)
    return [FileRow(id=r[0], full_path=r[1], suffix=r[2], content_hash=r[3]) for r in rows]


@router.get("/node-types", response_model=list[NodeTypeRow])
async def node_types(
    file: str | None = Query(None),
    limit: int = Query(50, ge=1),
    db: GraphDatabase = Depends(get_database),
) -> list[NodeTypeRow]:
    await db.ensure_ready()
    rows = await _query_node_types(db, file, limit)
    return [NodeTypeRow(type=str(r[0])) for r in rows]


@router.get("/nodes", response_model=list[NodeRow])
async def nodes(
    type: str = Query(...),
    file: str | None = Query(None),
    limit: int = Query(50, ge=1),
    db: GraphDatabase = Depends(get_database),
) -> list[NodeRow]:
    await db.ensure_ready()
    rows = await _query_nodes(db, type, file, limit)
    return [NodeRow(span_key=str(r[0]), type=str(r[1]), start_byte=str(r[2]), end_byte=str(r[3])) for r in rows]


@router.get("/children", response_model=list[ChildRow])
async def children(
    span_key: str = Query(...),
    limit: int = Query(50, ge=1),
    db: GraphDatabase = Depends(get_database),
) -> list[ChildRow]:
    await db.ensure_ready()
    rows = await _query_children(db, span_key, limit)
    return [ChildRow(span_key=str(r[0]), type=str(r[1]), child_index=str(r[2])) for r in rows]


@router.post("/cypher", response_model=CypherResponse)
async def cypher(
    body: CypherRequest,
    db: GraphDatabase = Depends(get_database),
) -> CypherResponse:
    await db.ensure_ready()
    rows = await _query_cypher(db, body.query, body.columns)
    return CypherResponse(rows=[[str(v) for v in row] for row in rows])

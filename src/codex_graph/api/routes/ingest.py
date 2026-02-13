from fastapi import APIRouter, Depends, HTTPException

from codex_graph.api.dependencies import get_database
from codex_graph.api.schemas import IngestRequest, IngestResponse
from codex_graph.core.ingest import run_ingest
from codex_graph.core.ports.database import GraphDatabase

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    db: GraphDatabase = Depends(get_database),
) -> IngestResponse:
    if body.path is None and body.code is None:
        raise HTTPException(status_code=422, detail="Either 'path' or 'code' must be provided.")

    await db.ensure_ready()
    file_uuid, language = await run_ingest(
        db,
        path=body.path,
        code=body.code,
        language=body.language,
    )
    return IngestResponse(file_uuid=file_uuid, language=language)

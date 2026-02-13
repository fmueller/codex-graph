from fastapi import APIRouter, Depends, Response, status

from codex_graph.api.dependencies import get_database
from codex_graph.api.schemas import HealthResponse, ReadinessResponse
from codex_graph.core.ports.database import GraphDatabase

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get("/healthz/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe — is the process alive?"""
    return HealthResponse()


@router.get("/healthz/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    db: GraphDatabase = Depends(get_database),
) -> ReadinessResponse:
    """Readiness probe — checks DB connectivity."""
    if await db.ping():
        return ReadinessResponse(status="ok", database="up")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="degraded", database="down")

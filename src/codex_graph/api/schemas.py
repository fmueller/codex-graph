from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# --- JSON:API resource schemas (used by FastAPI-JSONAPI ApplicationBuilder) ---


class FileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_path: str
    suffix: str
    content_hash: str
    language: str


class AstNodeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    shape_hash: str
    file_uuid: str


# --- Custom (non-JSON:API) endpoint schemas ---


class FileCreateSchema(BaseModel):
    """POST /files — ingest request attributes."""

    path: str | None = None
    code: str | None = None
    language: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str = "ok"
    database: str = "up"


class CypherRequest(BaseModel):
    query: str
    columns: int | None = None


class CypherResponse(BaseModel):
    rows: list[list[str]]

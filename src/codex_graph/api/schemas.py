from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class IngestRequest(BaseModel):
    path: str | None = None
    code: str | None = None
    language: str | None = None


class IngestResponse(BaseModel):
    file_uuid: str
    language: str


class FileRow(BaseModel):
    id: str
    full_path: str
    suffix: str
    content_hash: str


class NodeTypeRow(BaseModel):
    type: str


class NodeRow(BaseModel):
    span_key: str
    type: str
    start_byte: str
    end_byte: str


class ChildRow(BaseModel):
    span_key: str
    type: str
    child_index: str


class CypherRequest(BaseModel):
    query: str
    columns: int = 1


class CypherResponse(BaseModel):
    rows: list[list[str]]

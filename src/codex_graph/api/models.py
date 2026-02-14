"""Lightweight model objects returned by the custom data layer.

These are NOT Pydantic schemas; they are plain dataclasses whose attributes
are read by FastAPI-JSONAPI (via ``model_validate(..., from_attributes=True)``)
to build JSON:API response envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FileModel:
    id: str
    full_path: str
    suffix: str
    content_hash: str
    language: str


@dataclass
class AstNodeModel:
    id: str
    type: str
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    shape_hash: str
    file_uuid: str

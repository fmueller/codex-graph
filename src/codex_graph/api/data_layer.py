"""Custom BaseDataLayer bridging JSON:API CRUD operations to the GraphDatabase protocol."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi_jsonapi.data_layers.base import BaseDataLayer
from fastapi_jsonapi.data_typing import TypeModel, TypeSchema
from fastapi_jsonapi.exceptions import BadRequest, ObjectNotFound
from fastapi_jsonapi.querystring import QueryStringManager
from fastapi_jsonapi.views import RelationshipRequestInfo

from codex_graph.api.models import AstNodeModel, FileModel
from codex_graph.api.pagination import InvalidCursorError, decode_cursor, encode_cursor, parse_page_params
from codex_graph.core.ingest import run_ingest
from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import (
    query_files as _query_files,
)
from codex_graph.core.query import (
    query_nodes as _query_nodes,
)


def _strip_agtype(val: object) -> str:
    return str(val).strip('"')


def _agtype_int(val: object) -> int:
    s = str(val).strip('"')
    return int(s) if s else 0


class FileDataLayer(BaseDataLayer):
    """Data layer for the ``files`` JSON:API resource."""

    def __init__(
        self,
        request: Request,
        model: type[TypeModel],
        schema: type[TypeSchema],
        resource_type: str,
        db: GraphDatabase | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(request=request, model=model, schema=schema, resource_type=resource_type, **kwargs)
        assert db is not None, "GraphDatabase dependency must be provided"
        self.db = db

    async def get_collection(
        self,
        qs: QueryStringManager,
        view_kwargs: dict[str, Any] | None = None,
        relationship_request_info: RelationshipRequestInfo | None = None,
    ) -> tuple[int, list[Any]]:
        await self.db.ensure_ready()

        after_cursor, before_cursor, size = parse_page_params(self.request)

        after_path: str | None = None
        after_id: str | None = None
        before_path: str | None = None
        before_id: str | None = None

        try:
            if after_cursor:
                after_path, after_id = decode_cursor(after_cursor)
            elif before_cursor:
                before_path, before_id = decode_cursor(before_cursor)
        except InvalidCursorError as exc:
            raise BadRequest(detail=str(exc)) from exc

        # Fetch one extra row to determine if there are more results
        rows = await _query_files(
            self.db,
            limit=size + 1,
            after_path=after_path,
            after_id=after_id,
            before_path=before_path,
            before_id=before_id,
        )

        page = rows[:size]

        # Compute directional pagination flags
        if before_cursor:
            # Backward navigation: extra row means more items further back
            has_next = len(page) > 0  # items exist past the before_cursor
            has_prev = len(rows) > size  # more items further back
        else:
            # Forward navigation (after_cursor or initial request)
            has_next = len(rows) > size
            has_prev = after_cursor is not None and len(page) > 0

        # Fetch languages only for files on the current page
        page_uuids = [str(r[0]) for r in page]
        lang_map = await self.db.get_languages_for_files(page_uuids)

        items = [
            FileModel(
                id=str(r[0]),
                full_path=str(r[1]),
                suffix=str(r[2]),
                content_hash=str(r[3]),
                language=lang_map.get(str(r[0]), ""),
            )
            for r in page
        ]

        # Store pagination state on request for middleware to pick up
        self.request.state.cursor_pagination = {
            "has_next": has_next,
            "has_prev": has_prev,
            "size": size,
            "resource_path": "/files",
        }
        if page:
            first = page[0]
            last = page[-1]
            self.request.state.cursor_pagination["first_cursor"] = encode_cursor(str(first[1]), str(first[0]))
            self.request.state.cursor_pagination["last_cursor"] = encode_cursor(str(last[1]), str(last[0]))

        # Return 0 as count to avoid FastAPI-JSONAPI generating offset-based links
        return 0, items

    async def get_object(
        self,
        view_kwargs: dict[str, Any],
        qs: QueryStringManager | None = None,
        relationship_request_info: RelationshipRequestInfo | None = None,
    ) -> Any:
        await self.db.ensure_ready()
        file_uuid = view_kwargs.get("id", "")

        row = await self.db.get_file_by_id(file_uuid)
        if row is None:
            raise ObjectNotFound(detail=f"File {file_uuid} not found")

        lang = await self.db.get_language_for_file(file_uuid)
        return FileModel(
            id=str(row[0]),
            full_path=str(row[1]),
            suffix=str(row[2]),
            content_hash=str(row[3]),
            language=lang,
        )

    async def create_object(self, data_create: Any, view_kwargs: dict[str, Any]) -> Any:
        await self.db.ensure_ready()
        attrs = data_create.attributes
        path: str | None = getattr(attrs, "path", None)
        code: str | None = getattr(attrs, "code", None)
        language: str | None = getattr(attrs, "language", None)

        if path is None and code is None:
            raise BadRequest(detail="Either 'path' or 'code' must be provided.")

        file_uuid, resolved_language = await run_ingest(
            self.db,
            path=path,
            code=code,
            language=language,
        )

        # Build the created file model
        row = await self.db.get_file_by_id(file_uuid)
        if row is not None:
            return FileModel(
                id=file_uuid,
                full_path=str(row[1]),
                suffix=str(row[2]),
                content_hash=str(row[3]),
                language=resolved_language,
            )

        return FileModel(
            id=file_uuid,
            full_path=path or "",
            suffix="",
            content_hash="",
            language=resolved_language,
        )


class AstNodeDataLayer(BaseDataLayer):
    """Data layer for the ``ast-nodes`` JSON:API resource."""

    def __init__(
        self,
        request: Request,
        model: type[TypeModel],
        schema: type[TypeSchema],
        resource_type: str,
        db: GraphDatabase | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(request=request, model=model, schema=schema, resource_type=resource_type, **kwargs)
        assert db is not None, "GraphDatabase dependency must be provided"
        self.db = db

    async def get_collection(
        self,
        qs: QueryStringManager,
        view_kwargs: dict[str, Any] | None = None,
        relationship_request_info: RelationshipRequestInfo | None = None,
    ) -> tuple[int, list[Any]]:
        await self.db.ensure_ready()

        after_cursor, before_cursor, size = parse_page_params(self.request)

        after_start_byte: int | None = None
        after_span_key: str | None = None
        before_start_byte: int | None = None
        before_span_key: str | None = None

        try:
            if after_cursor:
                sort_val, id_val = decode_cursor(after_cursor)
                after_start_byte = int(sort_val)
                after_span_key = id_val
            elif before_cursor:
                sort_val, id_val = decode_cursor(before_cursor)
                before_start_byte = int(sort_val)
                before_span_key = id_val
        except InvalidCursorError as exc:
            raise BadRequest(detail=str(exc)) from exc

        # Extract filter[type] and filter[file_uuid] from querystring
        node_type: str | None = None
        file_filter: str | None = None
        for f in qs.filters:
            if f.get("name") == "type" and f.get("op") == "eq":
                node_type = str(f["val"])
            elif f.get("name") == "file_uuid" and f.get("op") == "eq":
                file_filter = str(f["val"])

        rows = await _query_nodes(
            self.db,
            node_type or "%",
            file_filter,
            limit=size + 1,
            after_start_byte=after_start_byte,
            after_span_key=after_span_key,
            before_start_byte=before_start_byte,
            before_span_key=before_span_key,
        )

        page = rows[:size]

        # Compute directional pagination flags
        if before_cursor:
            has_next = len(page) > 0
            has_prev = len(rows) > size
        else:
            has_next = len(rows) > size
            has_prev = after_cursor is not None and len(page) > 0

        # query_nodes returns (span_key, type, start_byte, end_byte)
        # Bulk-fetch full detail for all nodes on the page
        span_keys = [_strip_agtype(r[0]) for r in page]
        details = await self.db.get_node_details(span_keys)

        items: list[AstNodeModel] = []
        for r in page:
            span_key = _strip_agtype(r[0])
            d = details.get(span_key)
            if d is not None:
                items.append(
                    AstNodeModel(
                        id=span_key,
                        type=_strip_agtype(d[1]),
                        start_line=_agtype_int(d[2]),
                        start_column=_agtype_int(d[3]),
                        end_line=_agtype_int(d[4]),
                        end_column=_agtype_int(d[5]),
                        start_byte=_agtype_int(d[6]),
                        end_byte=_agtype_int(d[7]),
                        shape_hash=_strip_agtype(d[8]),
                        file_uuid=_strip_agtype(d[9]),
                    )
                )
            else:
                items.append(
                    AstNodeModel(
                        id=span_key,
                        type=_strip_agtype(r[1]),
                        start_byte=_agtype_int(r[2]),
                        end_byte=_agtype_int(r[3]),
                        start_line=0,
                        start_column=0,
                        end_line=0,
                        end_column=0,
                        shape_hash="",
                        file_uuid="",
                    )
                )

        # Store pagination state on request for middleware to pick up
        self.request.state.cursor_pagination = {
            "has_next": has_next,
            "has_prev": has_prev,
            "size": size,
            "resource_path": "/ast-nodes",
        }
        if page:
            first_r = page[0]
            last_r = page[-1]
            first_start = str(_agtype_int(first_r[2]))
            last_start = str(_agtype_int(last_r[2]))
            self.request.state.cursor_pagination["first_cursor"] = encode_cursor(first_start, _strip_agtype(first_r[0]))
            self.request.state.cursor_pagination["last_cursor"] = encode_cursor(last_start, _strip_agtype(last_r[0]))

        return 0, items

    async def get_object(
        self,
        view_kwargs: dict[str, Any],
        qs: QueryStringManager | None = None,
        relationship_request_info: RelationshipRequestInfo | None = None,
    ) -> Any:
        await self.db.ensure_ready()
        span_key = view_kwargs.get("id", "")

        details = await self.db.get_node_details([span_key])
        d = details.get(span_key)
        if d is None:
            raise ObjectNotFound(detail=f"AstNode {span_key} not found")
        return AstNodeModel(
            id=span_key,
            type=_strip_agtype(d[1]),
            start_line=_agtype_int(d[2]),
            start_column=_agtype_int(d[3]),
            end_line=_agtype_int(d[4]),
            end_column=_agtype_int(d[5]),
            start_byte=_agtype_int(d[6]),
            end_byte=_agtype_int(d[7]),
            shape_hash=_strip_agtype(d[8]),
            file_uuid=_strip_agtype(d[9]),
        )

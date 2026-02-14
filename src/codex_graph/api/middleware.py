"""ASGI middleware for injecting cursor-based pagination links into JSON:API responses."""

from __future__ import annotations

import json
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class CursorPaginationMiddleware(BaseHTTPMiddleware):
    """Injects ``links.next`` / ``links.prev`` into JSON:API list responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        pagination_state: dict[str, Any] | None = getattr(request.state, "cursor_pagination", None)
        if pagination_state is None:
            return response

        # Read the response body — BaseHTTPMiddleware always returns a StreamingResponse
        body_bytes = b""
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is not None:
            async for chunk in body_iterator:
                if isinstance(chunk, str):
                    body_bytes += chunk.encode()
                else:
                    body_bytes += chunk
        elif hasattr(response, "body"):
            body_bytes = bytes(response.body)

        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(content=body_bytes, status_code=response.status_code, headers=dict(response.headers))

        if not isinstance(body, dict) or "data" not in body:
            return Response(content=body_bytes, status_code=response.status_code, headers=dict(response.headers))

        resource_path = pagination_state["resource_path"]
        size = pagination_state["size"]
        has_next = pagination_state["has_next"]
        has_prev = pagination_state["has_prev"]

        links: dict[str, str | None] = body.get("links", {})

        if has_next and "last_cursor" in pagination_state:
            links["next"] = f"{resource_path}?page[size]={size}&page[after]={pagination_state['last_cursor']}"
        else:
            links["next"] = None

        if has_prev and "first_cursor" in pagination_state:
            links["prev"] = f"{resource_path}?page[size]={size}&page[before]={pagination_state['first_cursor']}"
        else:
            links["prev"] = None

        body["links"] = links

        meta: dict[str, Any] = body.get("meta", {})
        meta.pop("count", None)
        meta.pop("totalPages", None)
        body["meta"] = meta

        new_body = json.dumps(body).encode()
        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))
        return Response(
            content=new_body, status_code=response.status_code, headers=headers, media_type="application/vnd.api+json"
        )

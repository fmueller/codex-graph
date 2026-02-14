"""Cursor-based pagination utilities for the JSON:API endpoints.

Implements the JSON:API Cursor Pagination Profile using opaque base64-encoded
cursors containing a sort key and a unique ID for tie-breaking.
"""

from __future__ import annotations

import base64
import json

from starlette.requests import Request


def encode_cursor(sort_value: str, id_value: str) -> str:
    """Encode a sort value and ID into an opaque base64 cursor string."""
    payload = json.dumps({"s": sort_value, "i": id_value}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


class InvalidCursorError(ValueError):
    """Raised when a cursor string cannot be decoded."""


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Decode a cursor string back into (sort_value, id_value).

    Raises ``InvalidCursorError`` if the cursor is malformed.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return str(payload["s"]), str(payload["i"])
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        raise InvalidCursorError(f"Malformed cursor: {cursor!r}") from exc


def parse_page_params(request: Request) -> tuple[str | None, str | None, int]:
    """Extract ``page[after]``, ``page[before]``, and ``page[size]`` from query params."""
    after = request.query_params.get("page[after]")
    before = request.query_params.get("page[before]")
    size_raw = request.query_params.get("page[size]", "50")
    try:
        size = max(1, min(int(size_raw), 1000))
    except (ValueError, TypeError):
        size = 50
    return after, before, size

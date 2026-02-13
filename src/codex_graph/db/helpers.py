import hashlib
from typing import Any

GRAPH_NAME = "codex_graph"


def escape_str(value: str) -> str:
    """Escape single quotes, backslashes, and parameter-like tokens for safe Cypher literal usage."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def to_cypher_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int | float)):
        return str(value)
    return f"'{escape_str(str(value))}'"


def to_cypher_props(props: dict[str, Any]) -> str:
    inner = ", ".join(f"{k}: {to_cypher_value(v)}" for k, v in props.items())
    return "{" + inner + "}"


def make_span_key(file_uuid: str, ntype: str, start_byte: int, end_byte: int) -> str:
    return f"{file_uuid}:{ntype}:{start_byte}:{end_byte}"


def compute_shape_hash(node_type: str, source_slice: bytes, child_hashes: list[str]) -> str:
    h = hashlib.sha256()
    h.update(b"T|" + node_type.encode("utf-8"))
    h.update(b"|S|" + source_slice)
    for ch in child_hashes:
        h.update(b"|C|" + ch.encode("utf-8"))
    return h.hexdigest()


def parse_agtype_int(val: Any) -> int:
    s = str(val)
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0

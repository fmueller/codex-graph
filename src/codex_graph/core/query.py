from typing import Any

from codex_graph.core.ports.database import GraphDatabase


def _agtype_int(val: object) -> int:
    """Parse an AGE agtype value to int, stripping quotes if present."""
    s = str(val).strip('"')
    return int(s) if s else 0


def _escape_str(value: str) -> str:
    """Escape single quotes, backslashes, and parameter-like tokens for safe Cypher literal usage."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


async def query_files(
    database: GraphDatabase,
    limit: int = 50,
    after_path: str | None = None,
    after_id: str | None = None,
    before_path: str | None = None,
    before_id: str | None = None,
) -> list[tuple[str, str, str, str]]:
    return await database.list_files_cursor(
        limit,
        after_path=after_path,
        after_id=after_id,
        before_path=before_path,
        before_id=before_id,
    )


async def query_node_types(
    database: GraphDatabase, file_filter: str | None = None, limit: int = 50
) -> list[tuple[Any, ...]]:
    if file_filter:
        cypher = (
            f"MATCH (n:AstNode)-[:OCCURS_IN]->(fv:FileVersion {{path: '{_escape_str(file_filter)}'}}) "
            f"RETURN DISTINCT n.type ORDER BY n.type LIMIT {limit}"
        )
    else:
        cypher = f"MATCH (n:AstNode) RETURN DISTINCT n.type ORDER BY n.type LIMIT {limit}"
    return await database.fetch_cypher(cypher)


async def query_nodes(
    database: GraphDatabase,
    node_type: str,
    file_filter: str | None = None,
    limit: int = 50,
    after_start_byte: int | None = None,
    after_span_key: str | None = None,
    before_start_byte: int | None = None,
    before_span_key: str | None = None,
) -> list[tuple[Any, ...]]:
    if file_filter:
        match_clause = (
            f"MATCH (n:AstNode {{type: '{_escape_str(node_type)}'}})"
            f"-[:OCCURS_IN]->(fv:FileVersion {{path: '{_escape_str(file_filter)}'}})"
        )
    else:
        match_clause = f"MATCH (n:AstNode {{type: '{_escape_str(node_type)}'}})"

    where_parts: list[str] = []
    if after_start_byte is not None and after_span_key is not None:
        where_parts.append(
            f"(n.start_byte > {after_start_byte} OR "
            f"(n.start_byte = {after_start_byte} AND n.span_key > '{_escape_str(after_span_key)}'))"
        )
    elif before_start_byte is not None and before_span_key is not None:
        where_parts.append(
            f"(n.start_byte < {before_start_byte} OR "
            f"(n.start_byte = {before_start_byte} AND n.span_key < '{_escape_str(before_span_key)}'))"
        )

    where_clause = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""

    cypher = (
        f"{match_clause}{where_clause} "
        f"RETURN n.span_key, n.type, n.start_byte, n.end_byte "
        f"ORDER BY n.start_byte, n.span_key LIMIT {limit}"
    )
    return await database.fetch_cypher(cypher, columns=4)


async def query_children(database: GraphDatabase, span_key: str, limit: int = 50) -> list[tuple[Any, ...]]:
    cypher = (
        f"MATCH (p:AstNode {{span_key: '{_escape_str(span_key)}'}})-[e:PARENT_OF]->(c:AstNode) "
        f"RETURN c.span_key, c.type, e.child_index ORDER BY e.child_index LIMIT {limit}"
    )
    return await database.fetch_cypher(cypher, columns=3)


async def query_cypher(database: GraphDatabase, query_string: str, columns: int | None = None) -> list[tuple[Any, ...]]:
    return await database.fetch_cypher(query_string, columns=columns)


async def query_statistics(database: GraphDatabase) -> dict[str, int]:
    """Return aggregate counts: files, ast_nodes, parent_of edges, occurs_in edges."""
    files = await database.fetch_cypher("MATCH (fv:FileVersion) RETURN count(fv)")
    nodes = await database.fetch_cypher("MATCH (n:AstNode) RETURN count(n)")
    parent_edges = await database.fetch_cypher("MATCH ()-[e:PARENT_OF]->() RETURN count(e)")
    occurs_edges = await database.fetch_cypher("MATCH ()-[e:OCCURS_IN]->() RETURN count(e)")

    def _first_int(rows: list[tuple[Any, ...]]) -> int:
        return _agtype_int(rows[0][0]) if rows and rows[0] else 0

    return {
        "files": _first_int(files),
        "ast_nodes": _first_int(nodes),
        "parent_of_edges": _first_int(parent_edges),
        "occurs_in_edges": _first_int(occurs_edges),
    }


async def query_language_distribution(database: GraphDatabase) -> list[tuple[str, int]]:
    """Return (language, count) pairs for FileVersions."""
    rows = await database.fetch_cypher(
        "MATCH (fv:FileVersion) RETURN fv.language, count(fv) ORDER BY count(fv) DESC",
        columns=2,
    )
    return [(str(r[0]).strip('"'), _agtype_int(r[1])) for r in rows]


async def query_node_type_counts(database: GraphDatabase, limit: int = 50) -> list[tuple[str, int]]:
    """Return (node_type, count) pairs ordered by frequency."""
    rows = await database.fetch_cypher(
        f"MATCH (n:AstNode) RETURN n.type, count(n) ORDER BY count(n) DESC LIMIT {limit}",
        columns=2,
    )
    return [(str(r[0]).strip('"'), _agtype_int(r[1])) for r in rows]


async def query_file_node_counts(database: GraphDatabase, limit: int = 100) -> list[tuple[str, str, str, int]]:
    """Return (file_uuid, path, language, ast_node_count) per FileVersion."""
    rows = await database.fetch_cypher(
        "MATCH (n:AstNode)-[:OCCURS_IN]->(fv:FileVersion) "
        "RETURN fv.file_uuid, fv.path, fv.language, count(n) "
        f"ORDER BY count(n) DESC LIMIT {limit}",
        columns=4,
    )
    return [(str(r[0]).strip('"'), str(r[1]).strip('"'), str(r[2]).strip('"'), _agtype_int(r[3])) for r in rows]


async def query_shared_shapes(database: GraphDatabase, limit: int = 50) -> list[tuple[str, str, int]]:
    """Return (file_path_a, file_path_b, shared_count) for files sharing shape_hash values."""
    rows = await database.fetch_cypher(
        "MATCH (a:AstNode)-[:OCCURS_IN]->(fv1:FileVersion), "
        "(b:AstNode)-[:OCCURS_IN]->(fv2:FileVersion) "
        "WHERE a.shape_hash = b.shape_hash AND id(fv1) < id(fv2) "
        "RETURN fv1.path, fv2.path, count(DISTINCT a.shape_hash) "
        f"ORDER BY count(DISTINCT a.shape_hash) DESC LIMIT {limit}",
        columns=3,
    )
    return [(str(r[0]).strip('"'), str(r[1]).strip('"'), _agtype_int(r[2])) for r in rows]


async def query_node_detail(database: GraphDatabase, span_key: str) -> list[tuple[Any, ...]]:
    """Return all properties for a single AstNode."""
    cypher = (
        f"MATCH (n:AstNode {{span_key: '{_escape_str(span_key)}'}}) "
        "RETURN n.span_key, n.type, n.start_line, n.start_column, "
        "n.end_line, n.end_column, n.start_byte, n.end_byte, n.shape_hash, n.file_uuid"
    )
    return await database.fetch_cypher(cypher, columns=10)


async def query_file_root_nodes(
    database: GraphDatabase,
    file_path: str,
    limit: int = 100,
    node_type: str | None = None,
) -> list[tuple[Any, ...]]:
    """Return top-level AST nodes (no parent) for a given file."""
    type_filter = f" AND n.type = '{_escape_str(node_type)}'" if node_type else ""
    cypher = (
        f"MATCH (n:AstNode)-[:OCCURS_IN]->(fv:FileVersion {{path: '{_escape_str(file_path)}'}}) "
        "OPTIONAL MATCH (parent)-[:PARENT_OF]->(n) "
        f"WITH n, parent WHERE parent IS NULL{type_filter} "
        f"RETURN n.span_key, n.type, n.start_byte, n.end_byte ORDER BY n.start_byte LIMIT {limit}"
    )
    return await database.fetch_cypher(cypher, columns=4)

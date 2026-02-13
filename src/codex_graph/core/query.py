from typing import Any

from codex_graph.core.ports.database import GraphDatabase


def _escape_str(value: str) -> str:
    """Escape single quotes, backslashes, and parameter-like tokens for safe Cypher literal usage."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


async def query_files(database: GraphDatabase, limit: int = 50) -> list[tuple[str, str, str, str]]:
    return await database.list_files(limit)


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
) -> list[tuple[Any, ...]]:
    if file_filter:
        cypher = (
            f"MATCH (n:AstNode {{type: '{_escape_str(node_type)}'}})"
            f"-[:OCCURS_IN]->(fv:FileVersion {{path: '{_escape_str(file_filter)}'}}) "
            f"RETURN n.span_key, n.type, n.start_byte, n.end_byte LIMIT {limit}"
        )
    else:
        cypher = (
            f"MATCH (n:AstNode {{type: '{_escape_str(node_type)}'}}) "
            f"RETURN n.span_key, n.type, n.start_byte, n.end_byte LIMIT {limit}"
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

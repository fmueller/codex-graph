import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from codex_graph.db.helpers import GRAPH_NAME, escape_str, parse_agtype_int, to_cypher_props


async def ensure_graph(engine: AsyncEngine, name: str) -> None:
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS age"))
            await conn.execute(text("LOAD 'age'"))
        except Exception:
            pass

        await conn.execute(text('SET search_path = public, ag_catalog, "$user"'))

        res = await conn.execute(
            text("SELECT count(*) FROM ag_catalog.ag_graph WHERE name = :name"),
            {"name": name},
        )
        count = int(res.scalar_one())
        if count == 0:
            await conn.execute(text(f"SELECT create_graph('{name}')"))

        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ast_edge_guard
                (
                    parent_id   BIGINT NOT NULL,
                    child_id    BIGINT NOT NULL,
                    child_index INT    NOT NULL,
                    PRIMARY KEY (parent_id, child_id),
                    UNIQUE (parent_id, child_index)
                )
                """
            )
        )


@asynccontextmanager
async def _use_conn(engine: AsyncEngine, conn: AsyncConnection | None = None) -> AsyncIterator[AsyncConnection]:
    """Yield an existing connection or open a new transactional one."""
    if conn is not None:
        yield conn
    else:
        async with engine.begin() as new_conn:
            yield new_conn


async def execute_cypher(engine: AsyncEngine, cypher: str, conn: AsyncConnection | None = None) -> None:
    async with _use_conn(engine, conn) as c:
        tag = f"q_{uuid.uuid4().hex}"
        sql = f"SELECT * FROM ag_catalog.cypher('{GRAPH_NAME}', ${tag}$ {cypher} ${tag}$) AS (ignored agtype)"
        await c.exec_driver_sql(sql)


def count_return_columns(cypher: str) -> int:
    """Count the number of top-level RETURN columns in a Cypher query.

    Ignores commas inside parentheses/brackets/braces so that expressions
    like ``coalesce(a, b)`` are treated as a single column.  Returns 1 when
    the query has no RETURN clause (e.g. bare CREATE statements).
    """
    upper = cypher.upper()
    idx = upper.rfind("RETURN")
    if idx == -1:
        return 1
    after_return = cypher[idx + len("RETURN") :]
    stripped = after_return.lstrip()
    if stripped.upper().startswith("DISTINCT"):
        stripped = stripped[len("DISTINCT") :]
    # Trim trailing clauses that are not part of the column list
    end_keywords = ["ORDER BY", "SKIP", "LIMIT"]
    end_pos = len(stripped)
    for kw in end_keywords:
        pos = stripped.upper().find(kw)
        if pos != -1 and pos < end_pos:
            end_pos = pos
    expr = stripped[:end_pos]
    depth = 0
    count = 1
    for ch in expr:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
    return count


async def fetch_cypher(
    engine: AsyncEngine, cypher: str, columns: int | None = None, conn: AsyncConnection | None = None
) -> list[tuple[Any, ...]]:
    if columns is None:
        columns = count_return_columns(cypher)
    async with _use_conn(engine, conn) as c:
        tag = f"q_{uuid.uuid4().hex}"
        col_defs = ", ".join(f"c{i} agtype" for i in range(columns))
        sql = f"SELECT * FROM ag_catalog.cypher('{GRAPH_NAME}', ${tag}$ {cypher} ${tag}$) AS ({col_defs})"
        result = await c.exec_driver_sql(sql)
        rows = result.fetchall()
        return [tuple(row) for row in rows]


async def create_vertex(engine: AsyncEngine, label: str, props: dict[str, Any]) -> None:
    cypher = f"CREATE (n:{label} {to_cypher_props(props)}) RETURN 1"
    await execute_cypher(engine, cypher)


async def create_edge(
    engine: AsyncEngine, left_label: str, left_uuid: str, rel: str, right_label: str, right_uuid: str
) -> None:
    cypher = (
        f"MATCH (a:{left_label} {{uuid: '{escape_str(left_uuid)}'}}), "
        f"(b:{right_label} {{uuid: '{escape_str(right_uuid)}'}}) "
        f"CREATE (a)-[:`{rel}`]->(b) RETURN 1"
    )
    await execute_cypher(engine, cypher)


async def db_lookup_node_id_by_span(engine: AsyncEngine, span_key: str) -> int | None:
    cypher = "MATCH (n:AstNode {span_key: '" + escape_str(span_key) + "'}) RETURN id(n) LIMIT 1"
    rows = await fetch_cypher(engine, cypher)
    if rows:
        return parse_agtype_int(rows[0][0])
    return None


async def db_lookup_node_id_by_shape(engine: AsyncEngine, shape_hash: str) -> int | None:
    cypher = "MATCH (n:AstNode {shape_hash: '" + escape_str(shape_hash) + "'}) RETURN id(n) LIMIT 1"
    rows = await fetch_cypher(engine, cypher)
    if rows:
        return parse_agtype_int(rows[0][0])
    return None


async def db_insert_ast_node(engine: AsyncEngine, props: dict[str, Any]) -> int:
    props_cypher = to_cypher_props(props)
    cypher_create = f"CREATE (n:AstNode {props_cypher}) RETURN id(n)"
    rows = await fetch_cypher(engine, cypher_create)
    return parse_agtype_int(rows[0][0])


async def db_upsert_parent_of(engine: AsyncEngine, parent_id: int, child_id: int, child_index: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO ast_edge_guard(parent_id, child_id, child_index)
                VALUES (:p, :c, :i)
                ON CONFLICT (parent_id, child_id) DO NOTHING
                """
            ),
            {"p": parent_id, "c": child_id, "i": child_index},
        )
    cypher = (
        f"MATCH (p) WHERE id(p) = {parent_id} "
        f"MATCH (c) WHERE id(c) = {child_id} "
        f"MERGE (p)-[e:PARENT_OF]->(c) SET e.child_index = {child_index} RETURN id(e)"
    )
    await execute_cypher(engine, cypher)

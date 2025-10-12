import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser


class Position(BaseModel):
    row: int
    column: int


class AstNode(BaseModel):
    type: str
    start_byte: int
    end_byte: int
    start_point: Position
    end_point: Position
    text: str | None = None
    children: list["AstNode"] | None = None


AstNode.model_rebuild()  # necessary for recursive types


class FileAst(BaseModel):
    language: str
    path: str
    ast: AstNode


def extract_ast_from_file(path: str) -> FileAst:
    """
    Parses the AST from the given Python file.

    :param path: Path to the Python file.
    :return: FileAst model with AST data.
    """

    file_path = Path(path)
    if file_path.suffix.lower() != ".py":
        raise ValueError(f"Only Python files are supported, got: {file_path.suffix}")

    try:
        source_bytes = file_path.read_bytes()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}") from None

    parser = get_parser("python")

    tree = parser.parse(source_bytes)

    with open("src/codex_graph_server/queries/python_detailed.scm", encoding="utf-8") as f:
        query_text = f.read()
    query = Query(get_language("python"), query_text)
    cursor = QueryCursor(query)
    for _, captures in cursor.matches(tree.root_node):
        for cap_name, nodes in captures.items():
            for node in nodes:
                text_snippet = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
                print(cap_name + ": " + text_snippet)

    root = tree.root_node

    def node_to_model(node) -> AstNode:
        # Convert a tree-sitter Node into an AstNode model
        children = None
        text_value = None

        if node.child_count > 0:
            children = [node_to_model(child) for child in node.children]
        else:
            try:
                text_value = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
            except Exception:
                text_value = ""

        return AstNode(
            type=node.type,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=Position(row=node.start_point[0], column=node.start_point[1]),
            end_point=Position(row=node.end_point[0], column=node.end_point[1]),
            text=text_value,
            children=children,
        )

    return FileAst(
        language="python",
        path=str(file_path),
        ast=node_to_model(root),
    )


GRAPH_NAME = "codex_graph"


def _escape_str(value: str) -> str:
    """Escape single quotes, backslashes, and parameter-like tokens for safe Cypher literal usage."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _to_cypher_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int | float)):
        return str(value)
    return f"'{_escape_str(str(value))}'"


def _to_cypher_props(props: dict[str, Any]) -> str:
    inner = ", ".join(f"{k}: {_to_cypher_value(v)}" for k, v in props.items())
    return "{" + inner + "}"


def _get_engine() -> AsyncEngine:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    )
    return create_async_engine(db_url, future=True)


async def _ensure_graph(engine: AsyncEngine, name: str) -> None:
    async with engine.begin() as conn:
        try:
            # TODO move to alembic migration
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS age"))
            # TODO verify if we can get rid of this, if not: move to alembic migration
            await conn.execute(text("LOAD 'age'"))
        except Exception:
            # If LOAD fails, subsequent AGE calls will also fail; let them surface.
            pass

        # TODO move to Dockerfile and init script
        await conn.execute(text('SET search_path = ag_catalog, "$user", public'))

        res = await conn.execute(
            text("SELECT count(*) FROM ag_catalog.ag_graph WHERE name = :name"),
            {"name": name},
        )
        count = int(res.scalar_one())
        if count == 0:
            # Create the graph if it doesn't exist
            await conn.execute(text(f"SELECT create_graph('{name}')"))


async def _execute_cypher(engine, cypher: str) -> None:
    async with engine.begin() as conn:
        # Use a unique dollar-quote tag that won't collide with the payload
        tag = f"q_{uuid.uuid4().hex}"
        sql = f"SELECT * FROM ag_catalog.cypher('{GRAPH_NAME}', ${tag}$ {cypher} ${tag}$) AS (ignored agtype)"
        # Bypass SQLAlchemy param parsing
        await conn.exec_driver_sql(sql)


async def _create_vertex(engine: AsyncEngine, label: str, props: dict[str, Any]) -> None:
    cypher = f"CREATE (n:{label} {_to_cypher_props(props)}) RETURN 1"
    await _execute_cypher(engine, cypher)


async def _create_edge(
    engine: AsyncEngine, left_label: str, left_uuid: str, rel: str, right_label: str, right_uuid: str
) -> None:
    cypher = (
        f"MATCH (a:{left_label} {{uuid: '{_escape_str(left_uuid)}'}}), "
        f"(b:{right_label} {{uuid: '{_escape_str(right_uuid)}'}}) "
        f"CREATE (a)-[:`{rel}`]->(b) RETURN 1"
    )
    await _execute_cypher(engine, cypher)


async def _persist_ast_node(engine: AsyncEngine, node: AstNode, parent_uuid: str | None = None) -> str:
    node_uuid = str(uuid.uuid4())
    await _create_vertex(
        engine,
        "AstNode",
        {
            "uuid": node_uuid,
            "type": node.type,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "start_point": _to_cypher_props(node.start_point.model_dump()),
            "end_point": _to_cypher_props(node.end_point.model_dump()),
            "text": node.text,
        },
    )

    if parent_uuid is not None:
        await _create_edge(engine, "AstNode", node_uuid, "HAS_PARENT", "AstNode", parent_uuid)

    if node.children:
        for child in node.children:
            child_uuid = await _persist_ast_node(engine, child, parent_uuid=node_uuid)
            await _create_edge(engine, "AstNode", node_uuid, "HAS_CHILD", "AstNode", child_uuid)

    return node_uuid


async def persist_file_ast_to_age(engine: AsyncEngine, fa: FileAst) -> None:
    await _ensure_graph(engine, GRAPH_NAME)

    file_uuid = str(uuid.uuid4())
    await _create_vertex(engine, "FileAst", {"uuid": file_uuid, "language": fa.language, "path": fa.path})

    root_uuid = await _persist_ast_node(engine, fa.ast)
    await _create_edge(engine, "FileAst", file_uuid, "HAS_AST", "AstNode", root_uuid)


def main() -> None:
    ast = extract_ast_from_file("src/codex_graph_server/main.py")

    async def _runner() -> None:
        engine = _get_engine()
        try:
            await persist_file_ast_to_age(engine, ast)
        finally:
            await engine.dispose()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime
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
    file_uuid: str
    type: str
    start_byte: int
    end_byte: int
    start_point: Position
    end_point: Position
    children: list["AstNode"] | None = None


AstNode.model_rebuild()  # necessary for recursive types


class FileAst(BaseModel):
    file_uuid: str
    language: str
    ast: AstNode


def _extract_ast_from_file(path: str, file_uuid: str) -> FileAst:
    """
    Parses the AST from the given Python file.

    :param path: Path to the Python file.
    :param file_uuid: UUID of the file to use in the AST.
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

    with open("src/codex_graph/queries/python_detailed.scm", encoding="utf-8") as f:
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
        children = None
        if node.child_count > 0:
            children = [node_to_model(child) for child in node.children]

        return AstNode(
            type=node.type,
            file_uuid=file_uuid,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=Position(row=node.start_point[0], column=node.start_point[1]),
            end_point=Position(row=node.end_point[0], column=node.end_point[1]),
            children=children,
        )

    return FileAst(
        file_uuid=file_uuid,
        language="python",
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
            "file_uuid": node.file_uuid,
        },
    )

    if parent_uuid is not None:
        await _create_edge(engine, "AstNode", node_uuid, "HAS_PARENT", "AstNode", parent_uuid)

    if node.children:
        for child in node.children:
            child_uuid = await _persist_ast_node(engine, child, parent_uuid=node_uuid)
            await _create_edge(engine, "AstNode", node_uuid, "HAS_CHILD", "AstNode", child_uuid)

    return node_uuid


async def _persist_file_ast_to_age(engine: AsyncEngine, fa: FileAst) -> None:
    await _ensure_graph(engine, GRAPH_NAME)

    file_node_uuid = str(uuid.uuid4())
    await _create_vertex(
        engine, "FileAst", {"uuid": file_node_uuid, "language": fa.language, "file_uuid": fa.file_uuid}
    )

    root_uuid = await _persist_ast_node(engine, fa.ast, file_node_uuid)
    await _create_edge(engine, "FileAst", file_node_uuid, "HAS_AST", "AstNode", root_uuid)


async def _ensure_files_table(engine: AsyncEngine) -> None:
    ddl = (
        "CREATE TABLE IF NOT EXISTS files ("
        " id UUID PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " full_path TEXT NOT NULL,"
        " suffix TEXT NOT NULL,"
        " content TEXT NOT NULL,"
        " content_hash TEXT NOT NULL,"
        " created TIMESTAMPTZ NOT NULL,"
        " last_modified TIMESTAMPTZ NOT NULL"
        ")"
    )
    async with engine.begin() as conn:
        await conn.execute(text(ddl))


async def _persist_file(engine: AsyncEngine, path: str) -> str:
    file_path = Path(path)
    full_path = str(file_path.resolve())
    name = file_path.name
    suffix = file_path.suffix
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback to binary decode with replacement
        content = file_path.read_bytes().decode("utf-8", errors="replace")

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    # TODO lookup if file exists in DB with same hash and return UUID if so

    stat = file_path.stat()
    # Note: st_ctime is platform-dependent; acceptable for now.
    created_dt = datetime.fromtimestamp(stat.st_ctime, tz=UTC)
    modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

    file_uuid = uuid.uuid4()

    await _ensure_files_table(engine)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO files (id, name, full_path, suffix, content, content_hash, created, last_modified)
                VALUES (:id, :name, :full_path, :suffix, :content, :content_hash, :created, :last_modified)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": file_uuid,
                "name": name,
                "full_path": full_path,
                "suffix": suffix,
                "content": content,
                "content_hash": content_hash,
                "created": created_dt,
                "last_modified": modified_dt,
            },
        )

    return str(file_uuid)


def main() -> None:
    file_path = "src/codex_graph/main.py"

    async def _runner() -> None:
        engine = _get_engine()
        try:
            file_uuid = await _persist_file(engine, file_path)
            print(f"Persisted file {file_path} with UUID {file_uuid}")

            ast = _extract_ast_from_file(file_path, file_uuid)
            print(f"Extracted AST from {file_path}")

            await _persist_file_ast_to_age(engine, ast)
            print(f"Persisted AST to {GRAPH_NAME}")
        finally:
            await engine.dispose()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()

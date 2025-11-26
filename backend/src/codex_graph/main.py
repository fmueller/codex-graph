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


def make_span_key(file_uuid: str, ntype: str, start_byte: int, end_byte: int) -> str:
    return f"{file_uuid}:{ntype}:{start_byte}:{end_byte}"


def compute_shape_hash(node_type: str, source_slice: bytes, child_hashes: list[str]) -> str:
    h = hashlib.sha256()
    h.update(b"T|" + node_type.encode("utf-8"))
    h.update(b"|S|" + source_slice)
    for ch in child_hashes:
        h.update(b"|C|" + ch.encode("utf-8"))
    return h.hexdigest()


def _parse_agtype_int(val: Any) -> int:
    s = str(val)
    # Extract consecutive digits
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0


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
            await conn.execute(text(f"SELECT create_graph('{name}')"))

        # Create edge guard table for ordered, idempotent edges
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


async def _execute_cypher(engine, cypher: str) -> None:
    async with engine.begin() as conn:
        tag = f"q_{uuid.uuid4().hex}"
        # Use a unique dollar-quote tag that won't collide with the payload
        sql = f"SELECT * FROM ag_catalog.cypher('{GRAPH_NAME}', ${tag}$ {cypher} ${tag}$) AS (ignored agtype)"
        # Bypass SQLAlchemy param parsing
        await conn.exec_driver_sql(sql)


async def _fetch_cypher(engine, cypher: str) -> list[tuple[Any, ...]]:
    async with engine.begin() as conn:
        tag = f"q_{uuid.uuid4().hex}"
        sql = f"SELECT * FROM ag_catalog.cypher('{GRAPH_NAME}', ${tag}$ {cypher} ${tag}$) AS (res agtype)"
        result = await conn.exec_driver_sql(sql)
        rows = result.fetchall()
        return rows


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


# DAG ingest helpers for AstNode identity and edges
async def db_lookup_node_id_by_span(engine: AsyncEngine, span_key: str) -> int | None:
    cypher = "MATCH (n:AstNode {span_key: '" + _escape_str(span_key) + "'}) RETURN id(n) LIMIT 1"
    rows = await _fetch_cypher(engine, cypher)
    if rows:
        return _parse_agtype_int(rows[0][0])
    return None


async def db_lookup_node_id_by_shape(engine: AsyncEngine, shape_hash: str) -> int | None:
    cypher = "MATCH (n:AstNode {shape_hash: '" + _escape_str(shape_hash) + "'}) RETURN id(n) LIMIT 1"
    rows = await _fetch_cypher(engine, cypher)
    if rows:
        return _parse_agtype_int(rows[0][0])
    return None


async def db_insert_ast_node(engine: AsyncEngine, props: dict[str, Any]) -> int:
    # Try match first (by span_key)
    span_key = props.get("span_key")
    if span_key:
        existing = await db_lookup_node_id_by_span(engine, span_key)
        if existing is not None:
            return existing
    # Create new
    props_cypher = _to_cypher_props(props)
    cypher_create = f"CREATE (n:AstNode {props_cypher}) RETURN id(n)"
    rows = await _fetch_cypher(engine, cypher_create)
    return _parse_agtype_int(rows[0][0])


async def db_upsert_parent_of(engine: AsyncEngine, parent_id: int, child_id: int, child_index: int) -> None:
    # Edge guard to ensure (parent, child) uniqueness and ordered child_index uniqueness per parent
    async with engine.begin() as conn:
        # TODO implement proper transactional semantics and decide about what to do if the edge already exists
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
    # Mirror into AGE graph with MERGE and set child_index
    cypher = (
        f"MATCH (p) WHERE id(p) = {parent_id} "
        f"MATCH (c) WHERE id(c) = {child_id} "
        f"MERGE (p)-[e:PARENT_OF]->(c) SET e.child_index = {child_index} RETURN id(e)"
    )
    await _execute_cypher(engine, cypher)


class _IngestCaches:
    def __init__(self) -> None:
        self.node_id_by_span: dict[str, int] = {}
        self.node_id_by_shape: dict[str, int] = {}


async def _ingest_node(
    engine: AsyncEngine,
    node: AstNode,
    file_uuid: str,
    source_bytes: bytes,
    caches: _IngestCaches,
    occurrences: list[tuple[int, int, int]],
) -> tuple[int, str | None]:
    # 1) process children first
    child_ids: list[int] = []
    child_shapes: list[str] = []
    if node.children:
        for child in node.children:
            cid, cshape = await _ingest_node(engine, child, file_uuid, source_bytes, caches, occurrences)
            child_ids.append(cid)
            if cshape:
                child_shapes.append(cshape)

    # 2) keys
    span_key = make_span_key(file_uuid, node.type, node.start_byte, node.end_byte)
    src_slice = source_bytes[node.start_byte : node.end_byte]
    shash = compute_shape_hash(node.type, src_slice, child_shapes)

    # 3) lookup-or-create
    nid = caches.node_id_by_span.get(span_key)
    if nid is None:
        nid = await db_lookup_node_id_by_span(engine, span_key)
    if nid is None and shash:
        nid = caches.node_id_by_shape.get(shash) or await db_lookup_node_id_by_shape(engine, shash)

    if nid is None:
        nid = await db_insert_ast_node(
            engine,
            {
                "file_uuid": file_uuid,
                "type": node.type,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
                "start_row": node.start_point.row,
                "start_col": node.start_point.column,
                "end_row": node.end_point.row,
                "end_col": node.end_point.column,
                "span_key": span_key,
                "shape_hash": shash,
            },
        )
    caches.node_id_by_span[span_key] = nid
    if shash:
        caches.node_id_by_shape.setdefault(shash, nid)

    # 4) ordered edges
    for idx, cid in enumerate(child_ids):
        await db_upsert_parent_of(engine, nid, cid, idx)

    # 5) record occurrence and return
    occurrences.append((nid, node.start_byte, node.end_byte))
    return nid, shash


async def _persist_file_ast_to_age(engine: AsyncEngine, fa: FileAst, file_path: str) -> None:
    await _ensure_graph(engine, GRAPH_NAME)

    # Create or get FileVersion node (MERGE on commit_id+file_uuid+path)
    commit_id = "local"
    ts_iso = datetime.now(UTC).isoformat()
    cypher_fv = (
        f"MERGE (fv:FileVersion {{commit_id: '{_escape_str(commit_id)}', file_uuid: '{_escape_str(fa.file_uuid)}', "
        f"path: '{_escape_str(file_path)}'}}) "
        f"SET fv.language = '{_escape_str(fa.language)}', fv.ts = '{_escape_str(ts_iso)}' "
        f"RETURN id(fv)"
    )
    fv_rows = await _fetch_cypher(engine, cypher_fv)
    file_version_id = _parse_agtype_int(fv_rows[0][0]) if fv_rows else 0

    caches = _IngestCaches()
    occurrences: list[tuple[int, int, int]] = []
    source_bytes = Path(file_path).read_bytes()
    await _ingest_node(engine, fa.ast, fa.file_uuid, source_bytes, caches, occurrences)

    # Create OCCURS_IN edges per occurrence
    for nid, start_b, end_b in occurrences:
        cypher_occurs = (
            f"MATCH (n) WHERE id(n) = {nid} "
            f"MATCH (fv) WHERE id(fv) = {file_version_id} "
            f"MERGE (n)-[r:OCCURS_IN {{commit_id: '{_escape_str(commit_id)}', file_uuid: '{_escape_str(fa.file_uuid)}',"
            f" start_byte: {start_b}, end_byte: {end_b}}}]->(fv) "
            f"RETURN id(r)"
        )
        await _execute_cypher(engine, cypher_occurs)


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

            await _persist_file_ast_to_age(engine, ast, file_path)
            print(f"Persisted AST to {GRAPH_NAME}")
        finally:
            await engine.dispose()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()

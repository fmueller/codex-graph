import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from codex_graph.db.cypher import (
    db_insert_ast_node,
    db_upsert_parent_of,
    ensure_graph,
    execute_cypher,
    fetch_cypher,
)
from codex_graph.db.git import get_git_commit_info, get_previous_commit_for_file
from codex_graph.db.helpers import GRAPH_NAME, compute_shape_hash, escape_str, make_span_key, parse_agtype_int
from codex_graph.models import AstNode, FileAst


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
    child_ids: list[int] = []
    child_shapes: list[str] = []
    if node.children:
        for child in node.children:
            cid, cshape = await _ingest_node(engine, child, file_uuid, source_bytes, caches, occurrences)
            child_ids.append(cid)
            if cshape:
                child_shapes.append(cshape)

    span_key = make_span_key(file_uuid, node.type, node.start_byte, node.end_byte)
    src_slice = source_bytes[node.start_byte : node.end_byte]
    shash = compute_shape_hash(node.type, src_slice, child_shapes)

    from codex_graph.db.cypher import db_lookup_node_id_by_shape, db_lookup_node_id_by_span

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

    for idx, cid in enumerate(child_ids):
        await db_upsert_parent_of(engine, nid, cid, idx)

    occurrences.append((nid, node.start_byte, node.end_byte))
    return nid, shash


async def _persist_file_ast_to_age(engine: AsyncEngine, fa: FileAst, file_path: str) -> None:
    await ensure_graph(engine, GRAPH_NAME)

    git_info = get_git_commit_info(file_path)
    commit_id = git_info.commit_id if git_info else "local"
    author = git_info.author if git_info else "local"
    ts_iso = git_info.timestamp if git_info else datetime.now(timezone.utc).isoformat()
    branch = git_info.branch if git_info else "local"
    cypher_fv = (
        f"MERGE (fv:FileVersion {{commit_id: '{escape_str(commit_id)}', file_uuid: '{escape_str(fa.file_uuid)}', "
        f"path: '{escape_str(file_path)}'}}) "
        f"SET fv.language = '{escape_str(fa.language)}', fv.ts = '{escape_str(ts_iso)}', "
        f"fv.author = '{escape_str(author)}', fv.branch = '{escape_str(branch)}' "
        f"RETURN id(fv)"
    )
    fv_rows = await fetch_cypher(engine, cypher_fv)
    file_version_id = parse_agtype_int(fv_rows[0][0]) if fv_rows else 0

    prev_commit = get_previous_commit_for_file(file_path, commit_id) if commit_id != "local" else None
    if prev_commit:
        cypher_link = (
            f"MATCH (prev:FileVersion {{commit_id: '{escape_str(prev_commit)}', path: '{escape_str(file_path)}'}}) "
            f"MATCH (cur) WHERE id(cur) = {file_version_id} "
            f"MERGE (prev)-[r:NEXT_VERSION]->(cur) "
            f"RETURN id(r)"
        )
        await execute_cypher(engine, cypher_link)

    caches = _IngestCaches()
    occurrences: list[tuple[int, int, int]] = []
    source_bytes = Path(file_path).read_bytes()
    await _ingest_node(engine, fa.ast, fa.file_uuid, source_bytes, caches, occurrences)

    for nid, start_b, end_b in occurrences:
        cypher_occurs = (
            f"MATCH (n) WHERE id(n) = {nid} "
            f"MATCH (fv) WHERE id(fv) = {file_version_id} "
            f"MERGE (n)-[r:OCCURS_IN {{commit_id: '{escape_str(commit_id)}', file_uuid: '{escape_str(fa.file_uuid)}',"
            f" start_byte: {start_b}, end_byte: {end_b}}}]->(fv) "
            f"RETURN id(r)"
        )
        await execute_cypher(engine, cypher_occurs)


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
        content = file_path.read_bytes().decode("utf-8", errors="replace")

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    await _ensure_files_table(engine)

    async with engine.begin() as conn:
        existing = await conn.execute(
            text(
                """
                SELECT id FROM files
                WHERE full_path = :full_path AND content_hash = :content_hash
                LIMIT 1
                """
            ),
            {"full_path": full_path, "content_hash": content_hash},
        )
        existing_id = existing.scalar_one_or_none()
        if existing_id is not None:
            return str(existing_id)

        stat = file_path.stat()
        created_dt = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
        modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        file_uuid = uuid.uuid4()

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


class PostgresGraphDatabase:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def persist_file(self, path: str) -> str:
        return await _persist_file(self._engine, path)

    async def persist_file_ast(self, fa: FileAst, file_path: str) -> None:
        await _persist_file_ast_to_age(self._engine, fa, file_path)

    async def ensure_ready(self) -> None:
        """Ensure AGE extension is loaded and graph exists."""
        await ensure_graph(self._engine, GRAPH_NAME)

    async def fetch_cypher(self, cypher: str, columns: int | None = None) -> list[tuple[Any, ...]]:
        """Run a read-only Cypher query and return result rows."""
        return await fetch_cypher(self._engine, cypher, columns)

    async def get_file_by_id(self, file_uuid: str) -> tuple[str, str, str, str] | None:
        """Return (id, full_path, suffix, content_hash_prefix) for a single file, or None."""
        await _ensure_files_table(self._engine)
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text("SELECT id, full_path, suffix, content_hash FROM public.files WHERE id = :file_id"),
                {"file_id": file_uuid},
            )
            row = result.fetchone()
            if row is None:
                return None
            return (str(row[0]), str(row[1]), str(row[2]), str(row[3])[:12])

    async def list_files(self, limit: int = 50) -> list[tuple[str, str, str, str]]:
        """Return (id, full_path, suffix, content_hash_prefix) from the files table."""
        await _ensure_files_table(self._engine)
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text("SELECT id, full_path, suffix, content_hash FROM public.files ORDER BY full_path LIMIT :lim"),
                {"lim": limit},
            )
            return [(str(row[0]), str(row[1]), str(row[2]), str(row[3])[:12]) for row in result.fetchall()]

    async def list_files_cursor(
        self,
        limit: int = 50,
        after_path: str | None = None,
        after_id: str | None = None,
        before_path: str | None = None,
        before_id: str | None = None,
    ) -> list[tuple[str, str, str, str]]:
        """Return files with cursor-based pagination ordered by (full_path, id)."""
        await _ensure_files_table(self._engine)
        async with self._engine.begin() as conn:
            if after_path is not None and after_id is not None:
                result = await conn.execute(
                    text(
                        "SELECT id, full_path, suffix, content_hash FROM public.files "
                        "WHERE (full_path, id::text) > (:after_path, :after_id) "
                        "ORDER BY full_path, id LIMIT :lim"
                    ),
                    {"after_path": after_path, "after_id": after_id, "lim": limit},
                )
            elif before_path is not None and before_id is not None:
                result = await conn.execute(
                    text(
                        "SELECT * FROM ("
                        "  SELECT id, full_path, suffix, content_hash FROM public.files "
                        "  WHERE (full_path, id::text) < (:before_path, :before_id) "
                        "  ORDER BY full_path DESC, id DESC LIMIT :lim"
                        ") sub ORDER BY full_path, id"
                    ),
                    {"before_path": before_path, "before_id": before_id, "lim": limit},
                )
            else:
                result = await conn.execute(
                    text(
                        "SELECT id, full_path, suffix, content_hash FROM public.files ORDER BY full_path, id LIMIT :lim"
                    ),
                    {"lim": limit},
                )
            return [(str(row[0]), str(row[1]), str(row[2]), str(row[3])[:12]) for row in result.fetchall()]

    async def get_language_for_file(self, file_uuid: str) -> str:
        """Return the language for a single file UUID from FileVersion nodes."""
        rows = await fetch_cypher(
            self._engine,
            f"MATCH (fv:FileVersion {{file_uuid: '{escape_str(file_uuid)}'}}) RETURN fv.language",
        )
        if rows:
            return str(rows[0][0]).strip('"')
        return ""

    async def get_languages_for_files(self, file_uuids: list[str]) -> dict[str, str]:
        """Return {file_uuid: language} for the given file UUIDs."""
        if not file_uuids:
            return {}
        uuid_list = ", ".join(f"'{escape_str(u)}'" for u in file_uuids)
        rows = await fetch_cypher(
            self._engine,
            f"MATCH (fv:FileVersion) WHERE fv.file_uuid IN [{uuid_list}] RETURN fv.file_uuid, fv.language",
            columns=2,
        )
        result: dict[str, str] = {}
        for r in rows:
            result[str(r[0]).strip('"')] = str(r[1]).strip('"')
        return result

    async def get_node_details(self, span_keys: list[str]) -> dict[str, tuple[Any, ...]]:
        """Return {span_key: (span_key, type, start_line, ...)} for the given span keys."""
        if not span_keys:
            return {}
        key_list = ", ".join(f"'{escape_str(k)}'" for k in span_keys)
        rows = await fetch_cypher(
            self._engine,
            f"MATCH (n:AstNode) WHERE n.span_key IN [{key_list}] "
            "RETURN n.span_key, n.type, n.start_line, n.start_column, "
            "n.end_line, n.end_column, n.start_byte, n.end_byte, n.shape_hash, n.file_uuid",
            columns=10,
        )
        result: dict[str, tuple[Any, ...]] = {}
        for r in rows:
            result[str(r[0]).strip('"')] = r
        return result

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        await self._engine.dispose()

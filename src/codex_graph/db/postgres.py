import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from codex_graph.db.cypher import (
    _use_conn,
    ensure_graph,
    execute_cypher,
    fetch_cypher,
)
from codex_graph.db.git import get_git_commit_info, get_previous_commit_for_file
from codex_graph.db.helpers import GRAPH_NAME, compute_shape_hash, escape_str, make_span_key, parse_agtype_int
from codex_graph.models import AstNode, FileAst

logger = logging.getLogger(__name__)

_graph_ensured = False


_BATCH_SIZE = 200


def _collect_ast_data(
    node: AstNode,
    file_uuid: str,
    source_bytes: bytes,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """Walk the AST tree and collect flat lists for batch DB operations.

    Returns ``(node_props, edges, occurrences)`` where:
    - ``node_props[i]`` is the property dict for node *i*
    - ``edges[j]`` is ``(parent_index, child_index, child_order)``
    - ``occurrences[k]`` is ``(node_index, start_byte, end_byte)``
    """
    nodes: list[dict[str, Any]] = []
    edges: list[tuple[int, int, int]] = []
    occurrences: list[tuple[int, int, int]] = []

    def _walk(n: AstNode) -> tuple[int, str]:
        child_indices: list[int] = []
        child_shapes: list[str] = []
        if n.children:
            for child in n.children:
                ci, cs = _walk(child)
                child_indices.append(ci)
                if cs:
                    child_shapes.append(cs)

        span_key = make_span_key(file_uuid, n.type, n.start_byte, n.end_byte)
        src_slice = source_bytes[n.start_byte : n.end_byte]
        shash = compute_shape_hash(n.type, src_slice, child_shapes)

        idx = len(nodes)
        nodes.append(
            {
                "file_uuid": file_uuid,
                "type": n.type,
                "start_byte": n.start_byte,
                "end_byte": n.end_byte,
                "start_row": n.start_point.row,
                "start_col": n.start_point.column,
                "end_row": n.end_point.row,
                "end_col": n.end_point.column,
                "span_key": span_key,
                "shape_hash": shash,
            }
        )

        for child_order, ci in enumerate(child_indices):
            edges.append((idx, ci, child_order))

        occurrences.append((idx, n.start_byte, n.end_byte))
        return idx, shash

    _walk(node)
    return nodes, edges, occurrences


async def _batch_lookup_spans(
    engine: AsyncEngine,
    span_keys: list[str],
    conn: Any,
) -> dict[str, int]:
    """Look up existing AstNode IDs by span_key in batches."""
    span_to_id: dict[str, int] = {}
    for i in range(0, len(span_keys), _BATCH_SIZE):
        chunk = span_keys[i : i + _BATCH_SIZE]
        key_list = ", ".join(f"'{escape_str(k)}'" for k in chunk)
        cypher = f"MATCH (n:AstNode) WHERE n.span_key IN [{key_list}] RETURN n.span_key, id(n)"
        rows = await fetch_cypher(engine, cypher, columns=2, conn=conn)
        for row in rows:
            sk = str(row[0]).strip('"')
            nid = parse_agtype_int(row[1])
            span_to_id[sk] = nid
    return span_to_id


async def _batch_create_nodes(
    engine: AsyncEngine,
    node_props_list: list[dict[str, Any]],
    conn: Any,
) -> list[int]:
    """Create AstNode vertices in batches and return their AGE IDs in order."""
    from codex_graph.db.helpers import to_cypher_props

    ids: list[int] = []
    for i in range(0, len(node_props_list), _BATCH_SIZE):
        chunk = node_props_list[i : i + _BATCH_SIZE]
        props_literals = ", ".join(to_cypher_props(p) for p in chunk)
        cypher = f"UNWIND [{props_literals}] AS props CREATE (n:AstNode) SET n = props RETURN id(n)"
        rows = await fetch_cypher(engine, cypher, columns=1, conn=conn)
        ids.extend(parse_agtype_int(row[0]) for row in rows)
    return ids


async def _batch_edge_guard(
    engine: AsyncEngine,
    triples: list[tuple[int, int, int]],
    conn: Any,
) -> None:
    """Bulk INSERT into ast_edge_guard."""
    if not triples:
        return
    for i in range(0, len(triples), _BATCH_SIZE):
        chunk = triples[i : i + _BATCH_SIZE]
        values = ", ".join(f"({p}, {c}, {idx})" for p, c, idx in chunk)
        sql = (
            f"INSERT INTO ast_edge_guard(parent_id, child_id, child_index) "
            f"VALUES {values} ON CONFLICT (parent_id, child_id) DO NOTHING"
        )
        async with _use_conn(engine, conn) as c:
            await c.execute(text(sql))


async def _batch_parent_edges(
    engine: AsyncEngine,
    triples: list[tuple[int, int, int]],
    conn: Any,
) -> None:
    """Create PARENT_OF edges in batches via UNWIND."""
    if not triples:
        return
    for i in range(0, len(triples), _BATCH_SIZE):
        chunk = triples[i : i + _BATCH_SIZE]
        items = ", ".join(f"{{pid: {p}, cid: {c}, idx: {idx}}}" for p, c, idx in chunk)
        cypher = (
            f"UNWIND [{items}] AS e "
            "MATCH (p) WHERE id(p) = e.pid "
            "MATCH (c) WHERE id(c) = e.cid "
            "MERGE (p)-[r:PARENT_OF]->(c) SET r.child_index = e.idx "
            "RETURN id(r)"
        )
        await execute_cypher(engine, cypher, conn=conn)


async def _batch_occurs_edges(
    engine: AsyncEngine,
    occurs: list[tuple[int, int, int]],
    file_version_id: int,
    commit_id: str,
    file_uuid: str,
    conn: Any,
) -> None:
    """Create OCCURS_IN edges in batches via UNWIND."""
    if not occurs:
        return
    esc_commit = escape_str(commit_id)
    esc_uuid = escape_str(file_uuid)
    for i in range(0, len(occurs), _BATCH_SIZE):
        chunk = occurs[i : i + _BATCH_SIZE]
        items = ", ".join(f"{{nid: {nid}, sb: {sb}, eb: {eb}}}" for nid, sb, eb in chunk)
        cypher = (
            f"UNWIND [{items}] AS o "
            f"MATCH (n) WHERE id(n) = o.nid "
            f"MATCH (fv) WHERE id(fv) = {file_version_id} "
            f"MERGE (n)-[r:OCCURS_IN {{commit_id: '{esc_commit}', file_uuid: '{esc_uuid}', "
            f"start_byte: o.sb, end_byte: o.eb}}]->(fv) "
            f"RETURN id(r)"
        )
        await execute_cypher(engine, cypher, conn=conn)


async def _persist_file_ast_to_age(engine: AsyncEngine, fa: FileAst, file_path: str) -> None:
    t_total = time.perf_counter()

    global _graph_ensured  # noqa: PLW0603
    t0 = time.perf_counter()
    if not _graph_ensured:
        await ensure_graph(engine, GRAPH_NAME)
        _graph_ensured = True
    t_ensure = time.perf_counter() - t0

    t0 = time.perf_counter()
    git_info = get_git_commit_info(file_path)
    t_git = time.perf_counter() - t0

    commit_id = git_info.commit_id if git_info else "local"
    author = git_info.author if git_info else "local"
    ts_iso = git_info.timestamp if git_info else datetime.now(timezone.utc).isoformat()
    branch = git_info.branch if git_info else "local"

    source_bytes = fa.source_bytes if fa.source_bytes is not None else Path(file_path).read_bytes()

    # --- Phase 1: collect (pure computation, no DB) ---
    t0 = time.perf_counter()
    node_props, edge_tuples, occurrence_tuples = _collect_ast_data(fa.ast, fa.file_uuid, source_bytes)
    t_collect = time.perf_counter() - t0

    # --- Phase 2: persist (all batched, single transaction) ---
    async with engine.begin() as conn:
        # File version
        t0 = time.perf_counter()
        cypher_fv = (
            f"MERGE (fv:FileVersion {{commit_id: '{escape_str(commit_id)}', "
            f"file_uuid: '{escape_str(fa.file_uuid)}', "
            f"path: '{escape_str(file_path)}'}}) "
            f"SET fv.language = '{escape_str(fa.language)}', fv.ts = '{escape_str(ts_iso)}', "
            f"fv.author = '{escape_str(author)}', fv.branch = '{escape_str(branch)}' "
            f"RETURN id(fv)"
        )
        fv_rows = await fetch_cypher(engine, cypher_fv, conn=conn)
        file_version_id = parse_agtype_int(fv_rows[0][0]) if fv_rows else 0

        prev_commit = get_previous_commit_for_file(file_path, commit_id) if commit_id != "local" else None
        if prev_commit:
            cypher_link = (
                f"MATCH (prev:FileVersion {{commit_id: '{escape_str(prev_commit)}', "
                f"path: '{escape_str(file_path)}'}}) "
                f"MATCH (cur) WHERE id(cur) = {file_version_id} "
                f"MERGE (prev)-[r:NEXT_VERSION]->(cur) RETURN id(r)"
            )
            await execute_cypher(engine, cypher_link, conn=conn)
        t_fv = time.perf_counter() - t0

        # Batch lookup existing nodes by span_key
        t0 = time.perf_counter()
        all_span_keys = [p["span_key"] for p in node_props]
        span_to_id = await _batch_lookup_spans(engine, all_span_keys, conn=conn)

        # Separate new vs existing nodes
        new_indices: list[int] = []
        new_props: list[dict[str, Any]] = []
        index_to_age_id: dict[int, int] = {}
        for i, props in enumerate(node_props):
            sk = props["span_key"]
            if sk in span_to_id:
                index_to_age_id[i] = span_to_id[sk]
            else:
                new_indices.append(i)
                new_props.append(props)

        # Batch create new nodes
        if new_props:
            created_ids = await _batch_create_nodes(engine, new_props, conn=conn)
            for list_pos, node_idx in enumerate(new_indices):
                index_to_age_id[node_idx] = created_ids[list_pos]
        t_nodes = time.perf_counter() - t0

        # Batch create edges
        t0 = time.perf_counter()
        # Map edge tuples from list indices to AGE IDs
        age_edge_triples = [
            (index_to_age_id[parent_idx], index_to_age_id[child_idx], child_order)
            for parent_idx, child_idx, child_order in edge_tuples
        ]
        await _batch_edge_guard(engine, age_edge_triples, conn=conn)
        await _batch_parent_edges(engine, age_edge_triples, conn=conn)

        # Batch create OCCURS_IN edges
        age_occurs = [(index_to_age_id[node_idx], sb, eb) for node_idx, sb, eb in occurrence_tuples]
        await _batch_occurs_edges(engine, age_occurs, file_version_id, commit_id, fa.file_uuid, conn=conn)
        t_edges = time.perf_counter() - t0

    t_elapsed = time.perf_counter() - t_total
    logger.info(
        "ingest %s: %d nodes (%d new), %.2fs total "
        "(ensure_graph=%.2fs, git=%.2fs, collect=%.2fs, file_version=%.2fs, "
        "nodes+lookup=%.2fs, edges+occurs=%.2fs)",
        file_path,
        len(node_props),
        len(new_props) if new_props else 0,
        t_elapsed,
        t_ensure,
        t_git,
        t_collect,
        t_fv,
        t_nodes,
        t_edges,
    )


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

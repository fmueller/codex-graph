import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_graph.db.git import get_git_commit_info
from codex_graph.db.helpers import compute_shape_hash, make_span_key
from codex_graph.models import AstNode, FileAst


@dataclass(frozen=True)
class InMemoryFileRecord:
    file_id: str
    name: str
    full_path: str
    suffix: str
    content: str
    content_hash: str
    created: datetime
    last_modified: datetime


@dataclass(frozen=True)
class InMemoryFileVersion:
    version_id: int
    commit_id: str
    file_uuid: str
    path: str
    language: str
    timestamp: str
    author: str


@dataclass(frozen=True)
class InMemoryAstNode:
    node_id: int
    file_uuid: str
    node_type: str
    start_byte: int
    end_byte: int
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    span_key: str
    shape_hash: str


@dataclass(frozen=True)
class InMemoryOccurrence:
    node_id: int
    file_version_id: int
    commit_id: str
    file_uuid: str
    start_byte: int
    end_byte: int


class InMemoryGraphDatabase:
    def __init__(self) -> None:
        self.files: dict[str, InMemoryFileRecord] = {}
        self.files_by_path_hash: dict[tuple[str, str], str] = {}
        self.file_versions: list[InMemoryFileVersion] = []
        self.ast_nodes: dict[int, InMemoryAstNode] = {}
        self.ast_nodes_by_span: dict[str, int] = {}
        self.ast_nodes_by_shape: dict[str, int] = {}
        self.parent_edges: set[tuple[int, int, int]] = set()
        self.occurrences: list[InMemoryOccurrence] = []
        self._next_node_id = 1
        self._next_file_version_id = 1

    async def persist_file(self, path: str) -> str:
        file_path = Path(path)
        full_path = str(file_path.resolve())
        name = file_path.name
        suffix = file_path.suffix
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_bytes().decode("utf-8", errors="replace")

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing_id = self.files_by_path_hash.get((full_path, content_hash))
        if existing_id is not None:
            return existing_id

        stat = file_path.stat()
        created_dt = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
        modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        file_id = str(uuid.uuid4())
        record = InMemoryFileRecord(
            file_id=file_id,
            name=name,
            full_path=full_path,
            suffix=suffix,
            content=content,
            content_hash=content_hash,
            created=created_dt,
            last_modified=modified_dt,
        )
        self.files[file_id] = record
        self.files_by_path_hash[(full_path, content_hash)] = file_id
        return file_id

    async def persist_file_ast(self, fa: FileAst, file_path: str) -> None:
        git_info = get_git_commit_info(file_path)
        commit_id = git_info.commit_id if git_info else "local"
        author = git_info.author if git_info else "local"
        ts_iso = git_info.timestamp if git_info else datetime.now(timezone.utc).isoformat()

        file_version_id = self._next_file_version_id
        self._next_file_version_id += 1
        self.file_versions.append(
            InMemoryFileVersion(
                version_id=file_version_id,
                commit_id=commit_id,
                file_uuid=fa.file_uuid,
                path=file_path,
                language=fa.language,
                timestamp=ts_iso,
                author=author,
            )
        )

        occurrences: list[tuple[int, int, int]] = []
        source_bytes = Path(file_path).read_bytes()
        self._ingest_node(fa.ast, fa.file_uuid, source_bytes, occurrences)

        for node_id, start_b, end_b in occurrences:
            self.occurrences.append(
                InMemoryOccurrence(
                    node_id=node_id,
                    file_version_id=file_version_id,
                    commit_id=commit_id,
                    file_uuid=fa.file_uuid,
                    start_byte=start_b,
                    end_byte=end_b,
                )
            )

    async def ensure_ready(self) -> None:
        pass

    async def fetch_cypher(self, cypher: str, columns: int | None = None) -> list[tuple[Any, ...]]:
        return []

    async def get_file_by_id(self, file_uuid: str) -> tuple[str, str, str, str] | None:
        record = self.files.get(file_uuid)
        if record is None:
            return None
        return (record.file_id, record.full_path, record.suffix, record.content_hash)

    async def list_files(self, limit: int = 50) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        for record in list(self.files.values())[:limit]:
            rows.append((record.file_id, record.full_path, record.suffix, record.content_hash))
        return rows

    async def list_files_cursor(
        self,
        limit: int = 50,
        after_path: str | None = None,
        after_id: str | None = None,
        before_path: str | None = None,
        before_id: str | None = None,
    ) -> list[tuple[str, str, str, str]]:
        all_files = sorted(self.files.values(), key=lambda r: (r.full_path, r.file_id))

        if after_path is not None and after_id is not None:
            all_files = [r for r in all_files if (r.full_path, r.file_id) > (after_path, after_id)]
        elif before_path is not None and before_id is not None:
            all_files = [r for r in all_files if (r.full_path, r.file_id) < (before_path, before_id)]
            all_files = all_files[-limit:]

        return [(r.file_id, r.full_path, r.suffix, r.content_hash) for r in all_files[:limit]]

    async def get_language_for_file(self, file_uuid: str) -> str:
        for fv in self.file_versions:
            if fv.file_uuid == file_uuid:
                return fv.language
        return ""

    async def get_languages_for_files(self, file_uuids: list[str]) -> dict[str, str]:
        uuid_set = set(file_uuids)
        result: dict[str, str] = {}
        for fv in self.file_versions:
            if fv.file_uuid in uuid_set:
                result[fv.file_uuid] = fv.language
        return result

    async def get_node_details(self, span_keys: list[str]) -> dict[str, tuple[Any, ...]]:
        key_set = set(span_keys)
        result: dict[str, tuple[Any, ...]] = {}
        for node in self.ast_nodes.values():
            if node.span_key in key_set:
                result[node.span_key] = (
                    node.span_key,
                    node.node_type,
                    node.start_row,
                    node.start_col,
                    node.end_row,
                    node.end_col,
                    node.start_byte,
                    node.end_byte,
                    node.shape_hash,
                    node.file_uuid,
                )
        return result

    async def ping(self) -> bool:
        return True

    async def dispose(self) -> None:
        pass

    def _ingest_node(
        self,
        node: AstNode,
        file_uuid: str,
        source_bytes: bytes,
        occurrences: list[tuple[int, int, int]],
    ) -> tuple[int, str]:
        child_ids: list[int] = []
        child_shapes: list[str] = []
        if node.children:
            for child in node.children:
                child_id, child_shape = self._ingest_node(child, file_uuid, source_bytes, occurrences)
                child_ids.append(child_id)
                child_shapes.append(child_shape)

        span_key = make_span_key(file_uuid, node.type, node.start_byte, node.end_byte)
        src_slice = source_bytes[node.start_byte : node.end_byte]
        shape_hash = compute_shape_hash(node.type, src_slice, child_shapes)

        node_id = self.ast_nodes_by_span.get(span_key)
        if node_id is None:
            node_id = self.ast_nodes_by_shape.get(shape_hash)

        if node_id is None:
            node_id = self._next_node_id
            self._next_node_id += 1
            self.ast_nodes[node_id] = InMemoryAstNode(
                node_id=node_id,
                file_uuid=file_uuid,
                node_type=node.type,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_row=node.start_point.row,
                start_col=node.start_point.column,
                end_row=node.end_point.row,
                end_col=node.end_point.column,
                span_key=span_key,
                shape_hash=shape_hash,
            )
            self.ast_nodes_by_span[span_key] = node_id
            self.ast_nodes_by_shape[shape_hash] = node_id

        for idx, child_id in enumerate(child_ids):
            self.parent_edges.add((node_id, child_id, idx))

        occurrences.append((node_id, node.start_byte, node.end_byte))
        return node_id, shape_hash

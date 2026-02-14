from typing import Any, Protocol

from codex_graph.models import FileAst


class GraphDatabase(Protocol):
    async def persist_file(self, path: str) -> str: ...

    async def persist_file_ast(self, fa: FileAst, file_path: str) -> None: ...

    async def ensure_ready(self) -> None: ...

    async def fetch_cypher(self, cypher: str, columns: int | None = None) -> list[tuple[Any, ...]]: ...

    async def list_files(self, limit: int = 50) -> list[tuple[str, str, str, str]]: ...

    async def list_files_cursor(
        self,
        limit: int = 50,
        after_path: str | None = None,
        after_id: str | None = None,
        before_path: str | None = None,
        before_id: str | None = None,
    ) -> list[tuple[str, str, str, str]]: ...

    async def ping(self) -> bool: ...

    async def dispose(self) -> None: ...

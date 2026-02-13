from pathlib import Path

from codex_graph.core.ast import extract_ast_from_file
from codex_graph.core.languages import resolve_language, write_temp_code_file
from codex_graph.core.ports.database import GraphDatabase


async def run_ingest(
    database: GraphDatabase,
    path: str | None = None,
    code: str | None = None,
    language: str | None = None,
) -> tuple[str, str]:
    """Ingest a file or code snippet into the graph database.

    Returns (file_uuid, resolved_language).
    """
    temp_path: Path | None = None
    file_path = Path(path) if path and code is None else None
    resolved_language = resolve_language(language, file_path)

    if code is not None:
        temp_path = write_temp_code_file(code, resolved_language)
        file_path = temp_path

    assert file_path is not None

    try:
        resolved_path = str(file_path)
        file_uuid = await database.persist_file(resolved_path)
        ast = extract_ast_from_file(resolved_path, file_uuid, resolved_language)
        await database.persist_file_ast(ast, resolved_path)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)

    return file_uuid, resolved_language

import argparse
import asyncio
import tempfile
from pathlib import Path
from typing import cast

from tree_sitter import Node, Query
from tree_sitter_language_pack import SupportedLanguage, get_language, get_parser

from codex_graph.db import GRAPH_NAME, PostgresGraphDatabase, _get_engine
from codex_graph.models import AstNode, FileAst, Position

_LANGUAGE_ALIASES = {
    "c#": "csharp",
    "csharp": "csharp",
    "cpp": "cpp",
    "c++": "cpp",
    "cs": "csharp",
    "css": "css",
    "go": "go",
    "golang": "go",
    "html": "html",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "json": "json",
    "md": "markdown",
    "markdown": "markdown",
    "python": "python",
    "py": "python",
    "rb": "ruby",
    "ruby": "ruby",
    "rs": "rust",
    "rust": "rust",
    "toml": "toml",
    "ts": "typescript",
    "tsx": "tsx",
    "typescript": "typescript",
    "yaml": "yaml",
    "yml": "yaml",
    "c": "c",
}

_EXTENSION_LANGUAGE_MAP = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".cxx": "cpp",
    ".go": "go",
    ".h": "c",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".htm": "html",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".md": "markdown",
    ".markdown": "markdown",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scss": "css",
    ".css": "css",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".yaml": "yaml",
    ".yml": "yaml",
}

_LANGUAGE_DEFAULT_EXTENSIONS = {
    "c": ".c",
    "cpp": ".cpp",
    "csharp": ".cs",
    "css": ".css",
    "go": ".go",
    "html": ".html",
    "java": ".java",
    "javascript": ".js",
    "json": ".json",
    "markdown": ".md",
    "python": ".py",
    "ruby": ".rb",
    "rust": ".rs",
    "toml": ".toml",
    "tsx": ".tsx",
    "typescript": ".ts",
    "yaml": ".yml",
}

_SUPPORTED_LANGUAGES = set(_LANGUAGE_DEFAULT_EXTENSIONS)


def _normalize_language(language: str) -> str:
    normalized = language.strip().lower()
    resolved = _LANGUAGE_ALIASES.get(normalized, normalized)
    if resolved not in _SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language '{language}'. Supported: {sorted(_SUPPORTED_LANGUAGES)}")
    return resolved


def _detect_language_from_path(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in _EXTENSION_LANGUAGE_MAP:
        return _EXTENSION_LANGUAGE_MAP[suffix]
    raise ValueError(f"Unsupported file extension: {suffix}")


def _load_query(language: str, query_type: str) -> Query:
    queries_dir = Path(__file__).parent / "queries"
    query_path = queries_dir / f"{language}_{query_type}.scm"
    if not query_path.exists():
        raise FileNotFoundError(f"Query file not found: {query_path}")
    query_text = query_path.read_text(encoding="utf-8")
    return Query(get_language(cast(SupportedLanguage, language)), query_text)


def _extract_ast_from_source(source_bytes: bytes, file_uuid: str, language: str) -> FileAst:
    parser = get_parser(cast(SupportedLanguage, language))
    tree = parser.parse(source_bytes)

    _load_query(language, "detailed")

    root = tree.root_node

    def node_to_model(node: Node) -> AstNode:
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
        language=language,
        ast=node_to_model(root),
    )


def _extract_ast_from_file(path: str, file_uuid: str, language: str | None = None) -> FileAst:
    """
    Parses the AST from the given Python file.

    :param path: Path to the Python file.
    :param file_uuid: UUID of the file to use in the AST.
    :return: FileAst model with AST data.
    """

    file_path = Path(path)
    resolved_language = _normalize_language(language) if language else _detect_language_from_path(file_path)

    try:
        source_bytes = file_path.read_bytes()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}") from None

    return _extract_ast_from_source(source_bytes, file_uuid, resolved_language)


def _resolve_language(language: str | None, file_path: Path | None) -> str:
    if language:
        return _normalize_language(language)
    if file_path:
        return _detect_language_from_path(file_path)
    raise ValueError("Language must be provided when no file path is available.")


def _write_temp_code_file(source: str, language: str) -> Path:
    suffix = _LANGUAGE_DEFAULT_EXTENSIONS.get(language, ".txt")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(source.encode("utf-8"))
        temp_file.flush()
        return Path(temp_file.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest code into the Codex graph.")
    parser.add_argument("path", nargs="?", default="src/codex_graph/main.py", help="Path to code file to ingest.")
    parser.add_argument("--code", help="Source code string to ingest instead of a file path.")
    parser.add_argument(
        "--language",
        help="Language name or code (e.g. python, js, ts, csharp). Required with --code.",
    )
    args = parser.parse_args()

    temp_path: Path | None = None
    file_path = Path(args.path) if args.code is None else None
    resolved_language = _resolve_language(args.language, file_path)

    if args.code is not None:
        temp_path = _write_temp_code_file(args.code, resolved_language)
        file_path = temp_path

    assert file_path is not None

    async def _runner() -> None:
        engine = _get_engine()
        database = PostgresGraphDatabase(engine)
        try:
            resolved_path = str(file_path)
            file_uuid = await database.persist_file(resolved_path)
            print(f"Persisted file {file_path} with UUID {file_uuid}")

            ast = _extract_ast_from_file(resolved_path, file_uuid, resolved_language)
            print(f"Extracted AST from {file_path}")

            await database.persist_file_ast(ast, resolved_path)
            print(f"Persisted AST to {GRAPH_NAME}")
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)
            await database.dispose()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()

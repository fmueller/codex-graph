from pathlib import Path
from typing import cast

from tree_sitter import Node, Query
from tree_sitter_language_pack import SupportedLanguage, get_language, get_parser

from codex_graph.core.languages import detect_language_from_path, normalize_language
from codex_graph.models import AstNode, FileAst, Position


def _load_query(language: str, query_type: str) -> Query:
    queries_dir = Path(__file__).parent.parent / "queries"
    query_path = queries_dir / f"{language}_{query_type}.scm"
    if not query_path.exists():
        raise FileNotFoundError(f"Query file not found: {query_path}")
    query_text = query_path.read_text(encoding="utf-8")
    return Query(get_language(cast(SupportedLanguage, language)), query_text)


def extract_ast_from_source(source_bytes: bytes, file_uuid: str, language: str) -> FileAst:
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


def extract_ast_from_file(path: str, file_uuid: str, language: str | None = None) -> FileAst:
    file_path = Path(path)
    resolved_language = normalize_language(language) if language else detect_language_from_path(file_path)

    try:
        source_bytes = file_path.read_bytes()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}") from None

    return extract_ast_from_source(source_bytes, file_uuid, resolved_language)

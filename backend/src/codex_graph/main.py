import asyncio
from pathlib import Path

from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

from codex_graph.db import GRAPH_NAME, PostgresGraphDatabase, _get_engine
from codex_graph.models import AstNode, FileAst, Position


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
        language="python",
        ast=node_to_model(root),
    )


def main() -> None:
    file_path = "src/codex_graph/main.py"

    async def _runner() -> None:
        engine = _get_engine()
        database = PostgresGraphDatabase(engine)
        try:
            file_uuid = await database.persist_file(file_path)
            print(f"Persisted file {file_path} with UUID {file_uuid}")

            ast = _extract_ast_from_file(file_path, file_uuid)
            print(f"Extracted AST from {file_path}")

            await database.persist_file_ast(ast, file_path)
            print(f"Persisted AST to {GRAPH_NAME}")
        finally:
            await database.dispose()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()

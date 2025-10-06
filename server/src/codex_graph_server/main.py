from pathlib import Path

from pydantic import BaseModel
from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser


class Position(BaseModel):
    row: int
    column: int


class AstNode(BaseModel):
    type: str
    start_byte: int
    end_byte: int
    start_point: Position
    end_point: Position
    text: str | None = None
    children: list["AstNode"] | None = None


AstNode.model_rebuild()


class FileAst(BaseModel):
    language: str
    path: str
    ast: AstNode


def extract_ast_from_file(path: str) -> FileAst:
    """
    Parses the AST from the given Python file.

    :param path: Path to the Python file.
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

    with open("src/codex_graph_server/queries/python_detailed.scm", encoding="utf-8") as f:
        query_text = f.read()
    query = Query(get_language("python"), query_text)
    cursor = QueryCursor(query)
    for _, captures in cursor.matches(tree.root_node):
        for cap_name, nodes in captures.items():
            for node in nodes:
                text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
                print(cap_name + ": " + text)

    root = tree.root_node

    def node_to_model(node) -> AstNode:
        # Convert a tree-sitter Node into an AstNode model
        children = None
        text_value = None

        if node.child_count > 0:
            children = [node_to_model(child) for child in node.children]
        else:
            try:
                text_value = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
            except Exception:
                text_value = ""

        return AstNode(
            type=node.type,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_point=Position(row=node.start_point[0], column=node.start_point[1]),
            end_point=Position(row=node.end_point[0], column=node.end_point[1]),
            text=text_value,
            children=children,
        )

    ast_model = FileAst(
        language="python",
        path=str(file_path),
        ast=node_to_model(root),
    )
    return ast_model


def main() -> None:
    ast = extract_ast_from_file("src/codex_graph_server/main.py")
    print(ast)


if __name__ == "__main__":
    main()

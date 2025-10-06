from pathlib import Path
from typing import Any, Dict

from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_parser, get_language


def extract_ast_from_file(path: str) -> Dict[str, Any]:
    """
    Parses the AST from the given Python file.

    :param path: Path to the Python file.
    :return: Dict with AST data.
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

    query = Query(get_language("python"), open("src/codex_graph_server/queries/python_detailed.scm").read())
    cursor = QueryCursor(query)
    for pattern_idx, captures in cursor.matches(tree.root_node):
        for cap_name, nodes in captures.items():
            for node in nodes:
                text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
                print(cap_name + ": " + text)

    root = tree.root_node

    def node_to_dict(node) -> Dict[str, Any]:
        # Convert a tree-sitter Node into a serializable dict
        data: Dict[str, Any] = {
            "type": node.type,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "start_point": {"row": node.start_point[0], "column": node.start_point[1]},
            "end_point": {"row": node.end_point[0], "column": node.end_point[1]},
        }

        # Include children if present; otherwise include the leaf text
        if node.child_count > 0:
            data["children"] = [node_to_dict(child) for child in node.children]
        else:
            # Leaf node text (can be useful for identifiers/literals)
            # Decode safely to avoid errors on odd encodings
            try:
                data["text"] = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            except Exception:  # pragma: no cover
                data["text"] = ""
        return data

    ast_dict = {
        "language": "python",
        "path": str(file_path),
        "ast": node_to_dict(root),
    }
    return ast_dict


def main() -> None:
    ast = extract_ast_from_file("src/codex_graph_server/main.py")
    print(ast)


if __name__ == "__main__":
    main()

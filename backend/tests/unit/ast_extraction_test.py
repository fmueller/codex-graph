"""Unit tests for AST extraction functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codex_graph.main import _extract_ast_from_file
from codex_graph.models import AstNode, FileAst


class TestExtractAstFromFile:
    """Tests for _extract_ast_from_file function."""

    def test_extracts_ast_from_simple_python_file(self, tmp_path: Path) -> None:
        """Test extracting AST from a simple Python file."""
        py_file = tmp_path / "simple.py"
        py_file.write_text("x = 1")

        file_uuid = "test-uuid-123"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        assert isinstance(result, FileAst)
        assert result.file_uuid == file_uuid
        assert result.language == "python"
        assert isinstance(result.ast, AstNode)
        assert result.ast.type == "module"

    def test_extracts_ast_from_function_definition(self, tmp_path: Path) -> None:
        """Test extracting AST from a file with a function definition."""
        py_file = tmp_path / "func.py"
        py_file.write_text("""
def hello():
    return "world"
""")

        file_uuid = "test-uuid-func"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        assert result.ast.type == "module"
        assert result.ast.children is not None
        assert len(result.ast.children) > 0

        function_found = any(child.type == "function_definition" for child in result.ast.children)
        assert function_found

    def test_extracts_ast_from_class_definition(self, tmp_path: Path) -> None:
        """Test extracting AST from a file with a class definition."""
        py_file = tmp_path / "cls.py"
        py_file.write_text("""
class MyClass:
    def __init__(self):
        self.value = 42
""")

        file_uuid = "test-uuid-class"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        assert result.ast.type == "module"
        assert result.ast.children is not None

        class_found = any(child.type == "class_definition" for child in result.ast.children)
        assert class_found

    def test_extracts_ast_with_correct_positions(self, tmp_path: Path) -> None:
        """Test that AST extraction captures correct byte positions."""
        py_file = tmp_path / "positions.py"
        content = "x = 1\ny = 2"
        py_file.write_text(content)

        file_uuid = "test-uuid-pos"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        assert result.ast.start_byte == 0
        assert result.ast.end_byte == len(content)
        assert result.ast.start_point.row == 0
        assert result.ast.start_point.column == 0

    def test_rejects_unknown_extension(self, tmp_path: Path) -> None:
        """Test that unsupported extensions are rejected."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("Hello, world!")

        file_uuid = "test-uuid-txt"

        with pytest.raises(ValueError, match="Unsupported file extension"):
            _extract_ast_from_file(str(txt_file), file_uuid)

    def test_accepts_javascript_file(self, tmp_path: Path) -> None:
        """Test that JavaScript files are accepted."""
        js_file = tmp_path / "script.js"
        js_file.write_text("const x = 1;")

        file_uuid = "test-uuid-js"

        result = _extract_ast_from_file(str(js_file), file_uuid)
        assert result.language == "javascript"
        assert result.ast.type == "program"

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        """Test that missing files raise FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.py"

        file_uuid = "test-uuid-missing"

        with pytest.raises(FileNotFoundError, match="File not found"):
            _extract_ast_from_file(str(nonexistent), file_uuid)

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """Test extracting AST from an empty Python file."""
        py_file = tmp_path / "empty.py"
        py_file.write_text("")

        file_uuid = "test-uuid-empty"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        assert result.ast.type == "module"
        assert result.ast.children is None or len(result.ast.children) == 0

    def test_handles_unicode_content(self, tmp_path: Path) -> None:
        """Test extracting AST from a file with Unicode content."""
        py_file = tmp_path / "unicode.py"
        py_file.write_text('message = "Hello, 世界! 🌍"', encoding="utf-8")

        file_uuid = "test-uuid-unicode"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        assert result.ast.type == "module"
        assert result.ast.children is not None

    def test_ast_node_children_are_recursive(self, tmp_path: Path) -> None:
        """Test that AST nodes have recursive children structure."""
        py_file = tmp_path / "nested.py"
        py_file.write_text("""
def outer():
    def inner():
        pass
""")

        file_uuid = "test-uuid-nested"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        def find_node_types(node: AstNode, types: set[str]) -> None:
            types.add(node.type)
            if node.children:
                for child in node.children:
                    find_node_types(child, types)

        node_types: set[str] = set()
        find_node_types(result.ast, node_types)

        assert "module" in node_types
        assert "function_definition" in node_types
        assert "identifier" in node_types

    def test_all_nodes_have_file_uuid(self, tmp_path: Path) -> None:
        """Test that all AST nodes have the correct file_uuid."""
        py_file = tmp_path / "uuid_check.py"
        py_file.write_text("x = 1")

        file_uuid = "unique-file-uuid"

        with patch("codex_graph.main.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda s, *args: None
            mock_open.return_value.read.return_value = ""

            result = _extract_ast_from_file(str(py_file), file_uuid)

        def check_file_uuid(node: AstNode) -> bool:
            if node.file_uuid != file_uuid:
                return False
            if node.children:
                return all(check_file_uuid(child) for child in node.children)
            return True

        assert check_file_uuid(result.ast)

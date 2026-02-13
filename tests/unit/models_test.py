"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from codex_graph.models import AstNode, FileAst, Position


class TestPositionModel:
    """Tests for the Position model."""

    def test_creates_position_with_valid_data(self) -> None:
        """Test creating a Position with valid row and column."""
        pos = Position(row=0, column=5)
        assert pos.row == 0
        assert pos.column == 5

    def test_creates_position_with_large_values(self) -> None:
        """Test creating a Position with large values."""
        pos = Position(row=1000000, column=500)
        assert pos.row == 1000000
        assert pos.column == 500

    def test_position_is_immutable_by_default(self) -> None:
        """Test that Position fields can be accessed."""
        pos = Position(row=1, column=2)
        assert pos.row == 1
        assert pos.column == 2

    def test_position_requires_row(self) -> None:
        """Test that Position requires row field."""
        with pytest.raises(ValidationError):
            Position(column=0)  # type: ignore[call-arg]

    def test_position_requires_column(self) -> None:
        """Test that Position requires column field."""
        with pytest.raises(ValidationError):
            Position(row=0)  # type: ignore[call-arg]

    def test_position_serializes_to_dict(self) -> None:
        """Test that Position can be serialized to dict."""
        pos = Position(row=10, column=20)
        data = pos.model_dump()
        assert data == {"row": 10, "column": 20}

    def test_position_from_dict(self) -> None:
        """Test creating Position from dict."""
        data = {"row": 5, "column": 15}
        pos = Position.model_validate(data)
        assert pos.row == 5
        assert pos.column == 15


class TestAstNodeModel:
    """Tests for the AstNode model."""

    def test_creates_ast_node_without_children(self) -> None:
        """Test creating an AstNode without children."""
        node = AstNode(
            file_uuid="abc-123",
            type="identifier",
            start_byte=0,
            end_byte=5,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=5),
        )
        assert node.file_uuid == "abc-123"
        assert node.type == "identifier"
        assert node.start_byte == 0
        assert node.end_byte == 5
        assert node.children is None

    def test_creates_ast_node_with_children(self) -> None:
        """Test creating an AstNode with children."""
        child = AstNode(
            file_uuid="abc-123",
            type="identifier",
            start_byte=0,
            end_byte=1,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=1),
        )
        parent = AstNode(
            file_uuid="abc-123",
            type="assignment",
            start_byte=0,
            end_byte=5,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=5),
            children=[child],
        )
        assert parent.children is not None
        assert len(parent.children) == 1
        assert parent.children[0].type == "identifier"

    def test_creates_nested_ast_nodes(self) -> None:
        """Test creating deeply nested AstNode structure."""
        leaf = AstNode(
            file_uuid="uuid",
            type="number",
            start_byte=4,
            end_byte=5,
            start_point=Position(row=0, column=4),
            end_point=Position(row=0, column=5),
        )
        middle = AstNode(
            file_uuid="uuid",
            type="expression",
            start_byte=0,
            end_byte=5,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=5),
            children=[leaf],
        )
        root = AstNode(
            file_uuid="uuid",
            type="module",
            start_byte=0,
            end_byte=5,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=5),
            children=[middle],
        )
        assert root.children is not None
        assert root.children[0].children is not None
        assert root.children[0].children[0].type == "number"

    def test_ast_node_requires_file_uuid(self) -> None:
        """Test that AstNode requires file_uuid."""
        with pytest.raises(ValidationError):
            AstNode(  # type: ignore[call-arg]
                type="identifier",
                start_byte=0,
                end_byte=1,
                start_point=Position(row=0, column=0),
                end_point=Position(row=0, column=1),
            )

    def test_ast_node_requires_type(self) -> None:
        """Test that AstNode requires type."""
        with pytest.raises(ValidationError):
            AstNode(  # type: ignore[call-arg]
                file_uuid="uuid",
                start_byte=0,
                end_byte=1,
                start_point=Position(row=0, column=0),
                end_point=Position(row=0, column=1),
            )

    def test_ast_node_serializes_to_dict(self) -> None:
        """Test that AstNode can be serialized to dict."""
        node = AstNode(
            file_uuid="uuid-123",
            type="module",
            start_byte=0,
            end_byte=10,
            start_point=Position(row=0, column=0),
            end_point=Position(row=1, column=0),
        )
        data = node.model_dump()
        assert data["file_uuid"] == "uuid-123"
        assert data["type"] == "module"
        assert data["start_byte"] == 0
        assert data["end_byte"] == 10
        assert data["children"] is None

    def test_ast_node_serializes_children(self) -> None:
        """Test that AstNode serializes children properly."""
        child = AstNode(
            file_uuid="uuid",
            type="child",
            start_byte=0,
            end_byte=1,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=1),
        )
        parent = AstNode(
            file_uuid="uuid",
            type="parent",
            start_byte=0,
            end_byte=5,
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=5),
            children=[child],
        )
        data = parent.model_dump()
        assert data["children"] is not None
        assert len(data["children"]) == 1
        assert data["children"][0]["type"] == "child"

    def test_ast_node_from_dict(self) -> None:
        """Test creating AstNode from dict."""
        data = {
            "file_uuid": "test-uuid",
            "type": "module",
            "start_byte": 0,
            "end_byte": 100,
            "start_point": {"row": 0, "column": 0},
            "end_point": {"row": 10, "column": 0},
            "children": None,
        }
        node = AstNode.model_validate(data)
        assert node.file_uuid == "test-uuid"
        assert node.type == "module"
        assert node.start_point.row == 0


class TestFileAstModel:
    """Tests for the FileAst model."""

    def test_creates_file_ast(self) -> None:
        """Test creating a FileAst."""
        root = AstNode(
            file_uuid="file-uuid",
            type="module",
            start_byte=0,
            end_byte=10,
            start_point=Position(row=0, column=0),
            end_point=Position(row=5, column=0),
        )
        file_ast = FileAst(
            file_uuid="file-uuid",
            language="python",
            ast=root,
        )
        assert file_ast.file_uuid == "file-uuid"
        assert file_ast.language == "python"
        assert file_ast.ast.type == "module"

    def test_file_ast_requires_file_uuid(self) -> None:
        """Test that FileAst requires file_uuid."""
        root = AstNode(
            file_uuid="uuid",
            type="module",
            start_byte=0,
            end_byte=10,
            start_point=Position(row=0, column=0),
            end_point=Position(row=1, column=0),
        )
        with pytest.raises(ValidationError):
            FileAst(language="python", ast=root)  # type: ignore[call-arg]

    def test_file_ast_requires_language(self) -> None:
        """Test that FileAst requires language."""
        root = AstNode(
            file_uuid="uuid",
            type="module",
            start_byte=0,
            end_byte=10,
            start_point=Position(row=0, column=0),
            end_point=Position(row=1, column=0),
        )
        with pytest.raises(ValidationError):
            FileAst(file_uuid="uuid", ast=root)  # type: ignore[call-arg]

    def test_file_ast_requires_ast(self) -> None:
        """Test that FileAst requires ast."""
        with pytest.raises(ValidationError):
            FileAst(file_uuid="uuid", language="python")  # type: ignore[call-arg]

    def test_file_ast_serializes_to_dict(self) -> None:
        """Test that FileAst can be serialized to dict."""
        root = AstNode(
            file_uuid="uuid",
            type="module",
            start_byte=0,
            end_byte=10,
            start_point=Position(row=0, column=0),
            end_point=Position(row=1, column=0),
        )
        file_ast = FileAst(
            file_uuid="uuid",
            language="python",
            ast=root,
        )
        data = file_ast.model_dump()
        assert data["file_uuid"] == "uuid"
        assert data["language"] == "python"
        assert data["ast"]["type"] == "module"

    def test_file_ast_from_dict(self) -> None:
        """Test creating FileAst from dict."""
        data = {
            "file_uuid": "test-file",
            "language": "python",
            "ast": {
                "file_uuid": "test-file",
                "type": "module",
                "start_byte": 0,
                "end_byte": 50,
                "start_point": {"row": 0, "column": 0},
                "end_point": {"row": 5, "column": 0},
                "children": None,
            },
        }
        file_ast = FileAst.model_validate(data)
        assert file_ast.file_uuid == "test-file"
        assert file_ast.language == "python"
        assert file_ast.ast.type == "module"

    def test_file_ast_with_complex_ast(self) -> None:
        """Test FileAst with a complex nested AST structure."""
        child1 = AstNode(
            file_uuid="uuid",
            type="function_definition",
            start_byte=0,
            end_byte=20,
            start_point=Position(row=0, column=0),
            end_point=Position(row=2, column=0),
        )
        child2 = AstNode(
            file_uuid="uuid",
            type="class_definition",
            start_byte=21,
            end_byte=50,
            start_point=Position(row=3, column=0),
            end_point=Position(row=6, column=0),
        )
        root = AstNode(
            file_uuid="uuid",
            type="module",
            start_byte=0,
            end_byte=50,
            start_point=Position(row=0, column=0),
            end_point=Position(row=6, column=0),
            children=[child1, child2],
        )
        file_ast = FileAst(
            file_uuid="uuid",
            language="python",
            ast=root,
        )
        assert file_ast.ast.children is not None
        assert len(file_ast.ast.children) == 2
        assert file_ast.ast.children[0].type == "function_definition"
        assert file_ast.ast.children[1].type == "class_definition"

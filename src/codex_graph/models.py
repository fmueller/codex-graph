from pydantic import BaseModel


class Position(BaseModel):
    row: int
    column: int


class AstNode(BaseModel):
    file_uuid: str
    type: str
    start_byte: int
    end_byte: int
    start_point: Position
    end_point: Position
    children: list["AstNode"] | None = None


AstNode.model_rebuild()  # necessary for recursive types


class FileAst(BaseModel):
    file_uuid: str
    language: str
    ast: AstNode

import asyncio
from pathlib import Path

from codex_graph.db import InMemoryGraphDatabase
from codex_graph.models import AstNode, FileAst, Position


def test_in_memory_db_persists_file_versions(tmp_path: Path, in_memory_db: InMemoryGraphDatabase) -> None:
    file_path = tmp_path / "sample.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")

    file_uuid = asyncio.run(in_memory_db.persist_file(str(file_path)))
    source_bytes = file_path.read_bytes()
    ast = FileAst(
        file_uuid=file_uuid,
        language="python",
        ast=AstNode(
            type="module",
            file_uuid=file_uuid,
            start_byte=0,
            end_byte=len(source_bytes),
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=len("print('hello')")),
            children=None,
        ),
    )

    asyncio.run(in_memory_db.persist_file_ast(ast, str(file_path)))

    assert len(in_memory_db.file_versions) == 1
    assert in_memory_db.file_versions[0].file_uuid == file_uuid
    assert in_memory_db.file_versions[0].commit_id == "local"
    assert in_memory_db.file_versions[0].branch == "local"
    assert len(in_memory_db.ast_nodes) == 1
    assert len(in_memory_db.occurrences) == 1


def test_in_memory_db_links_file_version_history(tmp_path: Path, in_memory_db: InMemoryGraphDatabase) -> None:
    file_path = tmp_path / "sample.py"

    file_path.write_text("v1\n", encoding="utf-8")
    file_uuid_1 = asyncio.run(in_memory_db.persist_file(str(file_path)))
    source_bytes_1 = file_path.read_bytes()
    ast_1 = FileAst(
        file_uuid=file_uuid_1,
        language="python",
        ast=AstNode(
            type="module",
            file_uuid=file_uuid_1,
            start_byte=0,
            end_byte=len(source_bytes_1),
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=2),
            children=None,
        ),
    )
    asyncio.run(in_memory_db.persist_file_ast(ast_1, str(file_path)))

    file_path.write_text("v2\n", encoding="utf-8")
    file_uuid_2 = asyncio.run(in_memory_db.persist_file(str(file_path)))
    source_bytes_2 = file_path.read_bytes()
    ast_2 = FileAst(
        file_uuid=file_uuid_2,
        language="python",
        ast=AstNode(
            type="module",
            file_uuid=file_uuid_2,
            start_byte=0,
            end_byte=len(source_bytes_2),
            start_point=Position(row=0, column=0),
            end_point=Position(row=0, column=2),
            children=None,
        ),
    )
    asyncio.run(in_memory_db.persist_file_ast(ast_2, str(file_path)))

    assert len(in_memory_db.file_versions) == 2
    assert len(in_memory_db.file_version_links) == 1
    link = in_memory_db.file_version_links[0]
    assert link.previous_file_version_id == in_memory_db.file_versions[0].version_id
    assert link.next_file_version_id == in_memory_db.file_versions[1].version_id
    assert link.path == str(file_path)

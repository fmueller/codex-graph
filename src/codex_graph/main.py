import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from codex_graph.core.ast import extract_ast_from_file as _extract_ast_from_file
from codex_graph.core.languages import (
    resolve_language as _resolve_language,
)
from codex_graph.core.languages import (
    write_temp_code_file as _write_temp_code_file,
)
from codex_graph.core.query import _escape_str
from codex_graph.db import GRAPH_NAME, PostgresGraphDatabase, _get_engine

_MAX_COL_WIDTH = 80


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    """Print a simple column-aligned text table with a row-count footer."""
    str_rows = [[_truncate(str(v)) for v in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, val in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(val))

    def _fmt_row(values: Sequence[str]) -> str:
        parts = [str(v).ljust(widths[i]) for i, v in enumerate(values)]
        return "  ".join(parts)

    print(_fmt_row(list(headers)))
    print("  ".join("-" * w for w in widths))
    for row in str_rows:
        print(_fmt_row(row))
    print(f"({len(str_rows)} rows)")


def _truncate(value: str, max_width: int = _MAX_COL_WIDTH) -> str:
    if len(value) > max_width:
        return value[: max_width - 3] + "..."
    return value


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex Graph CLI — ingest and query code ASTs.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # -- ingest subcommand --
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a code file into the graph.")
    ingest_parser.add_argument("path", nargs="?", default="src/codex_graph/main.py", help="Path to code file.")
    ingest_parser.add_argument("--code", help="Source code string to ingest instead of a file path.")
    ingest_parser.add_argument("--language", help="Language name or code (e.g. python, js, ts, csharp).")

    # -- query subcommand --
    query_parser = subparsers.add_parser("query", help="Query the ingested graph.")
    query_sub = query_parser.add_subparsers(dest="query_command")
    query_sub.required = True

    # query files
    files_parser = query_sub.add_parser("files", help="List ingested files.")
    files_parser.add_argument("--limit", type=int, default=50, help="Max rows to return (default 50).")

    # query node-types
    nt_parser = query_sub.add_parser("node-types", help="List distinct AST node types.")
    nt_parser.add_argument("--file", help="Filter by file path.")
    nt_parser.add_argument("--limit", type=int, default=50, help="Max rows to return (default 50).")

    # query nodes
    nodes_parser = query_sub.add_parser("nodes", help="Find AST nodes by type.")
    nodes_parser.add_argument("--type", required=True, help="AST node type to search for.")
    nodes_parser.add_argument("--file", help="Filter by file path.")
    nodes_parser.add_argument("--limit", type=int, default=50, help="Max rows to return (default 50).")

    # query children
    children_parser = query_sub.add_parser("children", help="List ordered children of a node.")
    children_parser.add_argument("--span-key", required=True, help="Span key of the parent node.")
    children_parser.add_argument("--limit", type=int, default=50, help="Max rows to return (default 50).")

    # query cypher
    cypher_parser = query_sub.add_parser("cypher", help="Run a raw Cypher query.")
    cypher_parser.add_argument("query_string", help="Cypher query to execute.")
    cypher_parser.add_argument(
        "--columns", type=int, default=1, help="Number of RETURN columns in the query (default 1)."
    )

    return parser


# ---------------------------------------------------------------------------
# Ingest handler
# ---------------------------------------------------------------------------


async def _run_ingest(args: argparse.Namespace) -> None:
    temp_path: Path | None = None
    file_path = Path(args.path) if args.code is None else None
    resolved_language = _resolve_language(args.language, file_path)

    if args.code is not None:
        temp_path = _write_temp_code_file(args.code, resolved_language)
        file_path = temp_path

    assert file_path is not None

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


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------


async def _run_query(args: argparse.Namespace, database: PostgresGraphDatabase | None = None) -> None:
    owns_db = database is None
    if database is None:
        engine = _get_engine()
        database = PostgresGraphDatabase(engine)

    try:
        await database.ensure_ready()
        cmd: str = args.query_command

        if cmd == "files":
            await _query_files(args, database)
        elif cmd == "node-types":
            await _query_node_types(args, database)
        elif cmd == "nodes":
            await _query_nodes(args, database)
        elif cmd == "children":
            await _query_children(args, database)
        elif cmd == "cypher":
            await _query_cypher(args, database)
    finally:
        if owns_db:
            await database.dispose()


async def _query_files(args: argparse.Namespace, database: PostgresGraphDatabase) -> None:
    rows = await database.list_files(args.limit)
    _print_table(["id", "full_path", "suffix", "content_hash"], rows)


async def _query_node_types(args: argparse.Namespace, database: PostgresGraphDatabase) -> None:
    file_filter: str | None = getattr(args, "file", None)
    limit: int = getattr(args, "limit", 50)
    if file_filter:
        cypher = (
            f"MATCH (n:AstNode)-[:OCCURS_IN]->(fv:FileVersion {{path: '{_escape_str(file_filter)}'}}) "
            f"RETURN DISTINCT n.type ORDER BY n.type LIMIT {limit}"
        )
    else:
        cypher = f"MATCH (n:AstNode) RETURN DISTINCT n.type ORDER BY n.type LIMIT {limit}"
    rows = await database.fetch_cypher(cypher)
    _print_table(["type"], rows)


async def _query_nodes(args: argparse.Namespace, database: PostgresGraphDatabase) -> None:
    node_type: str = args.type
    file_filter: str | None = getattr(args, "file", None)
    limit: int = getattr(args, "limit", 50)
    if file_filter:
        cypher = (
            f"MATCH (n:AstNode {{type: '{_escape_str(node_type)}'}})"
            f"-[:OCCURS_IN]->(fv:FileVersion {{path: '{_escape_str(file_filter)}'}}) "
            f"RETURN n.span_key, n.type, n.start_byte, n.end_byte LIMIT {limit}"
        )
    else:
        cypher = (
            f"MATCH (n:AstNode {{type: '{_escape_str(node_type)}'}}) "
            f"RETURN n.span_key, n.type, n.start_byte, n.end_byte LIMIT {limit}"
        )
    rows = await database.fetch_cypher(cypher, columns=4)
    _print_table(["span_key", "type", "start_byte", "end_byte"], rows)


async def _query_children(args: argparse.Namespace, database: PostgresGraphDatabase) -> None:
    span_key: str = args.span_key
    limit: int = getattr(args, "limit", 50)
    cypher = (
        f"MATCH (p:AstNode {{span_key: '{_escape_str(span_key)}'}})-[e:PARENT_OF]->(c:AstNode) "
        f"RETURN c.span_key, c.type, e.child_index ORDER BY e.child_index LIMIT {limit}"
    )
    rows = await database.fetch_cypher(cypher, columns=3)
    _print_table(["span_key", "type", "child_index"], rows)


async def _query_cypher(args: argparse.Namespace, database: PostgresGraphDatabase) -> None:
    query_string: str = args.query_string
    columns: int = args.columns
    rows = await database.fetch_cypher(query_string, columns=columns)
    if rows:
        headers = [f"col{i}" for i in range(len(rows[0]))]
        _print_table(headers, rows)
    else:
        print("(0 rows)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        asyncio.run(_run_ingest(args))
    elif args.command == "query":
        asyncio.run(_run_query(args))


if __name__ == "__main__":
    main()

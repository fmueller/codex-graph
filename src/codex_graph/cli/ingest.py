import asyncio
from typing import Annotated

import typer
from rich.console import Console

from codex_graph.core.ingest import run_ingest
from codex_graph.db.engine import get_engine
from codex_graph.db.helpers import GRAPH_NAME
from codex_graph.db.postgres import PostgresGraphDatabase

console = Console()


def ingest(
    path: Annotated[str, typer.Argument(help="Path to code file.")] = "src/codex_graph/main.py",
    code: Annotated[str | None, typer.Option(help="Source code string to ingest instead of a file path.")] = None,
    language: Annotated[str | None, typer.Option(help="Language name or code (e.g. python, js, ts, csharp).")] = None,
) -> None:
    """Ingest a code file into the graph."""
    engine = get_engine()
    database = PostgresGraphDatabase(engine)

    async def _run() -> None:
        try:
            file_uuid, resolved_language = await run_ingest(
                database,
                path=path if code is None else None,
                code=code,
                language=language,
            )
            console.print(f"[green]Persisted[/green] file with UUID {file_uuid}")
            console.print(f"[green]Extracted[/green] AST (language: {resolved_language})")
            console.print(f"[green]Persisted[/green] AST to {GRAPH_NAME}")
        finally:
            await database.dispose()

    asyncio.run(_run())

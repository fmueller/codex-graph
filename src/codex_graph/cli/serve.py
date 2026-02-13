import typer
from rich.console import Console

serve_app = typer.Typer(help="Start servers.")
console = Console()


@serve_app.command("api")
def api(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Start the FastAPI REST API server."""
    import uvicorn

    from codex_graph.api.app import create_app

    app = create_app()
    console.print(f"[green]Starting API server on {host}:{port}[/green]")
    uvicorn.run(app, host=host, port=port)


@serve_app.command("mcp")
def mcp(
    transport: str = "stdio",
) -> None:
    """Start the MCP server."""
    from codex_graph.db.engine import get_engine
    from codex_graph.db.postgres import PostgresGraphDatabase
    from codex_graph.mcp.server import create_mcp_server

    db = PostgresGraphDatabase(get_engine())
    server = create_mcp_server(db)
    console.print(f"[green]Starting MCP server (transport: {transport})[/green]")
    server.run(transport=transport)  # type: ignore[arg-type]


@serve_app.command("dashboard")
def dashboard(
    host: str = "127.0.0.1",
    port: int = 8001,
) -> None:
    """Start the Dash web dashboard."""
    from codex_graph.dashboard.app import create_dashboard
    from codex_graph.db.engine import get_engine
    from codex_graph.db.postgres import PostgresGraphDatabase

    db = PostgresGraphDatabase(get_engine())
    app = create_dashboard(db)
    console.print(f"[green]Starting dashboard on {host}:{port}[/green]")
    app.run(host=host, port=port)


@serve_app.callback(invoke_without_command=True)
def serve_all(
    ctx: typer.Context,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> None:
    """Start all servers (API + MCP + dashboard)."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]Combined serve not yet implemented.[/yellow]")

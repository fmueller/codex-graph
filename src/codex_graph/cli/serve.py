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
    if ctx.invoked_subcommand is not None:
        return

    import threading

    import uvicorn

    from codex_graph.api.app import create_app
    from codex_graph.dashboard.app import create_dashboard
    from codex_graph.db.engine import get_engine
    from codex_graph.db.postgres import PostgresGraphDatabase
    from codex_graph.mcp.server import create_mcp_server

    engine = get_engine()
    db = PostgresGraphDatabase(engine)

    api_app = create_app()
    dash_app = create_dashboard(db)
    mcp_server = create_mcp_server(db)

    dashboard_port = port + 1
    mcp_port = port + 2

    threads = [
        threading.Thread(
            target=uvicorn.run,
            kwargs={"app": api_app, "host": host, "port": port},
            daemon=True,
        ),
        threading.Thread(
            target=dash_app.run,
            kwargs={"host": host, "port": dashboard_port},
            daemon=True,
        ),
        threading.Thread(
            target=mcp_server.run,
            kwargs={"transport": "sse", "host": host, "port": mcp_port},
            daemon=True,
        ),
    ]

    console.print(f"[green]Starting all servers on {host}[/green]")
    console.print(f"  API:       http://{host}:{port}")
    console.print(f"  Dashboard: http://{host}:{dashboard_port}")
    console.print(f"  MCP (SSE): http://{host}:{mcp_port}")

    for t in threads:
        t.start()
    for t in threads:
        t.join()

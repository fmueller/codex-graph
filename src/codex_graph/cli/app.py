import typer

from codex_graph.cli.db import db_app
from codex_graph.cli.ingest import ingest
from codex_graph.cli.query import query_app
from codex_graph.cli.serve import serve_app

app = typer.Typer(
    name="codex-graph",
    help="Codex Graph CLI — ingest and query code ASTs.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(db_app, name="db")
app.command("ingest")(ingest)
app.add_typer(query_app, name="query")
app.add_typer(serve_app, name="serve")


def main() -> None:
    app()

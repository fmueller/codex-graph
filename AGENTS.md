# Repository Guidelines

## Project Overview

Codex Graph parses source files into AST representations and stores them in a PostgreSQL database with Apache AGE graph extension for graph-based querying.

## Architecture: Hexagonal

**Key rule: `core/` never imports from any adapter package.**

- **`core/`** = domain logic + ports. No infrastructure dependencies.
- **`core/ports/`** = protocols defined by the domain. Adapters implement these.
- **`db/`, `watcher/`** = driven adapters (infrastructure).
- **`cli/`, `api/`, `mcp/`, `dashboard/`** = driving adapters (user-facing interfaces).

```
cli/ api/ mcp/ dashboard/     <- driving adapters (import core + driven adapters)
         |
    core/ + core/ports/       <- domain + ports (imports nothing outside core/)
         |
    db/  watcher/             <- driven adapters (implement ports)
```

## Project Structure

```
codex-graph/
    src/codex_graph/           # Python package
        models.py              # Domain models: Position, AstNode, FileAst
        core/                  # Domain layer
            ports/             # GraphDatabase, FileWatcherPort protocols
            languages.py       # Language detection and normalization
            ast.py             # AST extraction from source
            ingest.py          # Ingest orchestration
            query.py           # Query builders
        db/                    # Driven adapter: database
            engine.py          # Engine creation
            helpers.py         # Cypher escaping, span keys, shape hashes
            git.py             # Git commit info extraction
            cypher.py          # Cypher execution, DAG helpers
            postgres.py        # PostgresGraphDatabase (implements GraphDatabase)
            memory.py          # InMemoryGraphDatabase (implements GraphDatabase)
            migrations.py      # Alembic migration runner
        cli/                   # Driving adapter: Typer + Rich CLI
        api/                   # Driving adapter: FastAPI REST API
        mcp/                   # Driving adapter: FastMCP server
        dashboard/             # Driving adapter: Dash web dashboard
        watcher/               # Driven adapter: file watching
        queries/               # Tree-sitter .scm files
    tests/
        unit/                  # Fast tests, no external deps
        integration/           # Real DB via Testcontainers
    alembic/                   # Database migrations
    docker/                    # Dockerfile.database, init-extensions.sql
```

## CLI Commands

```
codex-graph db start [--port PORT]         # Pull image & start DB container
codex-graph db stop                        # Stop & remove DB container
codex-graph db status                      # Show DB container state
codex-graph ingest <path> [--code SOURCE] [--language LANG]
codex-graph query files [--limit N]
codex-graph query node-types [--file PATH] [--limit N]
codex-graph query nodes --type TYPE [--file PATH] [--limit N]
codex-graph query children --span-key KEY [--limit N]
codex-graph query cypher QUERY [--columns N]
codex-graph serve api [--host HOST] [--port PORT]
codex-graph serve mcp [--transport stdio|sse]
codex-graph serve dashboard [--host HOST] [--port PORT]
codex-graph serve [--host HOST] [--port PORT]  # starts all
```

## Setup, Build, Test, and Development Commands

- Install deps: `poetry install` (Python 3.12+).
- Lint/format: `poetry run ruff check` and `poetry run ruff format`.
- Static types: `poetry run mypy`.
- Tests: `poetry run pytest` (all), `poetry run pytest tests/unit` (unit only), `poetry run pytest tests/integration` (integration, needs Docker).
- Run CLI: `poetry run codex-graph ingest <path>`.
- Start local DB: `codex-graph db start` (requires Docker) or `docker compose up -d`.
- Environment: `DATABASE_URL` (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`).

## Coding Style & Naming Conventions

- Python, 4-space indentation, line length 120 (see `pyproject.toml`).
- Ruff enforces lint rules (`E,F,UP,B,SIM,I`) and formats code with double quotes.
- Mypy runs in strict mode; add precise type hints and avoid `Any`.
- Conventional commits (`feat:`, `refactor:`, `build:`).
- Name tests descriptively, e.g., `test_ingest_creates_occurs_edges`.

## Testing Guidelines

- Use `pytest` with files named `*_test.py`.
- Unit tests in `tests/unit/`, integration tests in `tests/integration/`.
- Cover the ingest path: file persistence, AST hashing, and AGE edge creation.
- Prefer deterministic fixtures (small sample files) over large fixtures.

## Mandatory Quality Checks

**IMPORTANT:** After any code change, you MUST run the following commands before considering a task complete:

```bash
poetry run ruff format   # Format code
poetry run ruff check    # Lint code
poetry run mypy          # Type check
poetry run pytest        # Run tests
```

All commands must pass without errors. Fix any issues before completing the task.

## Commit & Pull Request Guidelines

- Commit messages follow conventional commits (`feat:`, `refactor:`, `build:`).
- Keep scope small and logically grouped.
- PRs should describe intent, list key changes, and mention DB or schema impacts.

## Security & Configuration Tips

- Do not commit credentials; rely on `DATABASE_URL` env vars or Docker secrets.
- Avoid dumping full source blobs or connection strings in logs.

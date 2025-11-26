# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `src/codex_graph`: `main.py` runs the ingest demo/entry point, `db.py` handles PostgreSQL + AGE graph writes, `models.py` holds Pydantic schemas, and `queries/` stores Tree-sitter query definitions.
- Database helpers and ALEMBIC scaffolding are in `alembic/`; SQL bootstrapping lives in `init-extensions.sql` and `queries.sql`.
- Tests belong in `tests/` (add `test_*.py` modules alongside fixtures as needed).
- `Dockerfile.database` builds a local PostgreSQL + AGE image used by the graph ingest.

## Setup, Build, Test, and Development Commands
- Install deps: `poetry install` (Python 3.12).
- Lint/format: `poetry run ruff check` and `poetry run ruff format` (use `--check` in CI).
- Static types: `poetry run mypy`.
- Tests: `poetry run pytest`.
- Run the ingest example: `poetry run codex-graph-server` (expects `DATABASE_URL`, defaults to `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`).
- Start local DB (example): `docker build -t codex-graph-db -f Dockerfile.database . && docker run -p 5432:5432 codex-graph-db`.

## Coding Style & Naming Conventions
- Python, 4-space indentation, line length 120 (see `pyproject.toml`).
- Ruff enforces lint rules (`E,F,UP,B,SIM,I`) and formats code with double quotes; prefer `ruff format` over manual edits.
- Mypy runs in strict mode; add precise type hints and avoid `Any`.
- Follow repository naming seen in history (`feat:`, `refactor:`, `build:`); name tests/functions descriptively, e.g., `test_ingest_creates_occurs_edges`.

## Testing Guidelines
- Use `pytest` with files named `test_*.py`; colocate fixtures near usage.
- Cover the ingest path: file persistence, AST hashing, and AGE edge creation. Prefer deterministic fixtures (small sample `.py` files) over large fixtures.
- Add regression tests for bugs before fixes and ensure graph queries assert both node properties and relationships.

## Commit & Pull Request Guidelines
- Commit messages follow conventional commits (`feat:`, `refactor:`, `build:`). Keep scope small and logically grouped.
- PRs should describe intent, list key changes, and mention DB or schema impacts. Link issues/tickets; include screenshots or sample CLI output when behavior changes.
- Note required env vars (`DATABASE_URL`) and migrations/DDL changes in the PR body; coordinate when updates affect shared databases.

## Security & Configuration Tips
- Do not commit credentials; rely on `DATABASE_URL` env vars or Docker secrets.
- Load AGE with the provided init scripts; avoid running arbitrary Cypher against production graphs without review.
- When logging, avoid dumping full source blobs or connection strings; hash or redact where possible.

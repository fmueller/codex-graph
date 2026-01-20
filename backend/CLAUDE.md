# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Codex Graph is an MCP server that parses Python source files into AST (Abstract Syntax Tree) representations and stores them in a PostgreSQL database with Apache AGE graph extension for graph-based querying.

## Development Commands

```bash
# Install dependencies (Python 3.12)
poetry install

# Lint and format
poetry run ruff check
poetry run ruff format

# Type checking (strict mode)
poetry run mypy

# Run tests
poetry run pytest

# Run single test
poetry run pytest tests/test_example.py::test_function_name -v

# Run the ingest server
poetry run codex-graph-server

# Start local database
docker build -t codex-graph-db -f Dockerfile.database .
docker run -p 5432:5432 codex-graph-db
```

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres`)

## Architecture

### Core Modules (`src/codex_graph/`)

- **main.py**: Entry point that orchestrates file parsing and AST ingestion. Uses Tree-sitter to parse Python files and stores results in the graph database.

- **db.py**: Database layer handling both relational PostgreSQL operations and Apache AGE graph operations. Key responsibilities:
  - Graph creation and management via AGE Cypher queries
  - File persistence with content-hash-based deduplication
  - AST node ingestion with span-key and shape-hash identity
  - Edge creation for parent-child AST relationships and file occurrence tracking

- **models.py**: Pydantic models for AST representation (`AstNode`, `FileAst`, `Position`)

- **queries/**: Tree-sitter query definitions (`.scm` files) for extracting semantic information from Python ASTs

### Database Schema

**Relational Tables:**
- `files`: Source file metadata with content deduplication (id, name, full_path, suffix, content, content_hash)
- `ast_edge_guard`: Ensures ordered, idempotent parent-child edges

**AGE Graph (`codex_graph`):**
- `AstNode` vertices: AST nodes with `span_key` (file+type+position) and `shape_hash` (structural identity)
- `FileVersion` vertices: File snapshots with commit and timestamp info
- `PARENT_OF` edges: Ordered child relationships with `child_index`
- `OCCURS_IN` edges: Links AST nodes to their file occurrences

### Key Design Patterns

- **Deduplication**: Files are deduplicated by content hash + path. AST nodes use span-key for exact position matching and shape-hash for structural equivalence across files.
- **Ordered Children**: Parent-child edges maintain `child_index` for preserving AST structure order.
- **Cypher via Dollar-Quoting**: AGE Cypher queries use unique dollar-quote tags to avoid SQL/Cypher escaping conflicts.

## Code Style

- Line length: 120 characters
- Ruff lint rules: E, F, UP, B, SIM, I
- Double quotes for strings
- Mypy strict mode with full type hints
- Commit messages: conventional commits (`feat:`, `refactor:`, `build:`)

## Mandatory Quality Checks

**IMPORTANT:** After any code change, you MUST run the following commands before considering a task complete:

```bash
# 1. Format code
poetry run ruff format

# 2. Lint code
poetry run ruff check

# 3. Type check
poetry run mypy

# 4. Run tests
poetry run pytest
```

All commands must pass without errors. Fix any issues before completing the task.

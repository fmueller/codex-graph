"""Initial schema: files table, ast_edge_guard table, AGE graph.

Revision ID: 001
Revises:
Create Date: 2025-02-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS age")
    op.execute("LOAD 'age'")
    op.execute('SET search_path = ag_catalog, "$user", public')
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'codex_graph') THEN
                PERFORM create_graph('codex_graph');
            END IF;
        END $$
        """
    )
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("full_path", sa.Text, nullable=False),
        sa.Column("suffix", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.Text, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_modified", sa.DateTime(timezone=True), nullable=False),
        schema="public",
    )
    op.create_table(
        "ast_edge_guard",
        sa.Column("parent_id", sa.BigInteger, nullable=False),
        sa.Column("child_id", sa.BigInteger, nullable=False),
        sa.Column("child_index", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("parent_id", "child_id"),
        sa.UniqueConstraint("parent_id", "child_index"),
        schema="public",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("ast_edge_guard", schema="public")
    op.drop_table("files", schema="public")
    op.execute('SET search_path = ag_catalog, "$user", public')
    op.execute("SELECT drop_graph('codex_graph', true)")

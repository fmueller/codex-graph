"""Migration stairway test — verify up/down/up/down cycle works."""

from alembic.config import Config

from alembic import command


def test_migration_stairway(alembic_config: Config) -> None:
    """Ensure migrations can be applied and rolled back repeatedly."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

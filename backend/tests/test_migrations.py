"""Vérifie que les migrations Alembic restent synchronisées avec les modèles."""

from alembic import command
from sqlalchemy import Engine

from tests.helpers import alembic_config


def test_models_and_migrations_are_in_sync(migrated_db: Engine) -> None:
    """Échoue si un modèle a changé sans migration correspondante."""
    config = alembic_config()
    with migrated_db.connect() as connection:
        config.attributes["connection"] = connection
        command.check(config)  # lève une exception en cas d'écart

"""Environnement Alembic : l'URL de la base vient de Settings, jamais d'alembic.ini."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from app.core.config import get_settings
from app.core.database import Base, build_database_url, create_db_engine

# L'import des modèles les enregistre dans Base.metadata (nécessaire à l'autogenerate).
from app.modules.authentication import models as _authentication_models  # noqa: F401
from app.modules.candidates import models as _candidates_models  # noqa: F401
from app.modules.documents import models as _documents_models  # noqa: F401
from app.modules.embeddings import models as _embeddings_models  # noqa: F401
from app.modules.jobs import models as _jobs_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Génère le SQL sans se connecter (alembic upgrade head --sql)."""
    url = build_database_url(get_settings()).render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Les tests fournissent leur propre connexion (config.attributes["connection"]) pour
    # migrer la base de test ; sinon on se connecte avec la configuration de l'application.
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_migrations(connection)
        return

    engine = create_db_engine(get_settings())
    try:
        with engine.connect() as connection:
            _run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

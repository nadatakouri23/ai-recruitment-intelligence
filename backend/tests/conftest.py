"""Fixtures partagées par tous les tests.

Deux familles :
- `settings` / `client` : sans base de données (le moteur ne se connecte pas à la création).
- `db_settings` / `db_client` : avec une base PostgreSQL de test dédiée, migrée par Alembic.
  Les identifiants de connexion viennent de l'environnement (.env en local, variables sur la CI).
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.config import Settings
from app.core.database import create_db_engine
from app.main import create_app
from tests.helpers import alembic_config

TEST_JWT_SECRET = "test-secret-not-for-production-use-only"

# Les tests ne doivent JAMAIS utiliser les vraies clés du .env (appels payants, données envoyées
# à un tiers). Les variables d'environnement l'emportent sur .env : on les neutralise ici.
os.environ["LLM_PROVIDER"] = "none"
for _key in ("GEMINI_API_KEY", "MISTRAL_API_KEY", "GROQ_API_KEY", "LLM_MODEL"):
    os.environ[_key] = ""


@pytest.fixture
def settings() -> Settings:
    """Configuration de test sans base : indépendante du vrai fichier .env."""
    return Settings(
        environment="test",
        postgres_password="test-password",
        jwt_secret_key=TEST_JWT_SECRET,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Client HTTP en mémoire (aucun serveur, aucun port réseau, aucune base)."""
    return TestClient(create_app(settings))


def _ensure_database(settings: Settings) -> None:
    """Crée la base de test si elle n'existe pas (jamais la base de développement)."""
    admin_engine = create_db_engine(settings.model_copy(update={"postgres_db": "postgres"}))
    try:
        with admin_engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": settings.postgres_db},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{settings.postgres_db}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def db_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Configuration pointant vers une base `<nom>_test` et un dossier d'upload temporaire.

    Jamais la base de développement, jamais le vrai dossier `data/uploads`.
    """
    base = Settings(environment="test", jwt_secret_key=TEST_JWT_SECRET)
    return base.model_copy(
        update={
            "postgres_db": f"{base.postgres_db}_test",
            "upload_dir": tmp_path_factory.mktemp("uploads"),
        }
    )


@pytest.fixture(scope="session")
def migrated_db(db_settings: Settings) -> Iterator[Engine]:
    """Base de test à jour : les migrations Alembic sont rejouées (elles sont donc testées)."""
    assert db_settings.postgres_db.endswith("_test"), "Refus de migrer une base hors test."
    _ensure_database(db_settings)
    engine = create_db_engine(db_settings)
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def hashing_client(db_client: TestClient, db_settings: Settings) -> Iterator[TestClient]:
    """Second client sur la MÊME base (déjà vidée par `db_client`), avec embeddings « hashing ».

    Permet de tester le passage de « embeddings désactivés » à « activés » sur les mêmes données.
    """
    settings = db_settings.model_copy(update={"embedding_provider": "hashing"})
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def db_client(db_settings: Settings, migrated_db: Engine) -> Iterator[TestClient]:
    """Client branché sur la base de test, vidée avant chaque test."""
    with migrated_db.begin() as connection:
        # CASCADE vide aussi documents et candidates (clés étrangères vers users).
        connection.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
    for leftover in db_settings.upload_dir.glob("*"):
        leftover.unlink()
    with TestClient(create_app(db_settings)) as test_client:
        yield test_client

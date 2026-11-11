"""Fixtures partagées par tous les tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Configuration de test, indépendante du vrai fichier .env.

    On fournit explicitement le champ obligatoire : les tests marchent donc
    aussi sur la CI, où aucun .env n'existe.
    """
    return Settings(environment="test", postgres_password="test-password")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Client HTTP en mémoire (aucun serveur, aucun port réseau)."""
    return TestClient(create_app(settings))

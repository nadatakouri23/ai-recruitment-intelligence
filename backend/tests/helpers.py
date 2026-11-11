"""Fonctions d'aide partagées par les tests (les fixtures restent dans conftest.py)."""

from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient

from app.modules.authentication.models import Role
from app.modules.authentication.repository import UserRepository
from app.modules.authentication.service import AuthService

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def create_user_directly(
    client: TestClient, email: str, password: str, role: Role = Role.RECRUITER
) -> None:
    """Crée un utilisateur sans passer par l'API (l'API ne permet pas de créer un admin)."""
    state = client.app.state  # type: ignore[attr-defined]
    with state.session_factory() as session:
        AuthService(UserRepository(session), state.settings).register(
            email, password, "Utilisateur Test", role=role
        )


def login(client: TestClient, email: str, password: str) -> str:
    """Retourne un jeton d'accès (échoue le test si la connexion est refusée)."""
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

"""Tests d'intégration de l'authentification (API + PostgreSQL de test)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.core.security import create_access_token
from app.modules.authentication.models import Role
from tests.helpers import auth_header, create_user_directly, login

PASSWORD = "un-mot-de-passe-solide-123"
VALID_PAYLOAD = {"email": "alice@example.com", "password": PASSWORD, "full_name": "Alice Martin"}


# ------------------------------------------------------------------ inscription


def test_register_creates_recruiter_without_leaking_secrets(db_client: TestClient) -> None:
    response = db_client.post("/auth/register", json=VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "recruiter"
    assert body["is_active"] is True
    assert "password" not in body
    assert "hashed_password" not in body
    assert PASSWORD not in response.text


def test_register_cannot_choose_admin_role(db_client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "role": "admin", "is_active": False}

    response = db_client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["role"] == "recruiter"  # le champ `role` envoyé est ignoré
    assert response.json()["is_active"] is True


def test_register_stores_a_hash_not_the_password(db_client: TestClient, migrated_db) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)

    with migrated_db.connect() as conn:
        stored = conn.execute(text("SELECT hashed_password FROM users")).scalar_one()
    assert stored != PASSWORD
    assert stored.startswith("$argon2")


def test_register_duplicate_email_is_rejected_case_insensitively(db_client: TestClient) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)

    response = db_client.post(
        "/auth/register", json={**VALID_PAYLOAD, "email": "ALICE@Example.com"}
    )

    assert response.status_code == 409


def test_register_rejects_short_password(db_client: TestClient) -> None:
    response = db_client.post("/auth/register", json={**VALID_PAYLOAD, "password": "court"})

    assert response.status_code == 422


def test_register_rejects_invalid_email(db_client: TestClient) -> None:
    response = db_client.post("/auth/register", json={**VALID_PAYLOAD, "email": "pas-un-email"})

    assert response.status_code == 422


def test_register_rejects_blank_name(db_client: TestClient) -> None:
    response = db_client.post("/auth/register", json={**VALID_PAYLOAD, "full_name": "   "})

    assert response.status_code == 422


# ------------------------------------------------------------------ connexion


def test_login_returns_bearer_token(db_client: TestClient) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)

    response = db_client.post(
        "/auth/login", data={"username": "alice@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_accepts_email_with_different_case(db_client: TestClient) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)

    assert login(db_client, "  Alice@EXAMPLE.com ", PASSWORD)


def test_login_failures_are_indistinguishable(db_client: TestClient) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)

    wrong_password = db_client.post(
        "/auth/login", data={"username": "alice@example.com", "password": "mauvais-mot-de-passe"}
    )
    unknown_email = db_client.post(
        "/auth/login", data={"username": "inconnu@example.com", "password": PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()  # aucune fuite sur l'existence du compte


def test_inactive_user_cannot_login_or_use_existing_token(
    db_client: TestClient, migrated_db
) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)
    token = login(db_client, "alice@example.com", PASSWORD)
    with migrated_db.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = false"))

    relogin = db_client.post(
        "/auth/login", data={"username": "alice@example.com", "password": PASSWORD}
    )
    with_old_token = db_client.get("/users/me", headers=auth_header(token))

    assert relogin.status_code == 401
    assert with_old_token.status_code == 401


# ------------------------------------------------------------------ routes protégées


def test_me_requires_authentication(db_client: TestClient) -> None:
    response = db_client.get("/users/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_returns_current_user(db_client: TestClient) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)
    token = login(db_client, "alice@example.com", PASSWORD)

    response = db_client.get("/users/me", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_rejects_garbage_token(db_client: TestClient) -> None:
    response = db_client.get("/users/me", headers=auth_header("n-importe-quoi"))

    assert response.status_code == 401


def test_me_rejects_expired_token(db_client: TestClient, db_settings: Settings) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)
    expired = create_access_token("1", db_settings, now=datetime.now(UTC) - timedelta(hours=5))

    response = db_client.get("/users/me", headers=auth_header(expired))

    assert response.status_code == 401


def test_me_rejects_token_of_deleted_user(db_client: TestClient, db_settings: Settings) -> None:
    ghost = create_access_token("9999", db_settings)

    response = db_client.get("/users/me", headers=auth_header(ghost))

    assert response.status_code == 401


# ------------------------------------------------------------------ contrôle des rôles


def test_recruiter_cannot_list_users(db_client: TestClient) -> None:
    db_client.post("/auth/register", json=VALID_PAYLOAD)
    token = login(db_client, "alice@example.com", PASSWORD)

    response = db_client.get("/users", headers=auth_header(token))

    assert response.status_code == 403


def test_list_users_requires_authentication(db_client: TestClient) -> None:
    assert db_client.get("/users").status_code == 401


def test_admin_can_list_users_without_secrets(db_client: TestClient) -> None:
    create_user_directly(db_client, "admin@example.com", PASSWORD, role=Role.ADMIN)
    db_client.post("/auth/register", json=VALID_PAYLOAD)
    token = login(db_client, "admin@example.com", PASSWORD)

    response = db_client.get("/users", headers=auth_header(token))

    assert response.status_code == 200
    users = response.json()
    assert [u["email"] for u in users] == ["admin@example.com", "alice@example.com"]
    assert "hashed_password" not in response.text


def test_list_users_validates_pagination(db_client: TestClient) -> None:
    create_user_directly(db_client, "admin@example.com", PASSWORD, role=Role.ADMIN)
    token = login(db_client, "admin@example.com", PASSWORD)

    response = db_client.get("/users?limit=100000", headers=auth_header(token))

    assert response.status_code == 422

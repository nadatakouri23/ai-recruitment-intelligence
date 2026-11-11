"""Tests unitaires de core/security.py (aucune base de données)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_the_password_and_is_salted() -> None:
    first = hash_password("un-mot-de-passe-solide")
    second = hash_password("un-mot-de-passe-solide")

    assert first != "un-mot-de-passe-solide"
    assert first.startswith("$argon2")
    assert first != second  # sel aléatoire : deux hachages du même mot de passe diffèrent


def test_verify_password_accepts_correct_and_rejects_wrong() -> None:
    hashed = hash_password("un-mot-de-passe-solide")

    assert verify_password("un-mot-de-passe-solide", hashed) is True
    assert verify_password("un-autre-mot-de-passe", hashed) is False


def test_verify_password_returns_false_on_garbage_hash() -> None:
    assert verify_password("x", "ceci-n-est-pas-un-hash") is False


def test_token_roundtrip(settings: Settings) -> None:
    token = create_access_token("42", settings)

    assert decode_access_token(token, settings) == "42"


def test_expired_token_is_rejected(settings: Settings) -> None:
    long_ago = datetime.now(UTC) - timedelta(hours=3)
    token = create_access_token("42", settings, now=long_ago)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_signed_with_another_secret_is_rejected(settings: Settings) -> None:
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "un-autre-secret-complètement-différent-1234567890",
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged, settings)


def test_unsigned_token_with_alg_none_is_rejected(settings: Settings) -> None:
    unsigned = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)}, key="", algorithm="none"
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned, settings)


def test_token_without_subject_is_rejected(settings: Settings) -> None:
    token = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_malformed_token_is_rejected(settings: Settings) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("pas.un.jwt", settings)

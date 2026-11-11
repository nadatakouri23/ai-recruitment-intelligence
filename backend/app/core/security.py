"""Hachage des mots de passe (Argon2) et jetons JWT.

Aucune dépendance à la base ni à FastAPI : ce module est testable seul.
"""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

# Paramètres par défaut d'argon2-cffi (RFC 9106, profil « low memory »).
_hasher = PasswordHasher()


class InvalidTokenError(Exception):
    """Jeton absent, mal formé, falsifié ou expiré."""


def hash_password(password: str) -> str:
    """Retourne l'empreinte Argon2 (sel aléatoire inclus dans la chaîne)."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe. Retourne False (jamais d'exception) en cas d'échec."""
    try:
        return _hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(subject: str, settings: Settings, now: datetime | None = None) -> str:
    """Crée un JWT signé. `subject` est l'identifiant de l'utilisateur."""
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str, settings: Settings) -> str:
    """Valide le jeton et retourne son `sub`.

    On impose la liste d'algorithmes acceptés (jamais celle fournie par le jeton) et la
    présence de `exp` et `sub`. Toute anomalie lève `InvalidTokenError`.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Jeton invalide ou expiré.") from exc
    subject = payload["sub"]
    if not isinstance(subject, str):
        raise InvalidTokenError("Jeton invalide.")
    return subject

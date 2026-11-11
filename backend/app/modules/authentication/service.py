"""Règles métier de l'authentification."""

import structlog
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.modules.authentication.models import Role, User
from app.modules.authentication.repository import UserRepository

log = structlog.get_logger()

# Empreinte calculée une fois : utilisée quand l'email est inconnu pour que la durée de
# réponse soit comparable à celle d'un vrai mot de passe erroné (anti-énumération par le temps).
_DUMMY_HASH = hash_password("mot-de-passe-factice-pour-egaliser-le-temps")


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    """Email inconnu, mauvais mot de passe ou compte désactivé (volontairement indistinct)."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(self, repository: UserRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def register(
        self, email: str, password: str, full_name: str, role: Role = Role.RECRUITER
    ) -> User:
        """Crée un utilisateur. Le rôle n'est jamais fourni par l'API publique."""
        email = normalize_email(email)
        if self._repository.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
        )
        try:
            self._repository.add(user)
        except IntegrityError as exc:  # course entre deux inscriptions simultanées
            raise EmailAlreadyRegisteredError from exc
        # On journalise l'identifiant, jamais l'email ni le mot de passe.
        log.info("user_registered", user_id=user.id, role=user.role.value)
        return user

    def authenticate(self, email: str, password: str) -> str:
        """Retourne un jeton d'accès, ou lève InvalidCredentialsError."""
        user = self._repository.get_by_email(normalize_email(email))
        if user is None:
            verify_password(password, _DUMMY_HASH)
            log.info("login_failed", reason="invalid_credentials")
            raise InvalidCredentialsError
        if not verify_password(password, user.hashed_password) or not user.is_active:
            log.info("login_failed", reason="invalid_credentials", user_id=user.id)
            raise InvalidCredentialsError
        log.info("login_succeeded", user_id=user.id)
        return create_access_token(str(user.id), self._settings)

    def get_user_from_token(self, token: str) -> User:
        """Retourne l'utilisateur actif désigné par le jeton, ou lève InvalidTokenError."""
        subject = decode_access_token(token, self._settings)
        if not subject.isdecimal():
            raise InvalidTokenError("Jeton invalide.")
        user = self._repository.get_by_id(int(subject))
        if user is None or not user.is_active:
            raise InvalidTokenError("Jeton invalide.")
        return user

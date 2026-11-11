"""Routes HTTP : inscription, connexion, profil, liste des utilisateurs (admin)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_auth_service, get_current_user, get_db, require_admin
from app.modules.authentication.models import User
from app.modules.authentication.repository import UserRepository
from app.modules.authentication.schemas import Token, UserCreate, UserRead
from app.modules.authentication.service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)

auth_router = APIRouter(prefix="/auth", tags=["authentication"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, service: AuthService = Depends(get_auth_service)) -> User:
    """Crée un compte recruteur. Le rôle ne peut pas être choisi par l'appelant."""
    try:
        return service.register(payload.email, payload.password, payload.full_name)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse e-mail est déjà utilisée.",
        ) from None


@auth_router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
) -> Token:
    """Échange email (champ `username`) + mot de passe contre un jeton d'accès."""
    try:
        token = service.authenticate(form.username, form.password)
    except InvalidCredentialsError:
        # Même message pour email inconnu, mauvais mot de passe et compte désactivé.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return Token(access_token=token)


@users_router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@users_router.get("", response_model=list[UserRead])
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> list[User]:
    """Liste des utilisateurs (administrateurs uniquement)."""
    return UserRepository(session).list_all(limit=limit, offset=offset)

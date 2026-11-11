"""Configuration centralisée de l'application.

Toutes les valeurs viennent de l'environnement (variables système ou fichier
.env), jamais du code. Voir .env.example pour la liste des variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py = <racine>/backend/app/core/config.py
# parents[0]=core, [1]=app, [2]=backend, [3]=racine du projet.
# On calcule le chemin depuis ce fichier pour que le .env soit trouvé
# quel que soit le dossier depuis lequel on lance l'application.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Paramètres de l'application, validés au démarrage (fail-fast)."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        # Une variable inconnue dans .env (ou dans l'environnement système)
        # ne doit pas faire planter l'application.
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Talent Intelligence Platform"
    # Literal : toute autre valeur (ex. "prod") est rejetée au démarrage.
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- PostgreSQL (utilisé à partir de l'étape 9) ---
    postgres_host: str = "localhost"
    postgres_port: int = 5433  # 5433 côté hôte pour éviter un conflit avec 5432
    postgres_db: str = "talent_platform"
    postgres_user: str = "talent_user"
    # Pas de valeur par défaut : un secret ne doit jamais avoir de défaut dans le
    # code. S'il manque, l'application refuse de démarrer.
    # SecretStr masque la valeur dans print() et dans les logs.
    postgres_password: SecretStr


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique de Settings.

    lru_cache évite de relire et revalider le .env à chaque appel.
    """
    return Settings()

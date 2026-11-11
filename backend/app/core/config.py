"""Configuration centralisée de l'application.

Toutes les valeurs viennent de l'environnement (variables système ou fichier
.env), jamais du code. Voir .env.example pour la liste des variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.modules.matching.weights import MatchingWeights

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

    # --- Import de documents (CV) ---
    # Dossier de stockage des fichiers uploadés (ignoré par Git : données personnelles).
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    max_upload_size_mb: int = Field(default=5, gt=0, le=50)
    # Limite de pages lues dans un PDF (protège contre les fichiers volontairement énormes).
    max_pdf_pages: int = Field(default=30, gt=0, le=200)

    # --- LLM externe (Phase 7) ---
    # "none" : désactivé (défaut). Les trois fournisseurs sont EXTERNES : le texte (anonymisé et
    # expurgé) quitte la machine, ce qui exige un consentement explicite à chaque appel.
    llm_provider: Literal["none", "gemini", "mistral", "groq"] = "none"
    # Clés : jamais dans le code ni dans Git, uniquement dans .env.
    gemini_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    # Nom du modèle ; à défaut, un modèle par fournisseur (voir llm/providers.py, à vérifier).
    llm_model: str | None = None
    llm_timeout_seconds: int = Field(default=30, ge=5, le=120)
    # Plafond de caractères envoyés au fournisseur (coût et fuite de données limités).
    llm_max_input_chars: int = Field(default=12_000, ge=500, le=60_000)

    # --- Embeddings (recherche sémantique) ---
    # "none" : désactivé (défaut ; le modèle pèse ~470 Mo à télécharger). "sentence_transformers" :
    # modèle local multilingue (aucune donnée ne quitte la machine). "hashing" : doublure
    # déterministe, purement lexicale, pour les tests et la CI : PAS de sémantique.
    embedding_provider: Literal["none", "hashing", "sentence_transformers"] = "none"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # --- Matching ---
    # Poids par défaut des composantes du score (surchargeables dans chaque requête). Via
    # l'environnement : MATCHING_WEIGHTS='{"skills": 0.5, "experience": 0.2, ...}'
    matching_weights: MatchingWeights = Field(default_factory=MatchingWeights)

    # --- PostgreSQL (utilisé à partir de l'étape 9) ---
    # 127.0.0.1 et non "localhost" : sous Windows, "localhost" se résout d'abord en
    # IPv6 (::1) alors que Docker n'écoute qu'en IPv4, ce qui ajoute plusieurs
    # secondes (ou un blocage) à chaque connexion.
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433  # 5433 côté hôte pour éviter un conflit avec 5432
    postgres_db: str = "talent_platform"
    postgres_user: str = "talent_user"
    # Pas de valeur par défaut : un secret ne doit jamais avoir de défaut dans le
    # code. S'il manque, l'application refuse de démarrer.
    # SecretStr masque la valeur dans print() et dans les logs.
    postgres_password: SecretStr

    # --- Authentification (JWT) ---
    # Secret de signature des jetons : obligatoire, sans défaut, jamais dans Git.
    # Quiconque le connaît peut forger des jetons valides.
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    # Durée de vie courte : un JWT ne peut pas être révoqué avant son expiration.
    access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique de Settings.

    lru_cache évite de relire et revalider le .env à chaque appel.
    """
    return Settings()

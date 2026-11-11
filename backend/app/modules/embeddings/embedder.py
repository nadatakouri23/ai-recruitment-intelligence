"""Générateurs d'embeddings : un modèle local réel, et une doublure déterministe pour les tests.

Un embedding transforme un texte en vecteur de 384 nombres : deux textes de sens proche (même dans
deux langues) donnent des vecteurs proches. Tout est local : aucun texte de CV ne quitte la machine.
"""

import hashlib
import math
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

import structlog

from app.core.config import Settings
from app.modules.matching.text import analyzer, neutralize_gender_text

log = structlog.get_logger()

# Imposée par le schéma de la base (colonne vector(384)) et par le modèle multilingue retenu.
EMBEDDING_DIM = 384


class EmbeddingUnavailableError(Exception):
    """Le modèle d'embeddings ne peut pas être chargé (non installé, non téléchargé, mémoire…)."""


class Embedder(Protocol):
    name: (
        str  # stocké avec chaque vecteur : on ne compare jamais des vecteurs de modèles différents
    )
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Un vecteur normalisé (norme 1) par texte, dans l'ordre."""
        ...


class HashingEmbedder:
    """Doublure déterministe : projette les mots et bigrammes sur 384 dimensions par hachage.

    NE comprend PAS le sens (« ingénieur » et « engineer » restent distincts) : c'est un sac de
    mots. Sert aux tests et à la CI, sans téléchargement. Ne jamais la présenter comme sémantique.
    """

    name = "hashing-384"
    dimension = EMBEDDING_DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for feature in analyzer(text):
            digest = hashlib.md5(feature.encode("utf-8"), usedforsecurity=False).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector


class SentenceTransformerEmbedder:
    """Modèle multilingue `sentence-transformers`, exécuté localement sur CPU."""

    dimension = EMBEDDING_DIM

    def __init__(self, model_name: str) -> None:
        self.name = model_name
        try:
            from sentence_transformers import (
                SentenceTransformer,  # import tardif : PyTorch est lourd
            )
        except ImportError as exc:
            raise EmbeddingUnavailableError(
                "sentence-transformers n'est pas installé (pip install sentence-transformers)."
            ) from exc
        try:
            self._model = SentenceTransformer(model_name, device="cpu")
        except Exception as exc:  # noqa: BLE001 - modèle absent, réseau, fichier corrompu…
            log.error(
                "embedding_model_load_failed", model=model_name, error_type=type(exc).__name__
            )
            raise EmbeddingUnavailableError(
                f"Impossible de charger le modèle « {model_name} »."
            ) from exc
        # Méthode renommée dans sentence-transformers 5+ ; on accepte les deux noms.
        get_dimension = (
            getattr(self._model, "get_embedding_dimension", None)
            or self._model.get_sentence_embedding_dimension
        )
        actual = get_dimension()
        if actual != EMBEDDING_DIM:
            raise EmbeddingUnavailableError(
                f"Le modèle produit {actual} dimensions, la base attend {EMBEDDING_DIM}."
            )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            list(texts), batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return [[float(x) for x in row] for row in vectors]


def embed_texts(embedder: Embedder, texts: Sequence[str]) -> list[list[float]]:
    """Point d'entrée UNIQUE pour vectoriser un texte (passage, requête, offre).

    Neutralise d'abord les formes féminines de métiers connues : un modèle d'embeddings est sensible
    à « Ingénieure » contre « Ingénieur », ce que la mesure d'équité de la Phase 6 a montré. Tout
    code qui vectorise doit passer par ici, sinon vecteurs de CV et de requêtes divergent.
    """
    return embedder.embed([neutralize_gender_text(text) for text in texts])


@lru_cache(maxsize=4)
def _cached(provider: str, model: str) -> Embedder:
    if provider == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder(model)  # chargé une seule fois par processus


def build_embedder(settings: Settings) -> Embedder | None:
    """L'embedder configuré, ou None si la fonction est désactivée."""
    if settings.embedding_provider == "none":
        return None
    return _cached(settings.embedding_provider, settings.embedding_model)

"""Tests du VRAI modèle d'embeddings multilingue.

Ils ne téléchargent jamais le modèle (~450 Mo) : ignorés s'il n'est pas déjà en cache local,
ou si sentence-transformers n'est pas installé (c'est le cas en CI). Pour les exécuter : installer
`requirements-ml.txt` puis charger le modèle une fois.
"""

import math

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.modules.embeddings.embedder import EMBEDDING_DIM, build_embedder
from app.modules.embeddings.similarity import cosine
from tests.cv_factory import SYNTHETIC_CVS, render
from tests.helpers import auth_header, login

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _model_is_cached() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(MODEL, "model.safetensors"), str)


pytestmark = pytest.mark.skipif(
    not _model_is_cached(),
    reason="modèle d'embeddings absent du cache local (pas de téléchargement)",
)


@pytest.fixture(scope="module")
def embedder():
    pytest.importorskip("sentence_transformers")
    from app.modules.embeddings.embedder import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(MODEL)


def test_dimension_and_normalization(embedder) -> None:
    (vector,) = embedder.embed(["Ingénieur logiciel"])

    assert len(vector) == EMBEDDING_DIM == embedder.dimension
    assert math.sqrt(sum(x * x for x in vector)) == pytest.approx(1.0, abs=1e-4)
    assert embedder.name == MODEL


def test_embedding_is_deterministic(embedder) -> None:
    a, b = embedder.embed(["Développeur Python", "Développeur Python"])

    assert cosine(a, b) == pytest.approx(1.0, abs=1e-5)


def test_same_meaning_in_french_and_english_is_close_and_unrelated_is_far(embedder) -> None:
    fr, en, other = embedder.embed(
        [
            "Je développe des modèles d'apprentissage automatique en production",
            "I build machine learning models in production",
            "Campagnes publicitaires et référencement naturel",
        ]
    )

    assert cosine(fr, en) > 0.8
    assert cosine(fr, en) > cosine(fr, other) + 0.4


def test_the_model_is_semantic_where_the_lexical_stand_in_is_not(embedder) -> None:
    from app.modules.embeddings.embedder import HashingEmbedder

    a = "Gestion de l'infrastructure cloud et déploiement continu"
    b = "Managing cloud infrastructure and continuous deployment"
    real = cosine(*embedder.embed([a, b]))
    stand_in = cosine(*HashingEmbedder().embed([a, b]))

    assert real > 0.8 and stand_in < 0.4


def test_provider_builds_the_real_model_once() -> None:
    settings = Settings(
        postgres_password="x",
        jwt_secret_key="y",
        embedding_provider="sentence_transformers",
        embedding_model=MODEL,
    )

    assert build_embedder(settings) is build_embedder(settings)


def test_cross_language_semantic_search_end_to_end(db_client: TestClient, db_settings) -> None:
    """Une requête en anglais retrouve un CV écrit en français, sans qu'aucun mot ne soit commun."""
    from app.main import create_app

    pytest.importorskip("sentence_transformers")
    settings = db_settings.model_copy(
        update={"embedding_provider": "sentence_transformers", "embedding_model": MODEL}
    )
    with TestClient(create_app(settings)) as client:
        client.post(
            "/auth/register",
            json={
                "email": "ml@example.com",
                "password": "un-mot-de-passe-solide-123",
                "full_name": "RH",
            },
        )
        headers = auth_header(login(client, "ml@example.com", "un-mot-de-passe-solide-123"))
        by_slug = {}
        for slug in ("fr_devops", "fr_marketing", "fr_data_scientist"):
            cv = next(c for c in SYNTHETIC_CVS if c.slug == slug)
            response = client.post(
                "/candidates", headers=headers, files={"file": (cv.filename, render(cv))}
            )
            by_slug[slug] = response.json()["id"]

        status = client.get("/search/status", headers=headers).json()
        body = client.post(
            "/search/candidates",
            headers=headers,
            json={
                "query": "engineer who automates infrastructure and deploys containers",
                "mode": "semantic",
            },
        ).json()

    assert status["semantic_enabled"] and status["vectors"] == status["chunks"] > 0
    assert status["model"] == MODEL
    assert body["results"][0]["candidate"]["id"] == by_slug["fr_devops"]
    assert body["results"][0]["best_passage"]["text"]

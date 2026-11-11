"""Recherche de candidats (mots-clés, sémantique, hybride) et indexation, via l'API et PostgreSQL.

Les embeddings sont ici ceux de la doublure « hashing » (sac de mots déterministe) : ils vérifient
la PLOMBERIE (indexation, pgvector, fusion de rangs, isolation, erreurs), pas la qualité sémantique
d'un vrai modèle, qui est évaluée à part (docs/evaluation/semantic.md).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.cv_factory import SYNTHETIC_CVS, render
from tests.helpers import auth_header, login

PASSWORD = "un-mot-de-passe-solide-123"
CV_BY_SLUG = {cv.slug: cv for cv in SYNTHETIC_CVS}


def make_user(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Recruteur Test"},
    )
    return auth_header(login(client, email, PASSWORD))


def upload(client: TestClient, headers: dict[str, str], slug: str) -> int:
    cv = CV_BY_SLUG[slug]
    response = client.post(
        "/candidates", headers=headers, files={"file": (cv.filename, render(cv))}
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def search(client: TestClient, headers: dict[str, str], query: str, **extra):
    return client.post("/search/candidates", headers=headers, json={"query": query, **extra})


@pytest.fixture
def alice(db_client: TestClient) -> dict[str, str]:
    return make_user(db_client, "alice@example.com")


@pytest.fixture
def bob(db_client: TestClient) -> dict[str, str]:
    return make_user(db_client, "bob@example.com")


@pytest.fixture
def six(hashing_client: TestClient, alice) -> dict[str, int]:
    """Les 6 CV, importés avec les embeddings « hashing » actifs."""
    return {cv.slug: upload(hashing_client, alice, cv.slug) for cv in SYNTHETIC_CVS}


# ------------------------------------------------------------------ indexation


def test_importing_a_cv_indexes_its_passages_and_vectors(hashing_client, alice) -> None:
    upload(hashing_client, alice, "fr_devops")

    status = hashing_client.get("/search/status", headers=alice).json()

    assert status["semantic_enabled"] is True and status["provider"] == "hashing"
    assert status["model"] == "hashing-384"
    assert status["candidates"] == 1 and status["chunks"] >= 3
    assert status["vectors"] == status["chunks"]
    assert status["candidates_needing_index"] == 0


def test_without_embeddings_passages_are_still_indexed_for_keyword_search(db_client, alice) -> None:
    upload(db_client, alice, "fr_devops")

    status = db_client.get("/search/status", headers=alice).json()

    assert status["semantic_enabled"] is False
    assert status["chunks"] >= 3 and status["vectors"] == 0
    assert status["candidates_needing_index"] == 0  # rien à faire tant que le modèle est absent


def test_passages_and_vectors_exclude_identity(hashing_client, alice, six, migrated_db) -> None:
    with migrated_db.connect() as connection:
        rows = connection.execute(text("SELECT text FROM candidate_chunks")).scalars().all()
    joined = "\n".join(rows)

    assert rows
    for cv in SYNTHETIC_CVS:
        for secret in (cv.name, cv.email, cv.phone, cv.link):
            assert secret not in joined, (cv.slug, secret)


def test_deleting_a_candidate_removes_its_passages(hashing_client, alice, migrated_db) -> None:
    candidate_id = upload(hashing_client, alice, "fr_marketing")

    hashing_client.delete(f"/candidates/{candidate_id}", headers=alice)

    with migrated_db.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM candidate_chunks")).scalar_one() == 0


def test_an_indexing_failure_never_blocks_the_cv_import(
    hashing_client, alice, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Broken:
        name = "broken"
        dimension = 384

        def embed(self, texts):
            raise RuntimeError("mémoire insuffisante")

    monkeypatch.setattr("app.api.deps.build_embedder", lambda settings: Broken())

    candidate_id = upload(hashing_client, alice, "fr_devops")  # 201 malgré l'échec

    assert hashing_client.get(f"/candidates/{candidate_id}", headers=alice).status_code == 200
    status = hashing_client.get("/search/status", headers=alice).json()
    assert status["chunks"] >= 3 and status["vectors"] == 0  # passages conservés, sans vecteurs


def test_any_other_indexing_crash_never_blocks_the_cv_import_either(
    hashing_client, alice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second filet : une panne ailleurs que dans le modèle (base, bogue de découpage…)."""

    def explode(self, candidate):
        raise RuntimeError("panne inattendue de l'indexation")

    monkeypatch.setattr("app.modules.embeddings.service.IndexingService.index_candidate", explode)

    candidate_id = upload(hashing_client, alice, "fr_devops")  # toujours 201

    assert hashing_client.get(f"/candidates/{candidate_id}", headers=alice).status_code == 200
    status = hashing_client.get("/search/status", headers=alice).json()
    assert status["candidates"] == 1 and status["chunks"] == 0
    assert status["candidates_needing_index"] == 1  # rattrapable par /search/reindex


def test_reindex_catches_up_after_embeddings_are_enabled(db_client, hashing_client, alice) -> None:
    upload(db_client, alice, "fr_devops")  # importé SANS embeddings
    upload(db_client, alice, "en_ml_engineer")
    before = hashing_client.get("/search/status", headers=alice).json()

    report = hashing_client.post("/search/reindex", headers=alice).json()
    after = hashing_client.get("/search/status", headers=alice).json()
    second = hashing_client.post("/search/reindex", headers=alice).json()

    assert before["vectors"] == 0 and before["candidates_needing_index"] == 2
    assert report["candidates_processed"] == 2 and report["with_vectors"] == report["chunks"] > 0
    assert after["vectors"] == after["chunks"] and after["candidates_needing_index"] == 0
    assert second["candidates_processed"] == 0  # idempotent


def test_vectors_of_another_model_are_ignored_until_reindexed(
    hashing_client, alice, migrated_db
) -> None:
    upload(hashing_client, alice, "fr_devops")
    with migrated_db.begin() as connection:
        connection.execute(text("UPDATE candidate_chunks SET embedding_model = 'ancien-modele'"))

    stale = hashing_client.get("/search/status", headers=alice).json()
    semantic = search(hashing_client, alice, "kubernetes terraform", mode="semantic").json()
    hashing_client.post("/search/reindex", headers=alice)
    fresh = search(hashing_client, alice, "kubernetes terraform", mode="semantic").json()

    assert stale["vectors"] == 0 and stale["candidates_needing_index"] == 1
    assert semantic["results"] == [] and semantic["unindexed_candidates"] == 1
    assert len(fresh["results"]) == 1 and fresh["unindexed_candidates"] == 0


# ------------------------------------------------------------------ recherche


def test_keyword_search_finds_the_matching_candidate_with_its_passage(
    hashing_client, alice, six
) -> None:
    response = search(
        hashing_client, alice, "référencement naturel SEO Google Analytics", mode="keyword"
    )

    body = response.json()
    assert response.status_code == 200 and body["mode_used"] == "keyword"
    top = body["results"][0]
    assert top["candidate"]["id"] == six["fr_marketing"]
    assert top["candidate"]["full_name"] == "Léa Fontaine"
    assert 0 < top["score"] <= 1
    assert top["best_passage"]["section"] in ("summary", "experience", "skills")
    assert "SEO" in top["best_passage"]["text"] or "référencement" in top["best_passage"]["text"]
    assert top["keyword_rank"] == 1 and top["semantic_rank"] is None


def test_semantic_search_ranks_by_vector_similarity(hashing_client, alice, six) -> None:
    body = search(
        hashing_client, alice, "Kubernetes Terraform Ansible Jenkins Prometheus", mode="semantic"
    ).json()

    assert body["mode_used"] == "semantic"
    assert body["results"][0]["candidate"]["id"] == six["fr_devops"]
    assert body["results"][0]["semantic_rank"] == 1 and body["results"][0]["keyword_rank"] is None
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True) and all(0 < s <= 1 for s in scores)


def test_hybrid_fuses_ranks_and_reports_both(hashing_client, alice, six) -> None:
    body = search(
        hashing_client, alice, "Kubernetes Terraform Ansible Jenkins Prometheus", mode="hybrid"
    ).json()

    top = body["results"][0]
    assert body["mode_used"] == "hybrid"
    assert top["candidate"]["id"] == six["fr_devops"]
    assert top["keyword_rank"] == 1 and top["semantic_rank"] == 1
    assert top["score"] == pytest.approx(1.0)  # premier dans les deux classements
    assert all(0 < r["score"] <= 1 for r in body["results"])


def test_auto_mode_is_hybrid_with_embeddings_and_keyword_without(
    db_client, hashing_client, alice
) -> None:
    upload(hashing_client, alice, "fr_devops")

    with_embeddings = search(hashing_client, alice, "kubernetes", mode="auto").json()
    without = search(db_client, alice, "kubernetes", mode="auto").json()

    assert with_embeddings["mode_used"] == "hybrid" and without["mode_used"] == "keyword"


def test_semantic_search_is_refused_clearly_when_embeddings_are_disabled(db_client, alice) -> None:
    upload(db_client, alice, "fr_devops")

    for mode in ("semantic", "hybrid"):
        response = search(db_client, alice, "kubernetes", mode=mode)
        assert response.status_code == 503
        assert "désactivée" in response.json()["detail"] and "keyword" in response.json()["detail"]
    assert search(db_client, alice, "kubernetes", mode="keyword").status_code == 200


def test_skill_filter_is_bilingual(hashing_client, alice, six) -> None:
    def ids(**extra) -> set[int]:
        body = search(
            hashing_client, alice, "développement avec des modèles", mode="keyword", **extra
        ).json()
        return {r["candidate"]["id"] for r in body["results"]}

    only_ml = ids(skill="apprentissage automatique")

    assert only_ml and only_ml <= {six["fr_data_scientist"], six["en_ml_engineer"]}
    assert ids(skill="Kubernetes") <= {six["en_backend_engineer"], six["fr_devops"]}
    assert ids(skill="compétence inconnue") == set()


def test_anonymous_mode_hides_identity(hashing_client, alice, six) -> None:
    body = search(
        hashing_client, alice, "Kubernetes Terraform", mode="hybrid", anonymize=True
    ).json()

    assert body["results"]
    for result in body["results"]:
        assert result["candidate"]["full_name"] is None and result["candidate"]["email"] is None
    for cv in SYNTHETIC_CVS:
        assert cv.name not in str(body) and cv.email not in str(body)


def test_limit_is_respected_and_results_are_unique_candidates(hashing_client, alice, six) -> None:
    body = search(hashing_client, alice, "python sql docker", mode="hybrid", limit=3).json()

    ids = [r["candidate"]["id"] for r in body["results"]]
    assert len(ids) <= 3 and len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": " "},
        {"query": "x"},
        {"query": "x" * 501},
        {"query": "python", "mode": "magique"},
        {"query": "python", "limit": 0},
        {"query": "python", "limit": 51},
        {"query": "python", "skill": "x" * 61},
    ],
)
def test_invalid_search_requests_are_rejected(hashing_client, alice, payload: dict) -> None:
    assert hashing_client.post("/search/candidates", headers=alice, json=payload).status_code == 422


def test_search_does_not_log_the_query_or_personal_data(hashing_client, alice, six, capsys) -> None:
    capsys.readouterr()

    search(hashing_client, alice, "Mehdi Karoui administrateur systèmes", mode="hybrid")
    logs = capsys.readouterr().out

    assert "search_done" in logs
    assert "Karoui" not in logs and "Mehdi" not in logs and "administrateur" not in logs


# ------------------------------------------------------------------ isolation et accès


def test_a_recruiter_only_searches_their_own_candidates(hashing_client, alice, bob) -> None:
    upload(hashing_client, alice, "fr_devops")
    bobs = upload(hashing_client, bob, "fr_marketing")

    for mode in ("keyword", "semantic", "hybrid"):
        body = search(
            hashing_client, bob, "kubernetes terraform ansible seo analytics", mode=mode
        ).json()
        assert {r["candidate"]["id"] for r in body["results"]} <= {bobs}, mode


def test_status_and_reindex_are_per_recruiter(db_client, hashing_client, alice, bob) -> None:
    upload(db_client, alice, "fr_devops")

    assert hashing_client.get("/search/status", headers=bob).json()["candidates"] == 0
    assert hashing_client.post("/search/reindex", headers=bob).json()["candidates_processed"] == 0
    assert (
        hashing_client.get("/search/status", headers=alice).json()["candidates_needing_index"] == 1
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/search/candidates"), ("get", "/search/status"), ("post", "/search/reindex")],
)
def test_search_routes_require_authentication(hashing_client, method: str, path: str) -> None:
    assert getattr(hashing_client, method)(path).status_code == 401


# ------------------------------------------------------------------ matching


def test_semantic_weight_defaults_to_zero_and_changes_nothing(hashing_client, alice, six) -> None:
    job = hashing_client.post(
        "/jobs", headers=alice, json={"title": "Ingénieur DevOps", "description": _JOB}
    ).json()

    body = hashing_client.post(f"/jobs/{job['id']}/matches", headers=alice, json={}).json()

    assert body["weights_used"]["semantic"] == 0
    top = body["results"][0]
    semantic = next(c for c in top["components"] if c["name"] == "semantic")
    assert semantic["raw_score"] is not None  # calculée à titre indicatif
    assert semantic["effective_weight"] == 0 and "Poids à 0" in semantic["note"]
    assert top["candidate"]["id"] == six["fr_devops"]


def test_semantic_weight_can_be_activated_per_request(hashing_client, alice, six) -> None:
    job = hashing_client.post(
        "/jobs", headers=alice, json={"title": "Ingénieur DevOps", "description": _JOB}
    ).json()

    body = hashing_client.post(
        f"/jobs/{job['id']}/matches",
        headers=alice,
        json={
            "weights": {
                "skills": 0,
                "experience": 0,
                "tfidf": 0,
                "keyword": 0,
                "education": 0,
                "semantic": 1,
            }
        },
    ).json()

    top = body["results"][0]
    assert body["weights_used"]["semantic"] == 1
    assert top["score"] == pytest.approx(
        100 * next(c for c in top["components"] if c["name"] == "semantic")["raw_score"], abs=0.05
    )
    assert any("Similarité sémantique" in line for line in top["explanations"])


def test_semantic_weight_without_embeddings_gives_a_clear_warning(db_client, alice) -> None:
    upload(db_client, alice, "fr_devops")
    job = db_client.post(
        "/jobs", headers=alice, json={"title": "Ingénieur DevOps", "description": _JOB}
    ).json()

    body = db_client.post(
        f"/jobs/{job['id']}/matches",
        headers=alice,
        json={
            "weights": {
                "skills": 0,
                "experience": 0,
                "tfidf": 0,
                "keyword": 0,
                "education": 0,
                "semantic": 1,
            }
        },
    ).json()

    result = body["results"][0]
    assert result["score"] == 0
    assert any("Aucune composante évaluable" in w for w in result["warnings"])
    semantic = next(c for c in result["components"] if c["name"] == "semantic")
    assert semantic["raw_score"] is None and "désactivés" in semantic["note"]


_JOB = """Orbite Cloud recrute un Ingénieur DevOps.

Vos missions
- Automatiser l'infrastructure avec Terraform et Ansible
- Superviser avec Prometheus et Grafana

Votre profil
- 4 ans d'expérience minimum
- Solide pratique de Kubernetes, Docker et Linux
"""

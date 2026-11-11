"""Tests d'intégration des offres et du matching (API + PostgreSQL de test)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.cv_factory import SYNTHETIC_CVS, render
from tests.helpers import auth_header, login
from tests.job_factory import BACKEND_EN, DATA_SCIENTIST_FR, DEVOPS_FR, SyntheticJob

PASSWORD = "un-mot-de-passe-solide-123"
CV_BY_SLUG = {cv.slug: cv for cv in SYNTHETIC_CVS}


def make_user(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Recruteur Test"},
    )
    return auth_header(login(client, email, PASSWORD))


def upload_cv(client: TestClient, headers: dict[str, str], slug: str) -> int:
    cv = CV_BY_SLUG[slug]
    response = client.post(
        "/candidates", headers=headers, files={"file": (cv.filename, render(cv), "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def create_job(client: TestClient, headers: dict[str, str], job: SyntheticJob, **extra):
    payload = {"title": job.title, "description": job.description, **extra}
    return client.post("/jobs", headers=headers, json=payload)


@pytest.fixture
def alice(db_client: TestClient) -> dict[str, str]:
    return make_user(db_client, "alice@example.com")


@pytest.fixture
def bob(db_client: TestClient) -> dict[str, str]:
    return make_user(db_client, "bob@example.com")


@pytest.fixture
def six_cvs(db_client: TestClient, alice: dict[str, str]) -> dict[str, int]:
    return {cv.slug: upload_cv(db_client, alice, cv.slug) for cv in SYNTHETIC_CVS}


# ------------------------------------------------------------------ offres


def test_create_job_returns_the_structured_profile(db_client: TestClient, alice) -> None:
    response = create_job(db_client, alice, DATA_SCIENTIST_FR)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == DATA_SCIENTIST_FR.title
    profile = body["profile"]
    assert set(profile["required_skills"]) == set(DATA_SCIENTIST_FR.required)
    assert set(profile["optional_skills"]) == set(DATA_SCIENTIST_FR.optional)
    assert profile["min_experience_years"] == 3 and profile["education_level"] == 5
    assert profile["recruiter_overrides"] == []
    assert profile["parser_version"].startswith("job-rules-")


def test_recruiter_corrections_override_the_analysis_and_are_recorded(
    db_client: TestClient, alice
) -> None:
    response = create_job(
        db_client,
        alice,
        BACKEND_EN,
        required_skills=["java", "apprentissage automatique"],  # alias FR/EN acceptés
        optional_skills=["Java", "Docker"],  # Java est déjà requis : « requis » l'emporte
        min_experience_years=8,
    )

    profile = response.json()["profile"]
    assert profile["required_skills"] == ["Java", "Machine Learning"]
    assert profile["optional_skills"] == ["Docker"]
    assert profile["min_experience_years"] == 8
    assert profile["education_level"] == 3  # non corrigé : l'analyse est conservée
    assert profile["recruiter_overrides"] == [
        "min_experience_years", "optional_skills", "required_skills"
    ]  # fmt: skip


def test_unknown_skills_are_rejected_with_an_explicit_message(db_client: TestClient, alice) -> None:
    response = create_job(db_client, alice, BACKEND_EN, required_skills=["Java", "COBOL"])

    assert response.status_code == 422
    assert "COBOL" in response.json()["detail"] and "référentiel" in response.json()["detail"]
    assert db_client.get("/jobs", headers=alice).json()["total"] == 0  # rien n'a été créé


def test_empty_list_explicitly_clears_a_field(db_client: TestClient, alice) -> None:
    response = create_job(db_client, alice, DATA_SCIENTIST_FR, optional_skills=[])

    assert response.json()["profile"]["optional_skills"] == []
    assert response.json()["profile"]["required_skills"]  # le reste est conservé


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "description": "x" * 50},
        {"title": "   ", "description": "x" * 50},
        {"title": "Poste", "description": "trop court"},
        {"title": "Poste", "description": "x" * 20_001},
        {"title": "Poste", "description": "x" * 50, "education_level": 9},
        {"title": "Poste", "description": "x" * 50, "min_experience_years": -1},
    ],
)
def test_invalid_job_payloads_are_rejected(db_client: TestClient, alice, payload: dict) -> None:
    assert db_client.post("/jobs", headers=alice, json=payload).status_code == 422


def test_update_job(db_client: TestClient, alice) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    response = db_client.patch(
        f"/jobs/{job_id}",
        headers=alice,
        json={
            "title": "Lead DevOps",
            "min_experience_years": 6,
            "optional_skills": ["Azure", "AWS"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Lead DevOps"
    assert body["profile"]["min_experience_years"] == 6
    assert body["profile"]["optional_skills"] == ["Azure", "AWS"]
    assert "Kubernetes" in body["profile"]["required_skills"]  # inchangé
    assert db_client.get(f"/jobs/{job_id}", headers=alice).json()["title"] == "Lead DevOps"


def test_job_listing_pagination_and_validation(db_client: TestClient, alice) -> None:
    for job in (DATA_SCIENTIST_FR, BACKEND_EN, DEVOPS_FR):
        create_job(db_client, alice, job)

    page = db_client.get("/jobs?limit=2&offset=1", headers=alice).json()

    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["title"] == BACKEND_EN.title  # plus récents d'abord
    assert db_client.get("/jobs?limit=0", headers=alice).status_code == 422


def test_jobs_are_private_to_their_owner(db_client: TestClient, alice, bob) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]
    unknown = db_client.get("/jobs/999999", headers=bob)

    for method, path, kwargs in (
        ("get", f"/jobs/{job_id}", {}),
        ("patch", f"/jobs/{job_id}", {"json": {"title": "Piraté"}}),
        ("delete", f"/jobs/{job_id}", {}),
        ("post", f"/jobs/{job_id}/matches", {"json": {}}),
    ):
        response = getattr(db_client, method)(path, headers=bob, **kwargs)
        assert response.status_code == 404
        assert response.json() == unknown.json()

    assert db_client.get("/jobs", headers=bob).json()["total"] == 0
    assert db_client.get(f"/jobs/{job_id}", headers=alice).json()["title"] == DEVOPS_FR.title


def test_delete_job(db_client: TestClient, alice) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    assert db_client.delete(f"/jobs/{job_id}", headers=alice).status_code == 204
    assert db_client.get(f"/jobs/{job_id}", headers=alice).status_code == 404
    assert db_client.delete(f"/jobs/{job_id}", headers=alice).status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/jobs"), ("post", "/jobs"), ("get", "/jobs/1"), ("post", "/jobs/1/matches")],
)
def test_job_routes_require_authentication(db_client: TestClient, method: str, path: str) -> None:
    assert getattr(db_client, method)(path).status_code == 401


# ------------------------------------------------------------------ matching


def match(client: TestClient, headers, job_id: int, **body):
    return client.post(f"/jobs/{job_id}/matches", headers=headers, json=body)


def test_matching_ranks_the_relevant_candidates_first(
    db_client: TestClient, alice, six_cvs: dict[str, int]
) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    response = match(db_client, alice, job_id)

    assert response.status_code == 200
    body = response.json()
    assert body["pool_size"] == 6 and body["pool_truncated"] is False and body["returned"] == 6
    assert [r["rank"] for r in body["results"]] == [1, 2, 3, 4, 5, 6]
    top = body["results"][0]
    assert top["candidate"]["id"] == six_cvs["fr_devops"]
    assert top["candidate"]["full_name"] == "Mehdi Karoui"
    assert top["score"] > body["results"][1]["score"] + 15
    assert (
        body["limitations"]
        and "décision finale revient toujours au recruteur" in body["limitations"][0]
    )


def test_match_result_exposes_everything_needed_to_understand_the_score(
    db_client: TestClient, alice, six_cvs: dict[str, int]
) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    top = match(db_client, alice, job_id).json()["results"][0]

    assert {c["name"] for c in top["components"]} == {
        "skills", "experience", "education", "tfidf", "keyword", "semantic"
    }  # fmt: skip
    assert sum(c["contribution"] for c in top["components"]) == pytest.approx(
        top["score"], abs=0.05
    )
    assert top["skills"]["matched_required"] and top["skills"]["evidence"]
    assert (
        top["relevant_experience"] and top["explanations"] and top["confidence"]["level"] == "high"
    )


def test_default_weights_come_from_server_settings_and_are_reported(
    db_client: TestClient, alice, six_cvs
) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    weights = match(db_client, alice, job_id).json()["weights_used"]

    assert sum(weights.values()) == pytest.approx(1, abs=0.001)
    assert weights["skills"] == pytest.approx(0.45)


def test_custom_weights_are_applied_and_normalized(db_client: TestClient, alice, six_cvs) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    body = match(
        db_client, alice, job_id,
        weights={"skills": 3, "experience": 1, "tfidf": 0, "keyword": 0, "education": 0},
    ).json()  # fmt: skip

    assert body["weights_used"]["skills"] == 0.75 and body["weights_used"]["tfidf"] == 0
    tfidf = next(c for c in body["results"][0]["components"] if c["name"] == "tfidf")
    assert tfidf["effective_weight"] == 0 and "Poids à 0" in tfidf["note"]


@pytest.mark.parametrize(
    "body",
    [
        {"weights": {"skills": 0, "experience": 0, "tfidf": 0, "keyword": 0, "education": 0}},
        {"weights": {"skills": -1}},
        {"limit": 0},
        {"limit": 101},
        {"min_score": 101},
        {"min_score": -1},
    ],
)
def test_invalid_matching_requests_are_rejected(db_client: TestClient, alice, body: dict) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    assert match(db_client, alice, job_id, **body).status_code == 422


def test_limit_and_min_score(db_client: TestClient, alice, six_cvs) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    limited = match(db_client, alice, job_id, limit=2).json()
    strict = match(db_client, alice, job_id, min_score=50).json()

    assert limited["returned"] == 2 and limited["pool_size"] == 6
    assert [r["rank"] for r in limited["results"]] == [1, 2]
    assert strict["returned"] >= 1 and all(r["score"] >= 50 for r in strict["results"])
    assert strict["returned"] < 6


def test_anonymized_mode_hides_identity_but_not_the_ranking(
    db_client: TestClient, alice, six_cvs
) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]
    named = match(db_client, alice, job_id).json()
    blind = match(db_client, alice, job_id, anonymize=True).json()

    assert [r["candidate"]["id"] for r in blind["results"]] == [
        r["candidate"]["id"] for r in named["results"]
    ]
    assert [r["score"] for r in blind["results"]] == [r["score"] for r in named["results"]]
    assert all(
        r["candidate"]["full_name"] is None and r["candidate"]["email"] is None
        for r in blind["results"]
    )
    for cv in SYNTHETIC_CVS:  # nulle part dans la réponse
        assert cv.name not in str(blind) and cv.email not in str(blind)


def test_matching_only_considers_the_recruiters_own_candidates(
    db_client: TestClient, alice, bob
) -> None:
    upload_cv(db_client, alice, "fr_devops")
    bobs = upload_cv(db_client, bob, "fr_marketing")
    job_id = create_job(db_client, bob, DEVOPS_FR).json()["id"]

    body = match(db_client, bob, job_id).json()

    assert body["pool_size"] == 1
    assert [r["candidate"]["id"] for r in body["results"]] == [bobs]


def test_matching_with_no_candidates_returns_an_empty_ranking(db_client: TestClient, alice) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    body = match(db_client, alice, job_id).json()

    assert body["pool_size"] == 0 and body["results"] == [] and body["limitations"]


def test_matching_without_a_body_uses_defaults(db_client: TestClient, alice, six_cvs) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]

    response = db_client.post(f"/jobs/{job_id}/matches", headers=alice)

    assert response.status_code == 200 and response.json()["returned"] == 6


def test_corrected_skills_change_the_ranking(db_client: TestClient, alice, six_cvs) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]
    before = match(db_client, alice, job_id).json()["results"][0]["candidate"]["id"]

    db_client.patch(
        f"/jobs/{job_id}",
        headers=alice,
        json={"required_skills": ["SEO", "Google Analytics"], "min_experience_years": 3},
    )
    after = match(db_client, alice, job_id).json()["results"][0]["candidate"]["id"]

    assert before == six_cvs["fr_devops"] and after == six_cvs["fr_marketing"]


def test_deleting_a_candidate_removes_it_from_future_rankings(
    db_client: TestClient, alice, six_cvs
) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]
    top = match(db_client, alice, job_id).json()["results"][0]["candidate"]["id"]

    db_client.delete(f"/candidates/{top}", headers=alice)

    body = match(db_client, alice, job_id).json()
    assert body["pool_size"] == 5 and top not in [r["candidate"]["id"] for r in body["results"]]


def test_matching_does_not_log_personal_data(db_client: TestClient, alice, six_cvs, capsys) -> None:
    job_id = create_job(db_client, alice, DEVOPS_FR).json()["id"]
    capsys.readouterr()  # vide ce qui précède

    match(db_client, alice, job_id)
    logs = capsys.readouterr().out

    assert "matching_done" in logs
    for cv in SYNTHETIC_CVS:
        assert cv.name not in logs and cv.email not in logs


def test_job_table_is_wiped_with_the_user(db_client: TestClient, alice, migrated_db) -> None:
    create_job(db_client, alice, DEVOPS_FR)
    with migrated_db.begin() as connection:
        connection.execute(text("DELETE FROM users"))

    with migrated_db.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM jobs")).scalar_one() == 0

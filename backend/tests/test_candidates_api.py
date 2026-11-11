"""Tests d'intégration de l'API des candidats (PostgreSQL de test + dossier d'upload temporaire)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from tests.cv_factory import SYNTHETIC_CVS, SyntheticCV, blank_pdf, render
from tests.helpers import auth_header, login

PASSWORD = "un-mot-de-passe-solide-123"
CV_BY_SLUG = {cv.slug: cv for cv in SYNTHETIC_CVS}
PDF_CV = CV_BY_SLUG["fr_data_scientist"]
DOCX_CV = CV_BY_SLUG["fr_devops"]


def make_user(client: TestClient, email: str) -> dict[str, str]:
    """Crée un recruteur et retourne ses en-têtes d'authentification."""
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Recruteur Test"},
    )
    return auth_header(login(client, email, PASSWORD))


def upload(
    client: TestClient, headers: dict[str, str], cv: SyntheticCV | None = None, **overrides: object
):
    """Envoie un CV. `overrides` : filename, content, content_type."""
    cv = cv or PDF_CV
    filename = str(overrides.get("filename", cv.filename))
    content = overrides.get("content", render(cv))
    content_type = str(overrides.get("content_type", "application/octet-stream"))
    return client.post(
        "/candidates", headers=headers, files={"file": (filename, content, content_type)}
    )


def stored_files(settings: Settings) -> list[Path]:
    return sorted(p for p in settings.upload_dir.glob("*") if p.is_file())


@pytest.fixture
def alice(db_client: TestClient) -> dict[str, str]:
    return make_user(db_client, "alice@example.com")


@pytest.fixture
def bob(db_client: TestClient) -> dict[str, str]:
    return make_user(db_client, "bob@example.com")


# ------------------------------------------------------------------ import


def test_upload_pdf_returns_structured_profile(
    db_client: TestClient, db_settings: Settings, alice: dict[str, str]
) -> None:
    response = upload(db_client, alice)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == PDF_CV.filename
    assert body["kind"] == "pdf"
    assert body["page_count"] == 1
    profile = body["profile"]
    assert profile["full_name"] == PDF_CV.name
    assert profile["email"] == PDF_CV.email
    assert {s["name"] for s in profile["skills"]} == set(PDF_CV.truth.skills)
    assert profile["report"]["parser_version"].startswith("rules-")
    assert profile["report"]["limitations"]
    assert len(stored_files(db_settings)) == 1


def test_upload_docx(db_client: TestClient, alice: dict[str, str]) -> None:
    response = upload(db_client, alice, DOCX_CV)

    assert response.status_code == 201
    assert response.json()["kind"] == "docx"
    assert response.json()["page_count"] is None


def test_upload_requires_authentication(db_client: TestClient, db_settings: Settings) -> None:
    response = db_client.post("/candidates", files={"file": ("cv.pdf", render(PDF_CV))})

    assert response.status_code == 401
    assert stored_files(db_settings) == []


def test_upload_without_a_file_is_a_validation_error(
    db_client: TestClient, alice: dict[str, str]
) -> None:
    assert db_client.post("/candidates", headers=alice).status_code == 422


def test_response_never_exposes_server_paths_or_storage_names(
    db_client: TestClient, db_settings: Settings, alice: dict[str, str]
) -> None:
    response = upload(db_client, alice)

    stored = stored_files(db_settings)[0]
    assert stored.name not in response.text
    assert str(db_settings.upload_dir) not in response.text
    assert "storage_name" not in response.text
    assert "sha256" not in response.text


def test_stored_name_is_generated_and_ignores_hostile_filename(
    db_client: TestClient, db_settings: Settings, alice: dict[str, str]
) -> None:
    response = upload(db_client, alice, filename="../../../evil.pdf")

    assert response.status_code == 201
    assert response.json()["original_filename"] == "evil.pdf"
    (stored,) = stored_files(db_settings)
    assert stored.parent == db_settings.upload_dir
    assert stored.suffix == ".pdf" and "evil" not in stored.name
    assert not (db_settings.upload_dir.parent / "evil.pdf").exists()


def test_client_declared_content_type_is_not_trusted(
    db_client: TestClient, alice: dict[str, str]
) -> None:
    # Un fichier texte qui se déclare « application/pdf » est refusé sur sa signature réelle.
    response = upload(
        db_client,
        alice,
        filename="cv.pdf",
        content=b"juste du texte",
        content_type="application/pdf",
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("overrides", "status", "fragment"),
    [
        ({"filename": "cv.txt", "content": b"du texte"}, 422, "Format non pris en charge"),
        ({"filename": "cv.docx"}, 422, "ne correspond pas"),  # contenu PDF sous extension .docx
        ({"content": blank_pdf()}, 422, "OCR"),
        ({"filename": "cv.pdf", "content": b""}, 422, "vide"),
    ],
)
def test_invalid_uploads_are_rejected_and_leave_nothing_behind(
    db_client: TestClient,
    db_settings: Settings,
    alice: dict[str, str],
    overrides: dict[str, object],
    status: int,
    fragment: str,
) -> None:
    response = upload(db_client, alice, **overrides)

    assert response.status_code == status
    assert fragment in response.json()["detail"]
    assert stored_files(db_settings) == []
    assert db_client.get("/candidates", headers=alice).json()["total"] == 0


def test_oversized_upload_returns_413(
    db_client: TestClient, db_settings: Settings, alice: dict[str, str]
) -> None:
    too_big = b"%PDF-" + b"0" * (db_settings.max_upload_size_mb * 1024 * 1024)

    response = upload(db_client, alice, filename="gros.pdf", content=too_big)

    assert response.status_code == 413
    assert stored_files(db_settings) == []


def test_importing_the_same_file_twice_is_a_conflict(
    db_client: TestClient, db_settings: Settings, alice: dict[str, str]
) -> None:
    same_bytes = render(PDF_CV)  # un seul rendu : reportlab ajoute un id aléatoire à chaque PDF
    first = upload(db_client, alice, content=same_bytes)
    second = upload(db_client, alice, content=same_bytes)

    assert first.status_code == 201
    assert second.status_code == 409
    assert "déjà été importé" in second.json()["detail"]
    assert len(stored_files(db_settings)) == 1  # pas de fichier orphelin


def test_duplicate_detection_is_byte_exact_known_limitation(
    db_client: TestClient, alice: dict[str, str]
) -> None:
    # Limite connue : le même CV ré-exporté (octets différents) n'est pas reconnu comme doublon.
    assert upload(db_client, alice, content=render(PDF_CV)).status_code == 201
    assert upload(db_client, alice, content=render(PDF_CV)).status_code == 201


def test_two_recruiters_can_import_the_same_file(
    db_client: TestClient, alice: dict[str, str], bob: dict[str, str]
) -> None:
    same_bytes = render(PDF_CV)
    assert upload(db_client, alice, content=same_bytes).status_code == 201
    assert upload(db_client, bob, content=same_bytes).status_code == 201


# ------------------------------------------------------------------ isolation entre recruteurs


def test_a_recruiter_cannot_see_or_touch_another_recruiters_candidate(
    db_client: TestClient, db_settings: Settings, alice: dict[str, str], bob: dict[str, str]
) -> None:
    candidate_id = upload(db_client, alice).json()["id"]
    unknown = db_client.get("/candidates/999999", headers=bob)

    for method, path in (
        ("get", f"/candidates/{candidate_id}"),
        ("get", f"/candidates/{candidate_id}/text"),
        ("delete", f"/candidates/{candidate_id}"),
    ):
        response = getattr(db_client, method)(path, headers=bob)
        # Même réponse que pour un identifiant inexistant : on ne révèle pas l'existence.
        assert response.status_code == 404
        assert response.json() == unknown.json()

    assert db_client.get("/candidates", headers=bob).json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }
    assert db_client.get(f"/candidates/{candidate_id}", headers=alice).status_code == 200
    assert len(stored_files(db_settings)) == 1  # la tentative de suppression n'a rien effacé


def test_even_an_admin_does_not_see_other_recruiters_candidates(
    db_client: TestClient, alice: dict[str, str]
) -> None:
    from app.modules.authentication.models import Role
    from tests.helpers import create_user_directly

    candidate_id = upload(db_client, alice).json()["id"]
    create_user_directly(db_client, "admin@example.com", PASSWORD, role=Role.ADMIN)
    admin = auth_header(login(db_client, "admin@example.com", PASSWORD))

    assert db_client.get(f"/candidates/{candidate_id}", headers=admin).status_code == 404
    assert db_client.get("/candidates", headers=admin).json()["total"] == 0


# ------------------------------------------------------------------ consultation


def test_get_candidate_and_extracted_text(db_client: TestClient, alice: dict[str, str]) -> None:
    candidate_id = upload(db_client, alice).json()["id"]

    detail = db_client.get(f"/candidates/{candidate_id}", headers=alice)
    text = db_client.get(f"/candidates/{candidate_id}/text", headers=alice)

    assert detail.status_code == 200 and detail.json()["profile"]["full_name"] == PDF_CV.name
    assert text.status_code == 200
    assert PDF_CV.email in text.json()["text"]
    assert "(cid:" not in text.json()["text"]


@pytest.mark.parametrize("path", ["/candidates", "/candidates/1", "/candidates/1/text"])
def test_read_routes_require_authentication(db_client: TestClient, path: str) -> None:
    assert db_client.get(path).status_code == 401


def test_candidate_id_must_be_an_integer(db_client: TestClient, alice: dict[str, str]) -> None:
    assert db_client.get("/candidates/abc", headers=alice).status_code == 422


# ------------------------------------------------------------------ liste, filtres, pagination


@pytest.fixture
def three_candidates(db_client: TestClient, alice: dict[str, str]) -> dict[str, str]:
    for slug in ("fr_data_scientist", "en_ml_engineer", "fr_marketing"):
        assert upload(db_client, alice, CV_BY_SLUG[slug]).status_code == 201
    return alice


def test_list_returns_summaries_newest_first(
    db_client: TestClient, three_candidates: dict[str, str]
) -> None:
    body = db_client.get("/candidates", headers=three_candidates).json()

    assert body["total"] == 3
    assert [c["full_name"] for c in body["items"]] == [
        "Léa Fontaine",
        "Olivia Brandt",
        "Sofia Benali",
    ]
    first = body["items"][0]
    assert set(first) == {
        "id", "full_name", "email", "original_filename", "skills",
        "total_experience_months", "extraction_completeness", "created_at",
    }  # fmt: skip
    assert "profile" not in first


def test_filter_by_skill_is_bilingual_and_alias_aware(
    db_client: TestClient, three_candidates: dict[str, str]
) -> None:
    def names(query: str) -> set[str]:
        response = db_client.get(f"/candidates?skill={query}", headers=three_candidates)
        return {c["full_name"] for c in response.json()["items"]}

    ml = {"Sofia Benali", "Olivia Brandt"}
    assert names("Machine Learning") == ml
    assert names("apprentissage automatique") == ml  # français
    assert names("ml") == ml  # abréviation
    assert names("pgvector") == ml
    assert names("SEO") == {"Léa Fontaine"}
    assert names("Kubernetes") == set()
    assert names("compétence inconnue") == set()


def test_filter_by_name_and_wildcards_are_literal(
    db_client: TestClient, three_candidates: dict[str, str]
) -> None:
    def total(query: str) -> int:
        return db_client.get("/candidates", params={"q": query}, headers=three_candidates).json()[
            "total"
        ]

    assert total("olivia") == 1  # insensible à la casse
    assert total("ben") == 1
    assert total("%") == 0  # « % » n'est pas un joker
    assert total("_") == 0
    assert total("'; DROP TABLE candidates; --") == 0
    assert total("Olivia") == 1  # la table existe toujours


def test_pagination(db_client: TestClient, three_candidates: dict[str, str]) -> None:
    page = db_client.get("/candidates?limit=2&offset=2", headers=three_candidates).json()

    assert page["total"] == 3 and page["limit"] == 2 and page["offset"] == 2
    assert [c["full_name"] for c in page["items"]] == ["Sofia Benali"]


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
def test_pagination_bounds_are_validated(
    db_client: TestClient, alice: dict[str, str], query: str
) -> None:
    assert db_client.get(f"/candidates?{query}", headers=alice).status_code == 422


# ------------------------------------------------------------------ suppression


def test_delete_removes_the_database_rows_and_the_file(
    db_client: TestClient, db_settings: Settings, migrated_db, alice: dict[str, str]
) -> None:
    from sqlalchemy import text

    candidate_id = upload(db_client, alice).json()["id"]
    assert len(stored_files(db_settings)) == 1

    response = db_client.delete(f"/candidates/{candidate_id}", headers=alice)

    assert response.status_code == 204 and response.content == b""
    assert stored_files(db_settings) == []
    assert db_client.get(f"/candidates/{candidate_id}", headers=alice).status_code == 404
    with migrated_db.connect() as conn:  # le texte extrait (donnée personnelle) a bien disparu
        assert conn.execute(text("SELECT count(*) FROM documents")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM candidates")).scalar_one() == 0


def test_after_deleting_the_same_file_can_be_imported_again(
    db_client: TestClient, alice: dict[str, str]
) -> None:
    same_bytes = render(PDF_CV)
    candidate_id = upload(db_client, alice, content=same_bytes).json()["id"]
    db_client.delete(f"/candidates/{candidate_id}", headers=alice)

    assert upload(db_client, alice, content=same_bytes).status_code == 201


def test_deleting_twice_returns_404(db_client: TestClient, alice: dict[str, str]) -> None:
    candidate_id = upload(db_client, alice).json()["id"]

    assert db_client.delete(f"/candidates/{candidate_id}", headers=alice).status_code == 204
    assert db_client.delete(f"/candidates/{candidate_id}", headers=alice).status_code == 404

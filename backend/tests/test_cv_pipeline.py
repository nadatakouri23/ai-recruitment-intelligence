"""Chaîne complète sur de vrais fichiers PDF/DOCX : lecture → nettoyage → analyse.

Les CV sont synthétiques et leur vérité terrain est écrite à la main (voir cv_factory.py) : ces
tests détectent les RÉGRESSIONS ; ils ne mesurent pas la performance sur de vrais CV.
"""

from datetime import date

import pytest

from app.modules.candidates.parsing.parser import parse_cv
from app.modules.candidates.parsing.text_cleaning import clean_text
from app.modules.candidates.profile import CandidateProfile
from app.modules.documents.extraction import detect_kind, extract_text
from tests.cv_factory import SYNTHETIC_CVS, SyntheticCV, render

TODAY = date(2026, 11, 11)
MAX_BYTES = 5 * 1024 * 1024


def run_pipeline(cv: SyntheticCV) -> CandidateProfile:
    content = render(cv)
    kind = detect_kind(cv.filename, content, MAX_BYTES)
    text = clean_text(extract_text(content, kind, max_pages=30).text)
    return parse_cv(text, today=TODAY)


@pytest.fixture(scope="module", params=SYNTHETIC_CVS, ids=lambda cv: cv.slug)
def case(request: pytest.FixtureRequest) -> tuple[SyntheticCV, CandidateProfile]:
    cv: SyntheticCV = request.param
    return cv, run_pipeline(cv)


def test_identity_is_extracted(case: tuple[SyntheticCV, CandidateProfile]) -> None:
    cv, profile = case

    assert profile.full_name == cv.name
    assert profile.email == cv.email
    assert profile.phone == cv.phone
    assert cv.link in profile.links


def test_skills_match_ground_truth(case: tuple[SyntheticCV, CandidateProfile]) -> None:
    cv, profile = case
    found = {s.name for s in profile.skills}
    truth = set(cv.truth.skills)

    assert found == truth, f"manquées={sorted(truth - found)} en_trop={sorted(found - truth)}"


def test_experience_titles_and_companies(case: tuple[SyntheticCV, CandidateProfile]) -> None:
    cv, profile = case

    assert [e.title for e in profile.experience] == list(cv.truth.titles)
    for item, company in zip(profile.experience, cv.truth.companies, strict=True):
        assert item.company is not None
        assert item.company.startswith(company)


def test_education_languages_certifications_projects(
    case: tuple[SyntheticCV, CandidateProfile],
) -> None:
    cv, profile = case

    assert [e.degree for e in profile.education] == list(cv.truth.degrees)
    assert {lang.language for lang in profile.languages} == set(cv.truth.languages)
    assert len(profile.certifications) == cv.truth.n_certifications
    assert len(profile.projects) == cv.truth.n_projects


def test_detected_language_and_completeness(case: tuple[SyntheticCV, CandidateProfile]) -> None:
    cv, profile = case

    assert profile.report.detected_language == cv.lang
    assert profile.report.extraction_completeness >= 0.9
    assert profile.report.warnings == []


def test_every_extracted_item_carries_its_source(
    case: tuple[SyntheticCV, CandidateProfile],
) -> None:
    _, profile = case
    items = [*profile.skills, *profile.experience, *profile.education, *profile.languages]

    assert all(item.provenance.snippet for item in items)
    assert all(item.provenance.origin == "extracted" for item in items)


def test_computed_values_are_flagged_as_inferred(
    case: tuple[SyntheticCV, CandidateProfile],
) -> None:
    _, profile = case

    assert all("duration_months" in e.inferred_fields for e in profile.experience)
    assert "total_experience_months" in profile.report.inferred_fields
    assert profile.report.limitations  # les limites sont toujours rappelées


def test_total_experience_does_not_double_count_overlaps() -> None:
    cv = next(c for c in SYNTHETIC_CVS if c.slug == "en_ml_engineer")
    profile = run_pipeline(cv)

    # Jul 2019 → nov. 2026 en continu ; la mission de Sep 2022 à Aug 2023 chevauche le poste actuel.
    assert profile.total_experience_months == cv.truth.total_months_at_2026_11
    assert sum(e.duration_months or 0 for e in profile.experience) > profile.total_experience_months


def test_experience_skills_are_linked_to_each_job() -> None:
    cv = next(c for c in SYNTHETIC_CVS if c.slug == "en_backend_engineer")
    profile = run_pipeline(cv)
    first, second = profile.experience

    assert {"Java", "Spring", "Kubernetes", "Terraform", "GitHub Actions"} <= set(first.skills)
    assert {"Node.js", "React", "Azure", "PostgreSQL", "Redis"} <= set(second.skills)
    assert "Kubernetes" not in second.skills


def test_docx_table_content_is_read() -> None:
    cv = next(c for c in SYNTHETIC_CVS if c.slug == "en_data_analyst")
    content = render(cv)

    text = extract_text(content, detect_kind(cv.filename, content, MAX_BYTES), 30).text

    assert "Power BI, Tableau, Excel, SQL" in text


# ------------------------------------------------------------------ robustesse et éthique


def test_garbage_text_does_not_invent_anything() -> None:
    profile = parse_cv("lorem ipsum dolor sit amet " * 20, today=TODAY)

    assert profile.full_name is None
    assert profile.email is None
    assert profile.phone is None
    assert profile.skills == []
    assert profile.experience == []
    assert profile.education == []
    assert profile.total_experience_months is None
    assert profile.report.extraction_completeness == 0
    assert profile.report.warnings  # on avertit au lieu de deviner


def test_empty_text_does_not_crash() -> None:
    profile = parse_cv("", today=TODAY)

    assert profile.report.extraction_completeness == 0
    assert "Texte très court" in " ".join(profile.report.warnings)


def test_protected_characteristics_are_never_extracted() -> None:
    text = (
        "Camille Martin\n"
        "Née le 12/03/1990 à Casablanca\n"
        "Nationalité : marocaine\n"
        "Situation familiale : mariée, 2 enfants\n"
        "Adresse : 12 rue des Lilas, 75000 Paris\n"
        "camille.martin@example.com\n"
        "COMPÉTENCES\nPython, SQL\n"
        "CENTRES D'INTÉRÊT\nPratique religieuse, militantisme politique\n"
    )

    dumped = parse_cv(text, today=TODAY).model_dump_json().lower()

    for forbidden in (
        "1990",
        "casablanca",
        "marocaine",
        "mariée",
        "enfants",
        "lilas",
        "religieuse",
    ):
        assert forbidden not in dumped


def test_protected_traits_do_not_leak_through_the_stored_name_field() -> None:
    profile = parse_cv(
        "Née le 12/03/1990\nNationalité : marocaine\nPython, SQL, Docker", today=TODAY
    )

    assert profile.full_name is None

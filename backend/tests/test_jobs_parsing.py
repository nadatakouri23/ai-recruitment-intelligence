"""Analyse des offres d'emploi : requis / optionnel, expérience, niveau d'études, pièges."""

import pytest

from app.modules.jobs.parsing import analyze_job
from tests.job_factory import SYNTHETIC_JOBS, SyntheticJob


@pytest.fixture(params=SYNTHETIC_JOBS, ids=lambda j: j.slug)
def job(request: pytest.FixtureRequest) -> SyntheticJob:
    return request.param


def test_required_and_optional_skills_match_ground_truth(job: SyntheticJob) -> None:
    profile = analyze_job(job.title, job.description)

    assert set(profile.required_skills) == set(job.required)
    assert set(profile.optional_skills) == set(job.optional)


def test_experience_and_education_match_ground_truth(job: SyntheticJob) -> None:
    profile = analyze_job(job.title, job.description)

    assert profile.min_experience_years == job.min_years
    assert profile.education_level == job.education_level


def test_required_and_optional_never_overlap(job: SyntheticJob) -> None:
    profile = analyze_job(job.title, job.description)

    assert not set(profile.required_skills) & set(profile.optional_skills)


def test_company_perks_section_is_ignored() -> None:
    data = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    backend = next(j for j in SYNTHETIC_JOBS if j.slug == "backend_en")

    # « Nous offrons … (Kubernetes, Terraform) » et « Benefits … Docker » ne sont pas des exigences.
    data_skills = analyze_job(data.title, data.description)
    backend_skills = analyze_job(backend.title, backend.description)

    assert "Kubernetes" not in data_skills.required_skills + data_skills.optional_skills
    assert "Terraform" not in data_skills.required_skills + data_skills.optional_skills
    assert "Docker" not in backend_skills.required_skills + backend_skills.optional_skills


def test_responsibilities_and_preferred_are_extracted(job: SyntheticJob) -> None:
    profile = analyze_job(job.title, job.description)

    if job.slug in ("data_scientist_fr", "backend_en", "devops_fr", "marketing_fr"):
        assert 2 <= len(profile.responsibilities) <= 3
    if job.optional:
        assert profile.preferred_qualifications


def test_technical_requirements_are_the_technical_subset_of_required() -> None:
    marketing = next(j for j in SYNTHETIC_JOBS if j.slug == "marketing_fr")
    devops = next(j for j in SYNTHETIC_JOBS if j.slug == "devops_fr")

    assert analyze_job(marketing.title, marketing.description).technical_requirements == []
    assert "Kubernetes" in analyze_job(devops.title, devops.description).technical_requirements


def test_skill_in_both_sections_is_required() -> None:
    profile = analyze_job(
        "Dev",
        "Profil recherché\n- Python et Docker\nAtouts\n- Docker est un plus, Kubernetes aussi\n"
        "Ceci est une offre suffisamment longue pour passer.",
    )

    assert "Docker" in profile.required_skills
    assert "Docker" not in profile.optional_skills
    assert "Kubernetes" in profile.optional_skills


def test_cue_words_inside_a_line_make_a_skill_optional() -> None:
    profile = analyze_job(
        "Développeur",
        "Nous cherchons quelqu'un qui maîtrise Python. La connaissance de Docker serait un plus. "
        "Le candidat devra aussi connaître Git, c'est indispensable.",
    )

    assert "Docker" in profile.optional_skills
    assert "Git" in profile.required_skills


def test_short_bullets_may_open_with_an_ambiguous_tool_name() -> None:
    profile = analyze_job(
        "Dev",
        "Profil recherché\n- Python\n- Tableau\nAtouts\n- Spark est un plus\n- Excel\n"
        "Texte de remplissage pour atteindre la longueur minimale de l'offre ici.",
    )

    assert {"Python", "Tableau", "Excel"} <= set(profile.required_skills) | set(
        profile.optional_skills
    )
    assert "Spark" in profile.optional_skills
    assert "Tableau" in profile.required_skills


def test_long_sentences_stay_prudent_about_ambiguous_words() -> None:
    profile = analyze_job(
        "Dev",
        "Profil recherché\n- Excel dans la capacité à communiquer clairement avec les équipes\n"
        "Texte de remplissage pour atteindre la longueur minimale de l'offre ici.",
    )

    assert "Excel" not in profile.required_skills


def test_skills_in_the_title_are_required() -> None:
    profile = analyze_job("Python Developer", "Join our team " * 20)

    assert profile.required_skills == ["Python"]


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("3 ans d'expérience en développement", 3),
        ("Au moins 4 ans d'expérience", 4),
        ("5+ years of experience required", 5),
        ("Experience: minimum 2 years", 2),
        ("minimum 7 ans", 7),
        ("Expérience professionnelle de 6 ans", 6),
        ("Débutant accepté", None),
        ("Une expérience significative", None),
        ("Founded in 1999, we have 200 employees", None),  # des nombres ne sont pas des exigences
    ],
)
def test_years_of_experience(text: str, years: int | None) -> None:
    profile = analyze_job("Poste", f"{text}. " + "Texte de remplissage. " * 12)

    assert profile.min_experience_years == years


def test_several_different_durations_raise_a_warning() -> None:
    profile = analyze_job(
        "Poste", "3 ans d'expérience en Python et 5 ans d'expérience en gestion. " * 3
    )

    assert profile.min_experience_years == 3  # la première
    assert any("Plusieurs durées" in w for w in profile.warnings)


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("Bac+5 exigé", 5),
        ("Bac+3 à Bac+5", 3),  # niveau minimal accepté
        ("Master ou diplôme d'ingénieur", 5),
        ("Doctorat en informatique", 8),
        ("Licence ou équivalent", 3),
        ("BTS ou DUT", 2),
        ("Bachelor's degree", 3),
        ("Business Analyst (BA) confirmé", None),  # « BA » n'est pas un diplôme dans une offre
        ("Rejoignez ma nouvelle équipe", None),  # « ma » non plus
    ],
)
def test_education_level(text: str, level: int | None) -> None:
    profile = analyze_job("Poste", f"{text}. " + "Texte de remplissage. " * 12)

    assert profile.education_level == level


def test_unstructured_offer_gets_warnings_instead_of_guesses() -> None:
    profile = analyze_job(
        "Poste mystère", "Nous cherchons une personne sympathique et motivée. " * 6
    )

    assert profile.required_skills == [] and profile.optional_skills == []
    assert profile.min_experience_years is None
    assert profile.education_level is None
    joined = " ".join(profile.warnings)
    assert (
        "Aucune compétence" in joined
        and "Nombre d'années" in joined
        and "Niveau d'études" in joined
    )


def test_very_short_offer_is_flagged() -> None:
    assert any("très courte" in w for w in analyze_job("Dev", "Python").warnings)


def test_language_is_detected() -> None:
    fr = next(j for j in SYNTHETIC_JOBS if j.slug == "devops_fr")
    en = next(j for j in SYNTHETIC_JOBS if j.slug == "backend_en")

    assert analyze_job(fr.title, fr.description).detected_language == "fr"
    assert analyze_job(en.title, en.description).detected_language == "en"

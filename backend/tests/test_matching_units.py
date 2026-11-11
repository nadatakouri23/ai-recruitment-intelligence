"""Composantes du matching, poids, préparation du texte (sans scikit-learn, sans base)."""

import pytest
from pydantic import ValidationError

from app.modules.candidates.parsing.education import education_level, label, required_level
from app.modules.matching.components import (
    education_score,
    experience_score,
    keyword_score,
    skills_match,
)
from app.modules.matching.engine import format_duration
from app.modules.matching.text import analyzer, anonymized_cv_text, tokens
from app.modules.matching.weights import MatchingWeights

# ------------------------------------------------------------------ poids


def test_weights_are_normalized_keeping_their_ratios() -> None:
    weights = MatchingWeights(skills=2, experience=1, tfidf=1, keyword=0, education=0).normalized()

    assert weights.skills == 0.5 and weights.experience == 0.25 and weights.tfidf == 0.25
    assert weights.keyword == 0 and weights.education == 0
    assert round(weights.total(), 6) == 1


def test_default_weights_sum_to_one_after_normalization() -> None:
    assert round(MatchingWeights().normalized().total(), 6) == 1


def test_all_zero_weights_are_rejected() -> None:
    with pytest.raises(ValidationError, match="strictement positif"):
        MatchingWeights(skills=0, experience=0, tfidf=0, keyword=0, education=0)


def test_negative_or_absurd_weights_are_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchingWeights(skills=-1)
    with pytest.raises(ValidationError):
        MatchingWeights(skills=1_000_000)


# ------------------------------------------------------------------ compétences


def test_skills_match_reports_matched_and_missing() -> None:
    result = skills_match(["Python", "SQL", "Docker"], ["AWS", "Git"], {"Python", "Docker", "AWS"})

    assert result.matched_required == ["Python", "Docker"]
    assert result.missing_required == ["SQL"]
    assert result.matched_optional == ["AWS"]
    assert result.missing_optional == ["Git"]
    assert result.score == pytest.approx(0.8 * (2 / 3) + 0.2 * 0.5)


def test_skills_score_with_only_required_or_only_optional() -> None:
    assert skills_match(["A", "B"], [], {"A"}).score == 0.5
    assert skills_match([], ["A", "B"], {"A", "B"}).score == 1.0


def test_skills_score_is_not_evaluable_when_the_job_lists_no_skill() -> None:
    assert skills_match([], [], {"Python"}).score is None


def test_extra_candidate_skills_do_not_increase_the_score() -> None:
    few = skills_match(["Python"], [], {"Python"}).score
    many = skills_match(["Python"], [], {"Python", "Java", "Rust", "Go"}).score

    assert few == many == 1.0


# ------------------------------------------------------------------ expérience, études, mots-clés


@pytest.mark.parametrize(
    ("required", "months", "expected"),
    [
        (3, 36, 1.0),
        (3, 72, 1.0),  # plafonné : plus d'expérience n'augmente pas le score
        (4, 24, 0.5),
        (5, 0, 0.0),  # zéro mois lus, expérience réellement nulle
        (None, 60, None),  # l'offre n'exige rien
        (0, 60, None),
        (3, None, None),  # expérience illisible : non évalué, pas « zéro »
    ],
)
def test_experience_score(required: int | None, months: int | None, expected: float | None) -> None:
    assert experience_score(required, months) == expected


@pytest.mark.parametrize(
    ("required", "candidate", "expected"),
    [
        (5, 5, 1.0),
        (5, 8, 1.0),
        (5, 3, 0.6),
        (3, 2, pytest.approx(2 / 3)),
        (None, 5, None),
        (5, None, None),  # aucun diplôme lu : non évalué
    ],
)
def test_education_score(
    required: int | None, candidate: int | None, expected: float | None
) -> None:
    assert education_score(required, candidate) == expected


def test_keyword_score_is_the_share_of_job_words_found() -> None:
    assert keyword_score("python docker kubernetes", "expert python et docker") == pytest.approx(
        2 / 3
    )
    assert keyword_score("python", "rien à voir") == 0
    assert keyword_score("le la les de", "n'importe quoi") is None  # que des mots vides


def test_education_levels() -> None:
    assert education_level("Master Intelligence Artificielle") == 5
    assert education_level("Diplôme d'Ingénieur") == 5
    assert education_level("Licence Informatique") == 3
    assert education_level("BSc Computer Science") == 3
    assert education_level("BA Economics") == 3
    assert education_level("MSc") == 5
    assert education_level("Doctorat") == 8
    assert education_level("Bac+4") == 4
    assert education_level("Baccalauréat") == 0
    assert education_level("Formation interne") is None
    assert education_level("Maîtrise en informatique") == 4  # champ « diplôme » d'un CV
    assert required_level("BA confirmé") is None
    # « maîtrise » est un mot courant dans une offre, pas le diplôme Bac+4.
    assert required_level("Maîtrise de Python et d'Excel") is None
    assert label(5) == "Bac+5 (master)" and label(7) == "Bac+7"


def test_format_duration() -> None:
    assert format_duration(99) == "8 ans 3 mois"
    assert format_duration(24) == "2 ans"
    assert format_duration(5) == "5 mois"
    assert format_duration(13) == "1 an 1 mois"


# ------------------------------------------------------------------ texte


CV_TEXT = """Camille Martin
Ingénieure Data
camille.martin@example.com | +33 6 11 22 33 44 | github.com/cmartin

PROFIL
Data scientist passionnée par le NLP.

EXPÉRIENCE PROFESSIONNELLE
Data Scientist
Acme, Paris
Mars 2021 – Présent
- Modèles de langage avec Python

COMPÉTENCES
Python, SQL

LANGUES
Arabe (natif), Anglais (C1)

CENTRES D'INTÉRÊT
Pratique religieuse, militantisme

RÉFÉRENCES
Sur demande, M. Dupont
"""


def test_anonymized_text_keeps_only_job_related_sections() -> None:
    text = anonymized_cv_text(CV_TEXT)

    assert (
        "Data scientist passionnée" in text
        and "Modèles de langage" in text
        and "Python, SQL" in text
    )
    for excluded in (
        "Camille",
        "Martin",
        "@",
        "+33",
        "github",
        "Arabe",
        "Anglais",
        "religieuse",
        "Dupont",
    ):
        assert excluded not in text


def test_tokens_drop_stopwords_numbers_and_accents() -> None:
    assert tokens("Le développement de 3 applications en C++ et Node.js") == [
        "developpement", "applications", "c++", "node.js"
    ]  # fmt: skip


def test_feminine_job_titles_are_neutralized() -> None:
    assert tokens("Ingénieure et Développeuse, Directrice, Chargée de projet") == [
        "ingenieur", "developpeur", "directeur", "charge", "projet"
    ]  # fmt: skip
    assert tokens("Ingénieur Développeur") == tokens("Ingénieure Développeuse")


def test_analyzer_adds_bigrams_of_consecutive_words() -> None:
    assert analyzer("machine learning engineer") == [
        "machine", "learning", "engineer", "machine learning", "learning engineer"
    ]  # fmt: skip

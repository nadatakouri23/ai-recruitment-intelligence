"""Tests unitaires du parseur : nettoyage, sections, dates, compétences (dont les pièges)."""

from datetime import date

import pytest

from app.modules.candidates.parsing.dates import (
    find_date_range,
    format_date,
    merged_months,
    month_interval,
)
from app.modules.candidates.parsing.language_detection import detect_language
from app.modules.candidates.parsing.sections import Line, detect_heading, split_sections
from app.modules.candidates.parsing.skills import (
    canonical_skill_name,
    extract_skills,
    find_skills_in_text,
)
from app.modules.candidates.parsing.text_cleaning import clean_text, fold

TODAY = date(2026, 11, 11)

# ------------------------------------------------------------------ nettoyage


def test_clean_text_normalizes_bullets_spaces_and_blank_lines() -> None:
    raw = "﻿  Titre  \r\n\r\n\r\n• Premier   point\n▪ Second point\n\x00\n- Tiret"

    assert clean_text(raw) == "Titre\n\n- Premier point\n- Second point\n\n- Tiret"


def test_clean_text_turns_unmapped_pdf_glyphs_into_bullets() -> None:
    raw = "(cid:127) Premier point\n(cid:127)(cid:127) Second\nTexte avec (cid:12) glyphe"

    assert clean_text(raw) == "- Premier point\n- Second\nTexte avec glyphe"


def test_clean_text_is_idempotent() -> None:
    once = clean_text("•  Texte\n\n\n  autre ligne ﬁ")
    assert clean_text(once) == once


def test_fold_keeps_length_so_positions_map_back() -> None:
    text = "Ingénierie des données — Œuvre à côté"
    assert len(fold(text)) == len(text)
    assert fold("ÉCOLE Supérieure") == "ecole superieure"


# ------------------------------------------------------------------ sections


@pytest.mark.parametrize(
    ("line", "label"),
    [
        ("EXPÉRIENCE PROFESSIONNELLE", "experience"),
        ("Work Experience", "experience"),
        ("Compétences techniques :", "skills"),
        ("--- Formation ---", "education"),
        ("LANGUES", "languages"),
        ("Centres d'intérêt", "interests"),
        ("Certifications", "certifications"),
    ],
)
def test_headings_are_recognized_in_french_and_english(line: str, label: str) -> None:
    assert detect_heading(line) == label


@pytest.mark.parametrize(
    "line",
    [
        "Conception d'un moteur de recherche",
        "Experience in Python and SQL for several years",
        "Languages: Python, Java",  # libellé de rubrique, pas un titre de section
        "",
    ],
)
def test_ordinary_lines_are_not_headings(line: str) -> None:
    assert detect_heading(line) is None


def test_split_sections_assigns_header_then_sections() -> None:
    lines, found = split_sections("Jean Dupont\nPROFIL\nTexte\nFORMATION\nMaster X")

    assert found == ["summary", "education"]
    assert lines == [
        Line("Jean Dupont", "header"),
        Line("Texte", "summary"),
        Line("Master X", "education"),
    ]


# ------------------------------------------------------------------ dates


@pytest.mark.parametrize(
    ("line", "start", "end", "current"),
    [
        ("Mars 2021 – Présent", "2021-03", None, True),
        ("Jan 2020 - Present", "2020-01", None, True),
        ("06/2015 - 12/2019", "2015-06", "2019-12", False),
        ("2018-2020", "2018", "2020", False),
        ("Septembre 2018 – Février 2021", "2018-09", "2021-02", False),
        ("de 2019 à 2021", "2019", "2021", False),
        ("2022 - aujourd'hui", "2022", None, True),
        ("Data Scientist | Acme | Sept. 2017 - Mai 2019", "2017-09", "2019-05", False),
    ],
)
def test_find_date_range(line: str, start: str, end: str | None, current: bool) -> None:
    period = find_date_range(line)

    assert period is not None
    assert format_date(period.start_year, period.start_month) == start
    assert format_date(period.end_year, period.end_month) == end
    assert period.is_current is current


@pytest.mark.parametrize(
    "line",
    [
        "Université de Lyon 2016",  # une seule année : pas une période
        "+33 6 11 22 33 44",  # numéro de téléphone
        "Version 2.0 - 2024 features",  # pas deux dates
        "",
    ],
)
def test_non_periods_are_not_dates(line: str) -> None:
    assert find_date_range(line) is None


def test_month_interval_is_inclusive_and_uses_today_for_current() -> None:
    closed = find_date_range("Septembre 2018 – Février 2021")
    current = find_date_range("Mars 2021 – Présent")
    assert closed and current
    start, end = month_interval(closed, TODAY) or (0, -1)
    assert end - start + 1 == 30
    start, end = month_interval(current, TODAY) or (0, -1)
    assert end - start + 1 == 69


def test_inverted_period_is_rejected_not_negative() -> None:
    period = find_date_range("2020 - 2018")
    assert period is not None
    assert month_interval(period, TODAY) is None


def test_merged_months_counts_overlaps_once() -> None:
    a = (2020 * 12 + 1, 2020 * 12 + 12)  # 12 mois
    b = (2020 * 12 + 6, 2021 * 12 + 5)  # chevauche a
    c = (2021 * 12 + 6, 2021 * 12 + 8)  # adjacent à b
    d = (2023 * 12 + 1, 2023 * 12 + 2)  # séparé
    assert merged_months([a]) == 12
    assert merged_months([a, b]) == 17  # jan 2020 → mai 2021
    assert merged_months([a, b, c, d]) == 20 + 2
    assert merged_months([]) == 0


# ------------------------------------------------------------------ compétences


def _names(text: str) -> set[str]:
    return set(find_skills_in_text(text))


def test_java_is_not_found_inside_javascript() -> None:
    assert _names("Développement en JavaScript") == {"JavaScript"}
    assert _names("Java et JavaScript") == {"Java", "JavaScript"}


def test_sql_is_not_found_inside_mysql_or_postgresql() -> None:
    assert _names("MySQL") == {"MySQL"}
    assert _names("PostgreSQL") == {"PostgreSQL"}


def test_symbols_in_names_are_handled() -> None:
    assert _names("Développeur C++ et C# sous .NET") == {"C++", "C#", ".NET"}
    assert _names("ASP.NET Core") == {".NET"}
    assert _names("CI/CD avec GitLab CI") >= {"CI/CD", "GitLab CI"}


def test_longest_alias_wins() -> None:
    assert _names("React Native") == {"React Native"}
    assert _names("Spring Boot") == {"Spring"}
    assert _names("GitHub Actions") == {"GitHub Actions"}


def test_french_and_english_aliases_map_to_one_canonical_name() -> None:
    assert _names("apprentissage automatique") == {"Machine Learning"}
    assert _names("machine learning") == {"Machine Learning"}
    assert _names("Traitement du langage naturel") == {"NLP"}
    assert _names("ingénierie des données") == {"Data Engineering"}
    assert _names("Méthodes agiles") == {"Agile"}


@pytest.mark.parametrize(
    "text",
    [
        "Spring 2020 internship at a bank",  # la saison, pas le framework
        "Spring semester abroad",
        "Plan C for the project",
        "R&D department",
        "Go to market strategy",
        "Création d'un tableau de bord commercial",  # « tableau » français
        "Une vue d'ensemble du projet",  # « vue » français
        "I excel at teamwork",  # verbe anglais
        "Excel at communication",  # début de phrase
        "Contacted via github.com/foo and foo@example.com",
    ],
)
def test_common_words_are_not_skills_outside_the_skills_section(text: str) -> None:
    assert _names(text) == set()


def test_ambiguous_word_is_accepted_when_the_sentence_has_an_unambiguous_skill() -> None:
    assert _names("Maîtrise de Java, Spring et SQL") == {"Java", "Spring", "SQL"}
    assert _names("Python et Tableau") == {"Python", "Tableau"}
    # Seul, le mot reste refusé.
    assert _names("Stage de Spring 2020 dans une banque") == set()
    assert _names("Spring semester abroad") == set()
    # Les lettres isolées ne profitent jamais de cette règle.
    assert _names("Python, R et C") == {"Python"}
    assert _names("Go to market with Python") == {"Python"}


def test_listing_mode_accepts_an_ambiguous_tool_that_opens_a_short_bullet() -> None:
    assert find_skills_in_text("Spark est un plus", mode="listing") == ["Spark"]
    assert find_skills_in_text("Tableau", mode="listing") == ["Tableau"]
    # Le mode par défaut reste prudent : début de phrase = pas une compétence.
    assert find_skills_in_text("Spark est un plus") == []
    # Les lettres isolées ne sont jamais acceptées hors de la section compétences.
    assert find_skills_in_text("R", mode="listing") == []
    assert find_skills_in_text("Spring 2020", mode="listing") == []


def test_known_limitation_capitalized_ambiguous_word_mid_sentence() -> None:
    # Compromis assumé : « Spark » en milieu de phrase est lu comme Apache Spark.
    assert _names("Built ETL jobs with Spark") >= {"Spark", "ETL"}


def test_ambiguous_letters_only_count_in_the_skills_section() -> None:
    lines = [
        Line("Langages : Python, R, C, Go", "skills"),
        Line("Participation au projet R et au plan C avec Go", "experience"),
    ]
    items = {s.name: s for s in extract_skills(lines)}

    assert {"R", "C", "Go", "Python"} <= set(items)
    assert all(items[name].mentions == 1 for name in ("R", "C", "Go"))  # une seule ligne : la liste


def test_skill_provenance_points_to_the_source_line_and_section() -> None:
    lines = [Line("Poste", "experience"), Line("Déploiement avec Docker sur AWS", "experience")]
    docker = next(s for s in extract_skills(lines) if s.name == "Docker")

    assert docker.provenance.origin == "extracted"
    assert docker.provenance.section == "experience"
    assert "Docker" in docker.provenance.snippet
    assert docker.listed_in_skills_section is False


def test_canonical_skill_name_for_search() -> None:
    assert canonical_skill_name("ml") == "Machine Learning"
    assert canonical_skill_name("  Apprentissage Automatique ") == "Machine Learning"
    assert canonical_skill_name("python") == "Python"
    assert canonical_skill_name("compétence inventée") is None


# ------------------------------------------------------------------ langue


def test_language_detection() -> None:
    fr = "Ingénieur avec dix ans d'expérience dans le développement de produits pour des clients"
    en = "Engineer with ten years of experience in the development of products for clients"
    assert detect_language(fr) == "fr"
    assert detect_language(en) == "en"
    assert detect_language("Python SQL Docker") == "unknown"

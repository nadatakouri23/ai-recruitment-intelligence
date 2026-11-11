"""Découpage d'un CV en sections (titres reconnus en français et en anglais)."""

import re
from dataclasses import dataclass
from typing import Literal

from app.modules.candidates.parsing.text_cleaning import fold

SectionLabel = Literal[
    "header",
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "languages",
    "certifications",
    "interests",
    "other",
]

# Titres connus, déjà « pliés » (minuscules, sans accents).
_HEADINGS: dict[SectionLabel, tuple[str, ...]] = {
    "summary": (
        "profil",
        "profile",
        "summary",
        "professional summary",
        "profil professionnel",
        "professional profile",
        "resume",
        "a propos",
        "a propos de moi",
        "about me",
        "about",
        "objectif",
        "objectif professionnel",
        "objective",
        "career objective",
    ),
    "experience": (
        "experience",
        "experiences",
        "experience professionnelle",
        "experiences professionnelles",
        "work experience",
        "professional experience",
        "parcours professionnel",
        "employment history",
        "work history",
        "career history",
        "stages",
        "stages et experiences",
        "internships",
        "experience et stages",
    ),
    "education": (
        "formation",
        "formations",
        "education",
        "etudes",
        "parcours academique",
        "diplomes",
        "academic background",
        "academic qualifications",
        "formation et diplomes",
        "education and training",
        "parcours scolaire",
        "cursus",
        "formation academique",
    ),
    "skills": (
        "competences",
        "competences techniques",
        "technical skills",
        "skills",
        "key skills",
        "technologies",
        "competences cles",
        "hard skills",
        "outils",
        "tools",
        "technical competencies",
        "competences informatiques",
        "core skills",
        "expertise",
        "technical expertise",
        "competences et outils",
    ),
    "projects": (
        "projets",
        "projects",
        "projets personnels",
        "personal projects",
        "academic projects",
        "projets academiques",
        "selected projects",
        "projets realises",
        "realisations",
    ),
    "languages": ("langues", "languages", "competences linguistiques", "language skills"),
    "certifications": (
        "certifications",
        "certification",
        "certificats",
        "certificates",
        "licenses",
        "licences et certifications",
        "certifications et formations",
        "licenses and certifications",
        "formations complementaires",
        "courses",
    ),
    "interests": (
        "centres d interet",
        "centres d'interet",
        "interets",
        "interests",
        "hobbies",
        "loisirs",
        "activites extra professionnelles",
        "vie associative",
        "extracurricular activities",
    ),
    "other": (
        "references",
        "publications",
        "benevolat",
        "volunteering",
        "volunteer experience",
        "awards",
        "distinctions",
        "prix",
        "honors",
        "informations complementaires",
        "additional information",
        "divers",
        "miscellaneous",
        "contact",
        "coordonnees",
        "personal details",
        "informations personnelles",
    ),
}

_PHRASE_TO_LABEL: dict[str, SectionLabel] = {
    phrase: label for label, phrases in _HEADINGS.items() for phrase in phrases
}

_NON_ALNUM = re.compile(r"[^a-z0-9&' /]+")


@dataclass(frozen=True)
class Line:
    text: str
    section: SectionLabel


def detect_heading(line: str) -> SectionLabel | None:
    """Retourne la section annoncée par cette ligne, ou None si ce n'est pas un titre."""
    if not line or len(line) > 50 or len(line.split()) > 6:
        return None
    normalized = _NON_ALNUM.sub(" ", fold(line))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return _PHRASE_TO_LABEL.get(normalized)


def split_sections(cleaned_text: str) -> tuple[list[Line], list[SectionLabel]]:
    """Associe chaque ligne à sa section.

    Les lignes avant le premier titre sont dans « header » (nom, contacts…). Les lignes de
    titre elles-mêmes ne sont pas conservées. Retourne aussi les sections trouvées, dans l'ordre.
    """
    lines: list[Line] = []
    found: list[SectionLabel] = []
    current: SectionLabel = "header"
    for text in cleaned_text.split("\n"):
        heading = detect_heading(text)
        if heading is not None:
            current = heading
            if heading not in found:
                found.append(heading)
            continue
        lines.append(Line(text=text, section=current))
    return lines, found

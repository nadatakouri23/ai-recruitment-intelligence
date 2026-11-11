"""Analyse par règles du texte d'une offre d'emploi (FR/EN).

Sépare compétences requises et optionnelles à l'aide des titres de section (« Profil recherché »,
« Nice to have »…) et d'indices dans la ligne (« un plus », « indispensable »…). Ce sont des
heuristiques : le recruteur peut corriger le résultat.
"""

import re
from typing import Literal

from app.modules.candidates.parsing.education import required_level
from app.modules.candidates.parsing.language_detection import detect_language
from app.modules.candidates.parsing.skills import find_skills_in_text, skill_category
from app.modules.candidates.parsing.text_cleaning import clean_text, fold
from app.modules.jobs.profile import JobProfile

PARSER_VERSION = "job-rules-0.1"

JobSection = Literal["unspecified", "responsibilities", "requirements", "preferred", "ignore"]

_HEADINGS: dict[JobSection, tuple[str, ...]] = {
    "responsibilities": (
        "missions",
        "mission",
        "vos missions",
        "responsabilites",
        "vos responsabilites",
        "responsibilities",
        "key responsibilities",
        "your role",
        "the role",
        "role",
        "what you will do",
        "what you'll do",
        "ce que vous ferez",
        "le poste",
        "duties",
        "activites",
        "taches",
        "principales missions",
    ),
    "requirements": (
        "profil",
        "profil recherche",
        "votre profil",
        "profil requis",
        "competences requises",
        "competences",
        "requirements",
        "required skills",
        "qualifications",
        "must have",
        "must-have",
        "prerequis",
        "what we are looking for",
        "who you are",
        "your profile",
        "experience requise",
        "indispensable",
        "technical requirements",
        "required qualifications",
        "skills",
        "vous avez",
        "vous etes",
        "competences techniques",
    ),
    "preferred": (
        "atouts",
        "nice to have",
        "nice-to-have",
        "souhaite",
        "souhaites",
        "un plus",
        "preferred",
        "preferred qualifications",
        "bonus",
        "apprecie",
        "competences appreciees",
        "bonus points",
        "plus",
        "serait un plus",
        "ideal",
        "idealement",
    ),
    "ignore": (
        "nous offrons",
        "avantages",
        "we offer",
        "benefits",
        "pourquoi nous rejoindre",
        "why join us",
        "a propos",
        "about us",
        "notre entreprise",
        "about the company",
        "company",
        "comment postuler",
        "how to apply",
        "processus de recrutement",
        "contact",
        "remuneration",
        "salary",
        "perks",
        "notre offre",
    ),
}
_PHRASE_TO_SECTION = {p: s for s, phrases in _HEADINGS.items() for p in phrases}
_NON_ALNUM = re.compile(r"[^a-z0-9&' /-]+")

_PREFERRED_CUE = re.compile(
    r"\b(nice[ -]to[ -]have|un plus|est un plus|serait un plus|souhait\w*|apprecie\w*|bonus|"
    r"preferred|ideal\w*|desirable|a plus|appreciated|atouts?|valorise\w*|un avantage)\b"
)
_REQUIRED_CUE = re.compile(
    r"\b(required|requis\w*|indispensable\w*|obligatoire\w*|must|mandatory|imperativ\w*|"
    r"exige\w*|essential)\b"
)

_SENTENCES = re.compile(r"(?<=[.;!?])\s+")

_YEARS_BEFORE = re.compile(
    r"\b(\d{1,2})\s*\+?\s*(?:ans?|years?|yrs?)\b[^.\n]{0,40}?\b(?:experience|exp)\b"
)
_YEARS_AFTER = re.compile(
    r"\b(?:experience|exp)\b[^.\n]{0,30}?\b(\d{1,2})\s*\+?\s*(?:ans?|years?|yrs?)\b"
)
_MIN_YEARS = re.compile(r"\b(?:minimum|min\.?|at least|au moins)\s*(\d{1,2})\s*(?:ans?|years?)\b")

_TECHNICAL = {"programming", "web", "data_ml", "database", "cloud_devops"}
_MAX_ITEMS = 15


def _heading(line: str) -> JobSection | None:
    if not line or len(line) > 60 or len(line.split()) > 7:
        return None
    normalized = re.sub(r"\s+", " ", _NON_ALNUM.sub(" ", fold(line))).strip(" -/")
    return _PHRASE_TO_SECTION.get(normalized)


def _years(text: str) -> tuple[int | None, bool]:
    """(années minimales, plusieurs valeurs différentes ?). Première valeur plausible."""
    folded = fold(text)
    values = [
        int(m.group(1))
        for pattern in (_YEARS_BEFORE, _YEARS_AFTER, _MIN_YEARS)
        for m in pattern.finditer(folded)
    ]
    values = [v for v in values if 0 < v <= 40]
    if not values:
        return None, False
    first = min(
        (m.start(), int(m.group(1)))
        for pattern in (_YEARS_BEFORE, _YEARS_AFTER, _MIN_YEARS)
        for m in pattern.finditer(folded)
        if 0 < int(m.group(1)) <= 40
    )[1]
    return first, len(set(values)) > 1


def analyze_job(title: str, description: str) -> JobProfile:
    """Analyse une offre. Aucune information absente du texte n'est inventée."""
    text = clean_text(description)
    required: list[str] = []
    optional: list[str] = []
    responsibilities: list[str] = []
    preferred_lines: list[str] = []
    saw_heading = {section: False for section in _HEADINGS}

    for skill in find_skills_in_text(title):  # le titre du poste dit ce qui est central
        required.append(skill)

    section: JobSection = "unspecified"
    for raw in text.split("\n"):
        heading = _heading(raw)
        if heading is not None:
            section = heading
            saw_heading[heading] = True
            continue
        line = re.sub(r"^- ", "", raw).strip()
        if not line or section == "ignore":
            continue
        if section == "responsibilities" and len(responsibilities) < _MAX_ITEMS:
            responsibilities.append(line[:300])
        # Les indices (« un plus », « indispensable ») valent pour leur PHRASE, pas toute la ligne.
        for sentence in _SENTENCES.split(line):
            folded = fold(sentence)
            is_optional = bool(_PREFERRED_CUE.search(folded)) and not _REQUIRED_CUE.search(folded)
            is_optional = is_optional or (
                section == "preferred" and not _REQUIRED_CUE.search(folded)
            )
            # Une puce courte (≤ 6 mots) est une liste d'exigences : un outil peut l'ouvrir.
            mode = "listing" if len(sentence.split()) <= 6 else "relaxed"
            for skill in find_skills_in_text(sentence, mode=mode):
                target = optional if is_optional else required
                if skill not in target:
                    target.append(skill)
            if is_optional and len(preferred_lines) < _MAX_ITEMS:
                preferred_lines.append(sentence[:300])

    optional = [s for s in optional if s not in required]  # « requis » l'emporte
    years, several_years = _years(description)

    warnings: list[str] = []
    if not (saw_heading["requirements"] or saw_heading["preferred"]):
        warnings.append(
            "Aucune section « profil / requis » reconnue : la distinction entre compétences "
            "requises et optionnelles repose uniquement sur des indices dans les phrases."
        )
    if not required and not optional:
        warnings.append(
            "Aucune compétence du référentiel détectée : ajoutez-les à la main, sinon le "
            "matching reposera uniquement sur la similarité de texte."
        )
    if years is None:
        warnings.append("Nombre d'années d'expérience non trouvé dans l'offre.")
    if several_years:
        warnings.append(
            "Plusieurs durées d'expérience différentes sont citées ; la première a été retenue. "
            "Vérifiez-la."
        )
    level = required_level(description)
    if level is None:
        warnings.append("Niveau d'études non trouvé dans l'offre.")
    if len(text) < 200:
        warnings.append("Offre très courte : l'analyse sera peu fiable.")

    return JobProfile(
        title=title.strip(),
        required_skills=required,
        optional_skills=optional,
        technical_requirements=[s for s in required if skill_category(s) in _TECHNICAL],
        min_experience_years=years,
        education_level=level,
        responsibilities=responsibilities,
        preferred_qualifications=preferred_lines,
        detected_language=detect_language(text),
        parser_version=PARSER_VERSION,
        warnings=warnings,
    )

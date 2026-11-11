"""Parseur de CV par règles : texte brut → CandidateProfile.

Aucun LLM : le résultat est déterministe et reproductible. Une extraction par LLM (Phase 7)
pourra être comparée à celle-ci sur les mêmes CV.
"""

from datetime import date

from app.modules.candidates.parsing.dates import merged_months
from app.modules.candidates.parsing.extractors import (
    extract_certifications,
    extract_education,
    extract_email,
    extract_experience,
    extract_languages,
    extract_links,
    extract_name,
    extract_phone,
    extract_projects,
    extract_summary,
)
from app.modules.candidates.parsing.language_detection import detect_language
from app.modules.candidates.parsing.sections import split_sections
from app.modules.candidates.parsing.skills import extract_skills
from app.modules.candidates.parsing.text_cleaning import clean_text
from app.modules.candidates.profile import (
    CandidateProfile,
    ParsingReport,
    Provenance,
)

PARSER_VERSION = "rules-0.1"

LIMITATIONS = [
    "Extraction par règles : un CV à mise en page inhabituelle (colonnes, tableaux, graphiques) "
    "peut être mal lu.",
    "Les titres de poste et entreprises sont déduits de la forme de la ligne "
    "et peuvent être inversés.",
    "Seules les compétences du référentiel sont détectées ; les autres sont ignorées.",
    "Les PDF scannés (images) ne sont pas lus : la reconnaissance de caractères "
    "(OCR) n'est pas implémentée.",
    "Les durées sont calculées à partir des dates ; les mois manquants sont estimés.",
    "La complétude mesure ce qui a été trouvé, pas son exactitude.",
]

# Poids de la complétude : (clé, poids). Somme = 1.
_COMPLETENESS_WEIGHTS = (
    ("name", 0.15),
    ("email", 0.15),
    ("experience", 0.25),
    ("education", 0.20),
    ("skills", 0.20),
    ("languages", 0.05),
)


def parse_cv(raw_text: str, today: date | None = None) -> CandidateProfile:
    """Analyse le texte d'un CV. `today` sert au calcul des périodes « jusqu'à aujourd'hui »."""
    today = today or date.today()
    cleaned = clean_text(raw_text)
    lines, sections_found = split_sections(cleaned)

    evidence: dict[str, Provenance] = {}
    name = extract_name(lines)
    email = extract_email(lines)
    phone = extract_phone(lines)
    for key, found in (("full_name", name), ("email", email), ("phone", phone)):
        if found:
            evidence[key] = found[1]

    experience, intervals = extract_experience(lines, today)
    education = extract_education(lines)
    skills = extract_skills(lines)
    languages = extract_languages(lines)
    projects = extract_projects(lines)
    certifications = extract_certifications(lines)

    total_months = merged_months(intervals) if intervals else None

    found = {
        "name": name is not None,
        "email": email is not None,
        "experience": bool(experience),
        "education": bool(education),
        "skills": len(skills) >= 3,
        "languages": bool(languages),
    }
    completeness = round(sum(w for key, w in _COMPLETENESS_WEIGHTS if found[key]), 2)

    warnings: list[str] = []
    if len(cleaned) < 300:
        warnings.append("Texte très court : le CV est peut-être incomplet ou mal lu.")
    if name is None:
        warnings.append("Nom non identifié.")
    if email is None:
        warnings.append("Adresse e-mail non trouvée.")
    if "experience" not in sections_found:
        warnings.append("Aucune section d'expérience reconnue.")
    elif not experience:
        warnings.append("Section d'expérience trouvée mais aucune période datée n'a pu être lue.")
    if "education" not in sections_found:
        warnings.append("Aucune section de formation reconnue.")
    if not skills:
        warnings.append("Aucune compétence du référentiel détectée.")

    language = detect_language(cleaned)
    if language == "unknown":
        warnings.append("Langue du CV non déterminée (ni français ni anglais nettement dominant).")

    inferred = []
    if any("duration_months" in item.inferred_fields for item in experience):
        inferred.append("experience[].duration_months")
    if total_months is not None:
        inferred.append("total_experience_months")

    return CandidateProfile(
        full_name=name[0] if name else None,
        email=email[0] if email else None,
        phone=phone[0] if phone else None,
        links=extract_links(lines),
        summary=extract_summary(lines),
        skills=skills,
        education=education,
        experience=experience,
        projects=projects,
        languages=languages,
        certifications=certifications,
        total_experience_months=total_months,
        field_evidence=evidence,
        report=ParsingReport(
            parser_version=PARSER_VERSION,
            detected_language=language,
            sections_found=list(sections_found),
            warnings=warnings,
            extraction_completeness=completeness,
            inferred_fields=inferred,
            limitations=LIMITATIONS,
        ),
    )

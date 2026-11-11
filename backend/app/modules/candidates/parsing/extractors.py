"""Extraction par règles des blocs d'un CV (FR/EN).

Hypothèses assumées (voir aussi `LIMITATIONS` dans parser.py) :
- CV sur une colonne, texte sélectionnable (pas de scan).
- Une expérience contient une période datée ; une formation contient un diplôme ou un établissement.
- Aucune donnée protégée n'est extraite (âge, genre, nationalité, situation familiale, photo,
  adresse) : ces informations ne doivent pas pouvoir influencer un classement.
"""

import re
from datetime import date

from app.modules.candidates.parsing.dates import (
    DateRange,
    find_date_range,
    find_years,
    format_date,
    month_interval,
)
from app.modules.candidates.parsing.sections import Line, detect_heading
from app.modules.candidates.parsing.skills import find_skills_in_text
from app.modules.candidates.parsing.text_cleaning import fold
from app.modules.candidates.profile import (
    CertificationItem,
    EducationItem,
    ExperienceItem,
    LanguageItem,
    ProjectItem,
    Provenance,
)

_SNIPPET_MAX = 240
_DESCRIPTION_MAX = 1000
_TRIM = " ,;:-–—|()[]•\t"


def _snippet(text: str) -> str:
    return text[:_SNIPPET_MAX]


def _texts(lines: list[Line], section: str) -> list[str]:
    return [line.text for line in lines if line.section == section]


# ============================================================ contact

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<![\w+])(?:\+|00)?\d[\d ().-]{7,}\d(?!\w)")
_URL = re.compile(
    r"(?:https?://|www\.)[^\s,;<>()]+|(?:linkedin\.com|github\.com|gitlab\.com)/[^\s,;<>()]+",
    re.IGNORECASE,
)
_NAME_TOKEN = re.compile(r"^[^\W\d_]+(?:['’-][^\W\d_]+)*\.?$")
_NOT_A_NAME = {"curriculum vitae", "cv", "resume", "curriculum", "vitae"}
_TITLE_WORDS = frozenset(
    "engineer ingenieur ingenieure developer developpeur developpeuse analyst analyste manager "
    "consultant consultante scientist data intern internship stagiaire stage lead architect "
    "architecte designer chef responsable directeur directrice director officer specialist "
    "specialiste technicien technician administrateur administrator assistant assistante "
    "coordinator coordinateur freelance apprenti alternant researcher chercheur teacher "
    "enseignant professeur tester devops head president software full stack backend frontend "
    "senior junior cloud machine learning product owner student etudiant etudiante".split()
)


def extract_email(lines: list[Line]) -> tuple[str, Provenance] | None:
    for line in lines:
        match = _EMAIL.search(line.text)
        if match:
            return match.group(0).lower(), Provenance(
                section=line.section, snippet=_snippet(line.text)
            )
    return None


def extract_phone(lines: list[Line]) -> tuple[str, Provenance] | None:
    # Uniquement en-tête / coordonnées : ailleurs, des suites de chiffres sont des dates ou des ids.
    for line in lines:
        if line.section not in ("header", "other"):
            continue
        for match in _PHONE.finditer(line.text):
            digits = re.sub(r"\D", "", match.group(0))
            if 9 <= len(digits) <= 15:
                return re.sub(r"\s+", " ", match.group(0)).strip(), Provenance(
                    section=line.section, snippet=_snippet(line.text)
                )
    return None


def extract_links(lines: list[Line]) -> list[str]:
    links: list[str] = []
    for line in lines:
        for match in _URL.finditer(line.text):
            link = match.group(0).rstrip(".,;)")
            if link.lower() not in (existing.lower() for existing in links):
                links.append(link)
    return links[:10]


def _looks_like_name(text: str) -> bool:
    if not text or len(text) > 40 or "@" in text or any(ch.isdigit() for ch in text):
        return False
    folded = fold(text).strip()
    if folded in _NOT_A_NAME or detect_heading(text) is not None:
        return False
    tokens = text.split()
    if not 2 <= len(tokens) <= 4 or not all(_NAME_TOKEN.match(t) for t in tokens):
        return False
    return not any(fold(t).strip(".") in _TITLE_WORDS for t in tokens)


def extract_name(lines: list[Line]) -> tuple[str, Provenance] | None:
    """Premier texte du haut du CV qui ressemble à un nom (2 à 4 mots, sans titre de poste)."""
    header = [line for line in lines if line.section == "header" and line.text][:8]
    for line in header:
        if _looks_like_name(line.text):
            return line.text, Provenance(section="header", snippet=_snippet(line.text))
    return None


def extract_summary(lines: list[Line]) -> str | None:
    text = " ".join(t for t in _texts(lines, "summary") if t)
    return text[:600] or None


# ============================================================ expérience

_HEADER_SPLIT = re.compile(r"\s+[|—–-]\s+|\s*\|\s*|\s+(?:at|chez|@)\s+", re.IGNORECASE)


def _has_title_word(text: str) -> bool:
    return any(token in _TITLE_WORDS for token in re.findall(r"[a-z]+", fold(text)))


def _without_range(text: str, period: DateRange) -> str:
    return (text[: period.span[0]] + " " + text[period.span[1] :]).strip(_TRIM + " ")


def _previous_header_indices(texts: list[str], index: int, boundary: int) -> list[int]:
    """Jusqu'à deux lignes juste au-dessus d'une date : titre du poste et/ou entreprise.

    Une ligne ne convient pas si c'est une puce, une phrase (point final), une ligne trop
    longue, une ligne vide ou une ligne qui contient elle-même une période.
    """
    indices: list[int] = []
    current = index - 1
    while current > boundary and len(indices) < 2:
        text = texts[current]
        if not text or text.startswith("- ") or len(text) > 80 or text.endswith("."):
            break
        if find_date_range(text) is not None:
            break
        indices.insert(0, current)
        current -= 1
    return indices


def _bullets_to_text(texts: list[str]) -> str:
    joined = " ".join(re.sub(r"^- ", "", t) for t in texts if t)
    return joined[:_DESCRIPTION_MAX]


def extract_experience(
    lines: list[Line], today: date
) -> tuple[list[ExperienceItem], list[tuple[int, int]]]:
    """Une expérience = une ligne datée, avec son titre, son entreprise et sa description.

    Retourne aussi les intervalles en mois, pour cumuler sans compter deux fois les
    chevauchements.
    """
    texts = _texts(lines, "experience")
    periods = [(i, p) for i, t in enumerate(texts) if (p := find_date_range(t)) is not None]
    if not periods:
        return [], []

    entries: list[
        tuple[int, int, DateRange, list[str]]
    ] = []  # (début, ligne date, période, en-têtes)
    boundary = -1
    for index, period in periods:
        remainder = _without_range(texts[index], period)
        header_lines = [remainder] if len(remainder) >= 3 else []
        start = index
        previous = _previous_header_indices(texts, index, boundary)
        if previous and (
            not header_lines
            or (not _has_title_word(remainder) and any(_has_title_word(texts[i]) for i in previous))
        ):
            header_lines = [texts[i] for i in previous] + header_lines
            start = previous[0]
        entries.append((start, index, period, header_lines))
        boundary = index

    items: list[ExperienceItem] = []
    intervals: list[tuple[int, int]] = []
    for position, (_start, date_index, period, header_lines) in enumerate(entries):
        end = entries[position + 1][0] if position + 1 < len(entries) else len(texts)
        description_lines = texts[date_index + 1 : end]
        parts = [
            part.strip(_TRIM)
            for header in header_lines
            for part in _HEADER_SPLIT.split(header)
            if part.strip(_TRIM)
        ]
        title = next((p for p in parts if _has_title_word(p)), parts[0] if parts else None)
        company = next((p for p in parts if p != title), None)

        interval = month_interval(period, today)
        duration = interval[1] - interval[0] + 1 if interval else None
        if interval:
            intervals.append(interval)
        full_text = " ".join(header_lines + description_lines)
        items.append(
            ExperienceItem(
                title=title,
                company=company,
                start=format_date(period.start_year, period.start_month),
                end=None if period.is_current else format_date(period.end_year, period.end_month),
                is_current=period.is_current,
                duration_months=duration,
                inferred_fields=["duration_months"] if duration is not None else [],
                description=_bullets_to_text(description_lines),
                skills=find_skills_in_text(full_text),
                provenance=Provenance(
                    section="experience",
                    snippet=_snippet(" | ".join(header_lines) or texts[date_index]),
                ),
            )
        )
    return items, intervals


# ============================================================ formation

_DEGREE = re.compile(
    r"\b(licence|license|bachelor|bsc|b\.sc|master|msc|m\.sc|mba|phd|doctorat|doctorate|"
    r"ingenieur|diplome|bts|dut|deug|baccalaureat|bac\s*\+?\d?|cycle|degree|engineering degree|"
    r"mastere|maitrise|ba|ma|bs|b\.a|m\.a|b\.s)\b"
)
_EDUCATION_SPLIT = re.compile(r"\s+[|—–-]\s+|\s*[|,;]\s*|\s+(?:at|chez|@)\s+", re.IGNORECASE)
_INSTITUTION = re.compile(
    r"\b(universite|university|ecole|school|institut|institute|college|faculte|faculty|"
    r"academy|academie|polytechnique|lycee|iut|ensa|enset|ensias|esi|insa|centrale)\b"
)


def extract_education(lines: list[Line]) -> list[EducationItem]:
    texts = [t for t in _texts(lines, "education") if t]
    groups: list[list[str]] = []
    for text in texts:
        folded = fold(text)
        starts_new = bool(groups) and (
            (_DEGREE.search(folded) and any(_DEGREE.search(fold(t)) for t in groups[-1]))
            or (find_date_range(text) and any(find_date_range(t) for t in groups[-1]))
        )
        if not groups or starts_new:
            groups.append([text])
        else:
            groups[-1].append(text)

    items: list[EducationItem] = []
    for group in groups:
        degree = institution = None
        for text in group:
            period = find_date_range(text)
            cleaned = _without_range(text, period) if period else text
            for part in _EDUCATION_SPLIT.split(cleaned):
                part = part.strip(_TRIM)
                folded = fold(part)
                if institution is None and _INSTITUTION.search(folded):
                    institution = part
                elif degree is None and _DEGREE.search(folded):
                    degree = part
        if degree is None and institution is None:
            continue
        years = [y for t in group for y in find_years(t)]
        period = next((p for t in group if (p := find_date_range(t))), None)
        start_year = period.start_year if period else (min(years) if years else None)
        end_year = (
            period.end_year if period and period.end_year else (max(years) if years else None)
        )
        if start_year == end_year and period is None:
            start_year = None  # une seule année citée : c'est l'année de fin / d'obtention
        items.append(
            EducationItem(
                degree=degree,
                institution=institution,
                start_year=start_year,
                end_year=end_year,
                provenance=Provenance(section="education", snippet=_snippet(" | ".join(group))),
            )
        )
    return items


# ============================================================ projets


def extract_projects(lines: list[Line]) -> list[ProjectItem]:
    """Blocs séparés par une ligne vide ; sinon, chaque ligne non puce ouvre un projet."""
    texts = _texts(lines, "projects")
    blocks: list[list[str]] = [[]]
    for text in texts:
        if not text:
            if blocks[-1]:
                blocks.append([])
        else:
            blocks[-1].append(text)
    blocks = [b for b in blocks if b]
    if len(blocks) == 1 and sum(1 for t in blocks[0] if not t.startswith("- ")) > 1:
        split: list[list[str]] = []
        for text in blocks[0]:
            if not text.startswith("- ") or not split:
                split.append([text])
            else:
                split[-1].append(text)
        blocks = split

    items: list[ProjectItem] = []
    for block in blocks:
        name = re.sub(r"^- ", "", block[0]).strip(_TRIM)
        if not name:
            continue
        body = " ".join(re.sub(r"^- ", "", t) for t in block[1:])
        items.append(
            ProjectItem(
                name=name[:200],
                description=body[:_DESCRIPTION_MAX],
                technologies=find_skills_in_text(" ".join(block)),
                provenance=Provenance(section="projects", snippet=_snippet(" ".join(block))),
            )
        )
    return items[:20]


# ============================================================ langues

_LANGUAGES: dict[str, str] = {
    "francais": "French", "french": "French", "anglais": "English", "english": "English",
    "arabe": "Arabic", "arabic": "Arabic", "espagnol": "Spanish", "spanish": "Spanish",
    "allemand": "German", "german": "German", "italien": "Italian", "italian": "Italian",
    "portugais": "Portuguese", "portuguese": "Portuguese", "chinois": "Chinese",
    "chinese": "Chinese", "mandarin": "Chinese", "russe": "Russian", "russian": "Russian",
    "japonais": "Japanese", "japanese": "Japanese", "turc": "Turkish", "turkish": "Turkish",
    "neerlandais": "Dutch", "dutch": "Dutch", "berbere": "Amazigh", "amazigh": "Amazigh",
    "tamazight": "Amazigh", "hindi": "Hindi", "urdu": "Urdu", "korean": "Korean",
    "coreen": "Korean", "polish": "Polish", "polonais": "Polish", "swedish": "Swedish",
    "suedois": "Swedish", "greek": "Greek", "grec": "Greek", "hebrew": "Hebrew",
    "hebreu": "Hebrew", "persian": "Persian", "farsi": "Persian", "persan": "Persian",
    "vietnamese": "Vietnamese", "vietnamien": "Vietnamese",
}  # fmt: skip
_LANGUAGE_RE = re.compile(r"\b(" + "|".join(_LANGUAGES) + r")\b")
_LEVEL_RE = re.compile(
    r"\b([abc][12]|native|natif|langue maternelle|mother tongue|bilingue|bilingual|fluent|courant|"
    r"professionnel|professional|advanced|avance|intermediate|intermediaire|beginner|debutant|"
    r"basic|elementaire|notions|scolaire)\b"
)


def extract_languages(lines: list[Line]) -> list[LanguageItem]:
    """Langues citées dans la section « Langues » uniquement (ailleurs, « English teacher »
    ne signifie pas que le candidat parle anglais)."""
    items: dict[str, LanguageItem] = {}
    for text in _texts(lines, "languages"):
        folded = fold(text)
        matches = list(_LANGUAGE_RE.finditer(folded))
        for position, match in enumerate(matches):
            end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
            level_match = _LEVEL_RE.search(folded, match.end(), end)
            name = _LANGUAGES[match.group(1)]
            if name not in items:
                items[name] = LanguageItem(
                    language=name,
                    level=text[level_match.start() : level_match.end()] if level_match else None,
                    provenance=Provenance(section="languages", snippet=_snippet(text)),
                )
    return list(items.values())


# ============================================================ certifications


def extract_certifications(lines: list[Line]) -> list[CertificationItem]:
    items = []
    for text in _texts(lines, "certifications"):
        name = re.sub(r"^- ", "", text).strip(_TRIM)
        if name:
            items.append(
                CertificationItem(
                    name=name[:200],
                    provenance=Provenance(section="certifications", snippet=_snippet(text)),
                )
            )
    return items[:30]

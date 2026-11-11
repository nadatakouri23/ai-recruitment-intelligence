"""Niveau d'études, exprimé en années après le baccalauréat (« Bac+5 » = 5).

Sert à comparer le diplôme d'un candidat à celui demandé par une offre. Seul le NIVEAU est utilisé,
jamais l'établissement (le prestige d'une école est un proxy de milieu social).
"""

import re

from app.modules.candidates.parsing.text_cleaning import fold

DOCTORATE = 8


def _compile(rows: tuple[tuple[str, int], ...]) -> tuple[tuple[re.Pattern[str], int], ...]:
    return tuple((re.compile(pattern), level) for pattern, level in rows)


# Motifs sur texte « plié » (minuscules, sans accents) ; on retient le niveau le plus élevé trouvé.
_COMMON = _compile(
    (
        (r"\b(phd|ph\.d|doctorat|doctorate|doctoral)\b", DOCTORATE),
        (r"\b(master|msc|m\.sc|mba|mastere|ingenieur|engineering degree)\b", 5),
        (r"\b(licence|license|bachelor|bsc|b\.sc)\b", 3),
        (r"\b(bts|dut|deug|associate degree)\b", 2),
    )
)
# Mots ambigus (« BA » = Business Analyst, « ma » = mon, « maîtrise » = savoir-faire) : uniquement
# dans le champ « diplôme » d'un CV, jamais dans le texte libre d'une offre.
_DEGREE_FIELD_ONLY = _compile(
    (
        (r"\bmaitrise\b", 4),
        (r"\b(ma|m\.a)\b", 5),
        (r"\b(ba|b\.a|bs|b\.s)\b", 3),
        (r"\b(baccalaureat|bac)\b", 0),
    )
)
_BAC_PLUS = re.compile(r"\bbac\s*\+\s*(\d)\b")

LABELS = {
    0: "Bac",
    2: "Bac+2",
    3: "Bac+3 (licence)",
    4: "Bac+4",
    5: "Bac+5 (master)",
    DOCTORATE: "Doctorat",
}


def label(level: int) -> str:
    return LABELS.get(level, f"Bac+{level}")


def education_level(degree_text: str) -> int | None:
    """Niveau le plus élevé du champ « diplôme » d'un CV, ou None si aucun n'est reconnu."""
    folded = fold(degree_text)
    levels = [int(m.group(1)) for m in _BAC_PLUS.finditer(folded)]
    levels += [lvl for pattern, lvl in (*_COMMON, *_DEGREE_FIELD_ONLY) if pattern.search(folded)]
    return max(levels) if levels else None


def required_level(job_text: str) -> int | None:
    """Niveau MINIMAL accepté par une offre : « Bac+3 à Bac+5 » -> 3, « Master ou ingénieur » -> 5.

    Seuls les motifs non ambigus sont utilisés dans le texte libre d'une offre.
    """
    folded = fold(job_text)
    levels = [int(m.group(1)) for m in _BAC_PLUS.finditer(folded)]
    levels += [lvl for pattern, lvl in _COMMON if pattern.search(folded)]
    return min(levels) if levels else None

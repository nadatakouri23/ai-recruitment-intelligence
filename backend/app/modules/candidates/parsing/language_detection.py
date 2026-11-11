"""Détection française / anglaise par comptage de mots grammaticaux courants."""

import re

from app.modules.candidates.parsing.text_cleaning import fold
from app.modules.candidates.profile import DetectedLanguage

_FR = frozenset(
    "le la les de des du et un une pour avec dans en au aux sur par est ans chez mon ma mes "
    "ses son sa qui que ou nous vous je il elle et".split()
)
_EN = frozenset(
    "the and of to in for with a an on by is at years my our their which that or as from "
    "have has was were be been".split()
)


def detect_language(text: str) -> DetectedLanguage:
    """ "fr", "en" ou "unknown" (texte trop court ou ambigu)."""
    words = re.findall(r"[a-z']+", fold(text))
    fr = sum(1 for w in words if w in _FR)
    en = sum(1 for w in words if w in _EN)
    if fr + en < 5:
        return "unknown"
    if fr > en * 1.3:
        return "fr"
    if en > fr * 1.3:
        return "en"
    return "unknown"

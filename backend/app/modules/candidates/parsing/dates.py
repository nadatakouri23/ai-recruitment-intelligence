"""Lecture des périodes (« Jan 2020 - Mars 2022 », « 2018-2020 », « 03/2019 - présent »…)."""

import re
from dataclasses import dataclass
from datetime import date

from app.modules.candidates.parsing.text_cleaning import fold

_MONTHS: dict[str, int] = {
    # anglais
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    # français (sans accents : le texte est « plié » avant la recherche)
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    "janv": 1, "fev": 2, "fevr": 2, "avr": 4, "juil": 7,
}  # fmt: skip

_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))


def _date_pattern(prefix: str) -> str:
    """Une date : « mars 2020 », « 2020 » ou « 03/2020 »."""
    return (
        rf"(?:(?:(?P<{prefix}mo>{_MONTH_RE})\.?\s+)?(?P<{prefix}y>(?:19|20)\d{{2}})"
        rf"|(?P<{prefix}nm>0?[1-9]|1[0-2])\s*[/.\-]\s*(?P<{prefix}ny>(?:19|20)\d{{2}}))"
    )


_SEPARATOR = r"\s*(?:[-–—]|->|→|\bto\b|\bau\b|\ba\b|\buntil\b|jusqu'?a|jusqu'?au)\s*"
_PRESENT = (
    r"(?P<present>present|presente|currently|current|now|today|ongoing|aujourd'?hui|"
    r"en cours|actuellement|actuel|a ce jour|ce jour|to date)"
)
_RANGE = re.compile(
    rf"(?<!\d){_date_pattern('s')}{_SEPARATOR}(?:{_date_pattern('e')}|{_PRESENT})(?!\d)"
)
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")


@dataclass(frozen=True)
class DateRange:
    start_year: int
    start_month: int | None
    end_year: int | None
    end_month: int | None
    is_current: bool
    span: tuple[int, int]  # position de la période dans la ligne d'origine


def _month_of(match: re.Match[str], prefix: str) -> int | None:
    word = match.group(f"{prefix}mo")
    if word:
        return _MONTHS[word]
    numeric = match.group(f"{prefix}nm")
    return int(numeric) if numeric else None


def find_date_range(line: str) -> DateRange | None:
    """Trouve la première période de la ligne, ou None."""
    match = _RANGE.search(fold(line))
    if match is None:
        return None
    start_year = int(match.group("sy") or match.group("sny"))
    is_current = match.group("present") is not None
    end_year = None
    if not is_current:
        end_year = int(match.group("ey") or match.group("eny"))
    return DateRange(
        start_year=start_year,
        start_month=_month_of(match, "s"),
        end_year=end_year,
        end_month=None if is_current else _month_of(match, "e"),
        is_current=is_current,
        span=match.span(),
    )


def find_years(line: str) -> list[int]:
    return [int(year) for year in _YEAR.findall(line)]


def month_interval(period: DateRange, today: date) -> tuple[int, int] | None:
    """Intervalle en « numéro de mois absolu » (année*12 + mois), ou None s'il est incohérent.

    Quand le mois manque, on prend janvier pour le début et décembre pour la fin : c'est une
    DÉDUCTION, signalée comme telle dans le profil.
    """
    start = period.start_year * 12 + (period.start_month or 1)
    if period.is_current:
        end = today.year * 12 + today.month
    else:
        assert period.end_year is not None
        end = period.end_year * 12 + (period.end_month or 12)
    if end < start:
        return None
    return start, end


def interval_of(
    start: str | None, end: str | None, is_current: bool, today: date
) -> tuple[int, int] | None:
    """Intervalle en mois d'une expérience, reconstitué depuis ses dates « AAAA » / « AAAA-MM »."""
    if not start or (not is_current and not end):
        return None
    start_year, _, start_month = start.partition("-")
    end_year, _, end_month = (end or "").partition("-")
    period = DateRange(
        start_year=int(start_year),
        start_month=int(start_month) if start_month else None,
        end_year=int(end_year) if end_year else None,
        end_month=int(end_month) if end_month else None,
        is_current=is_current,
        span=(0, 0),
    )
    return month_interval(period, today)


def merged_months(intervals: list[tuple[int, int]]) -> int:
    """Total de mois couverts, les chevauchements n'étant comptés qu'une fois."""
    total = 0
    current_start: int | None = None
    current_end = 0
    for start, end in sorted(intervals):
        if current_start is None or start > current_end + 1:
            if current_start is not None:
                total += current_end - current_start + 1
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_start is not None:
        total += current_end - current_start + 1
    return total


def format_date(year: int | None, month: int | None) -> str | None:
    if year is None:
        return None
    return f"{year}-{month:02d}" if month else str(year)

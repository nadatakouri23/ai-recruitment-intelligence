"""Protection des données envoyées au fournisseur, et vérification de ce qui revient.

- `redact` : retire adresses e-mail, numéros de téléphone et liens (minimisation des données).
- `wrap_document` : place le texte entre balises en neutralisant toute balise forgée dedans.
- `is_grounded` : une affirmation n'est acceptée que si sa citation figure TEXTUELLEMENT dans le
  document envoyé. C'est la défense principale contre l'invention (hallucination) : un modèle peut
  mentir, il ne peut pas faire apparaître dans le document une phrase qui n'y est pas.
"""

import re

from app.modules.candidates.parsing.text_cleaning import fold

_EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.\w{2,}")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b(?:linkedin|github|gitlab)\.com/\S*", re.IGNORECASE)
_PHONE = re.compile(r"(?<![\w+])(?:\+|00)?\d[\d ().-]{7,}\d(?!\w)")
_DOC_TAG = re.compile(r"<\s*(/?)\s*document\b[^>]*>", re.IGNORECASE)
_SPACES = re.compile(r"\s+")

MIN_QUOTE_CHARS = 3


def redact(text: str) -> str:
    text = _EMAIL.sub("[adresse e-mail]", text)
    text = _URL.sub("[lien]", text)
    return _PHONE.sub(
        lambda m: "[téléphone]" if len(re.sub(r"\D", "", m.group(0))) >= 9 else m.group(0), text
    )


def wrap_document(text: str) -> str:
    """Délimite le texte non fiable. Une balise <document> forgée dans le texte est neutralisée :
    il ne peut pas « fermer » le bloc pour faire passer ses instructions pour des consignes."""
    safe = _DOC_TAG.sub(lambda m: f"[balise {'fermante ' if m.group(1) else ''}retirée]", text)
    return f"<document>\n{safe}\n</document>"


def normalize(text: str) -> str:
    return _SPACES.sub(" ", fold(text)).strip()


def is_grounded(quote: str, source: str) -> bool:
    """La citation est une sous-chaîne du document (sans tenir compte des accents, de la casse ni
    des espaces). Trop courte (< 3 caractères) : refusée, car elle prouverait n'importe quoi."""
    needle = normalize(quote)
    return len(needle) >= MIN_QUOTE_CHARS and needle in normalize(source)


def contains_word(text: str, word: str) -> bool:
    return (
        re.search(rf"(?<![\w+#.]){re.escape(normalize(word))}(?![\w+#])", normalize(text))
        is not None
    )

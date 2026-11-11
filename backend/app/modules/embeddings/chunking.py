"""Découpage d'un CV en passages courts, pour les embeddings et la recherche.

Pourquoi découper : un modèle d'embedding ne lit que ~128 mots et dilue le sens d'un long texte ;
un passage court cible un fait précis (« 3 ans de Python chez X »). On découpe par section, avec
un recouvrement d'une ligne pour ne pas couper une idée en deux.

Équité : seuls les passages des sections liées au poste sont produits (jamais l'en-tête, les langues
parlées ni les centres d'intérêt), comme pour le matching.
"""

from dataclasses import dataclass

from app.modules.candidates.parsing.sections import split_sections
from app.modules.candidates.parsing.text_cleaning import clean_text

# Le modèle retenu lit au plus 128 « tokens » (≈ 80 mots) : on reste en dessous.
MAX_WORDS = 70
ALLOWED_SECTIONS = {"summary", "experience", "education", "skills", "projects", "certifications"}


@dataclass(frozen=True)
class Chunk:
    position: int
    section: str
    text: str


def chunk_cv(extracted_text: str, max_words: int = MAX_WORDS) -> list[Chunk]:
    lines, _ = split_sections(clean_text(extracted_text))
    chunks: list[Chunk] = []
    current: list[str] = []
    words = 0
    section = ""

    def flush() -> None:
        if current:
            chunks.append(Chunk(len(chunks), section, "\n".join(current)))

    for line in lines:
        if line.section not in ALLOWED_SECTIONS or not line.text:
            continue
        line_words = len(line.text.split())
        if line.section != section or (current and words + line_words > max_words):
            flush()
            # Recouvrement d'une ligne dans une même section, si elle est courte.
            overlap = (
                [current[-1]]
                if current and line.section == section and len(current[-1].split()) < 20
                else []
            )
            current = overlap
            words = sum(len(t.split()) for t in current)
            section = line.section
        current.append(line.text)
        words += line_words
    flush()
    return chunks

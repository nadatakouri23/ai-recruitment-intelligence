"""Nettoyage du texte extrait d'un PDF / DOCX."""

import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Puces usuelles (y compris le tiret en début de ligne) suivies d'un espace.
_BULLET = re.compile(r"^[•▪●◦■□▫‣∙·►➢✓✔*\-–—]\s+")
# Certains PDF exposent les glyphes sans table de correspondance : une puce devient « (cid:127) ».
_CID_LEADING = re.compile(r"^\s*(?:\(cid:\d+\)\s*)+")
_CID_ANYWHERE = re.compile(r"\(cid:\d+\)")


def clean_text(raw: str) -> str:
    """Normalise le texte : Unicode, puces, espaces, lignes vides. Idempotent."""
    text = unicodedata.normalize("NFKC", raw).translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = _CONTROL.sub("", text)

    cleaned: list[str] = []
    previous_blank = True  # supprime les lignes vides en tête
    for line in text.split("\n"):
        line = _CID_LEADING.sub("- ", line)  # « (cid:127) Texte » = une puce
        line = _CID_ANYWHERE.sub(" ", line)
        line = re.sub(r" {2,}", " ", line).strip()
        line = _BULLET.sub("- ", line)
        if not line:
            if not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(line)
        previous_blank = False
    return "\n".join(cleaned).strip()


def fold(text: str) -> str:
    """Minuscules sans accents, en conservant la LONGUEUR du texte.

    Cela permet de chercher dans la version « pliée » et de retrouver les positions dans
    le texte d'origine (pour les extraits).
    """
    out: list[str] = []
    for char in text:
        base = "".join(
            c for c in unicodedata.normalize("NFD", char) if not unicodedata.combining(c)
        )
        lowered = base.lower()
        out.append(lowered if len(lowered) == 1 else char)
    return "".join(out)

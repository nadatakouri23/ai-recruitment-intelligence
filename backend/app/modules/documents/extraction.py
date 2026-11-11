"""Validation d'un fichier uploadé et extraction de son texte (PDF / DOCX).

Le contenu d'un fichier uploadé est NON FIABLE : on vérifie sa taille, son extension ET sa
signature réelle (les premiers octets), jamais le type annoncé par le client.
"""

import io
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

import pdfplumber
import structlog
from docx import Document as load_docx
from docx.table import Table
from docx.text.paragraph import Paragraph

log = structlog.get_logger()

# Un DOCX est une archive ZIP : on limite sa taille décompressée (protection « zip bomb »).
_MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024
_MIN_TEXT_CHARS = 50


class DocumentKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class InvalidUploadError(Exception):
    """Fichier refusé. Le message est destiné à l'utilisateur (aucun détail interne)."""


class FileTooLargeError(InvalidUploadError):
    """Fichier au-delà de la taille maximale (HTTP 413)."""


class NoExtractableTextError(InvalidUploadError):
    """Le fichier est valide mais ne contient pas de texte exploitable (ex. PDF scanné)."""


@dataclass(frozen=True)
class ExtractedDocument:
    kind: DocumentKind
    text: str
    page_count: int | None


def display_filename(filename: str | None) -> str:
    """Nom d'affichage sûr : sans dossier, sans caractères de contrôle, 255 caractères max.

    Ce nom n'est utilisé que pour l'affichage, jamais pour écrire sur le disque.
    """
    name = PurePath((filename or "").replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return (name or "document")[:255]


def detect_kind(filename: str | None, content: bytes, max_bytes: int) -> DocumentKind:
    """Valide taille, extension et signature ; retourne le type de document."""
    if not content:
        raise InvalidUploadError("Le fichier est vide.")
    if len(content) > max_bytes:
        raise FileTooLargeError(
            f"Le fichier dépasse la taille maximale autorisée ({max_bytes // (1024 * 1024)} Mo)."
        )

    extension = PurePath(filename or "").suffix.lower()
    if extension not in (".pdf", ".docx"):
        raise InvalidUploadError(
            "Format non pris en charge : seuls les fichiers PDF et DOCX sont acceptés."
        )

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise InvalidUploadError("Le contenu du fichier ne correspond pas à un PDF.")
        return DocumentKind.PDF

    if not _is_docx(content):
        raise InvalidUploadError(
            "Le contenu du fichier ne correspond pas à un document DOCX valide."
        )
    return DocumentKind.DOCX


def _is_docx(content: bytes) -> bool:
    if not content.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                return False
            return sum(info.file_size for info in archive.infolist()) <= _MAX_DOCX_UNCOMPRESSED
    except zipfile.BadZipFile:
        return False


def extract_text(content: bytes, kind: DocumentKind, max_pages: int) -> ExtractedDocument:
    """Extrait le texte brut. Lève InvalidUploadError si le fichier est illisible."""
    if kind is DocumentKind.PDF:
        text, pages = _extract_pdf(content, max_pages)
    else:
        text, pages = _extract_docx(content), None

    if len(text.strip()) < _MIN_TEXT_CHARS:
        raise NoExtractableTextError(
            "Aucun texte exploitable dans ce fichier (PDF scanné ou image ?). "
            "La reconnaissance de caractères (OCR) n'est pas disponible."
        )
    return ExtractedDocument(kind=kind, text=text, page_count=pages)


def _extract_pdf(content: bytes, max_pages: int) -> tuple[str, int]:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            total_pages = len(pdf.pages)
            if total_pages > max_pages:
                raise InvalidUploadError(
                    f"Le PDF contient trop de pages ({total_pages}, maximum {max_pages})."
                )
            texts = [page.extract_text() or "" for page in pdf.pages]
    except InvalidUploadError:
        raise
    except Exception as exc:  # noqa: BLE001 - bibliothèque tierce : erreurs de types variés
        # Fichier corrompu, chiffré par mot de passe, etc. On journalise le type d'erreur
        # (jamais le contenu) et on renvoie un message neutre à l'utilisateur.
        log.warning("pdf_extraction_failed", error_type=type(exc).__name__)
        raise InvalidUploadError(
            "Impossible de lire ce PDF (fichier corrompu ou protégé)."
        ) from exc
    return "\n\n".join(texts), total_pages


def _extract_docx(content: bytes) -> str:
    try:
        document = load_docx(io.BytesIO(content))
        lines: list[str] = []
        # On parcourt le corps dans l'ordre : paragraphes ET tableaux (fréquents dans les CV).
        for child in document.element.body.iterchildren():
            if child.tag.endswith("}p"):
                lines.append(Paragraph(child, document).text)
            elif child.tag.endswith("}tbl"):
                for row in Table(child, document).rows:
                    seen: set[int] = set()
                    for cell in row.cells:
                        if id(cell._tc) in seen:  # cellules fusionnées : ne pas répéter
                            continue
                        seen.add(id(cell._tc))
                        lines.extend(p.text for p in cell.paragraphs)
    except Exception as exc:  # noqa: BLE001 - bibliothèque tierce
        log.warning("docx_extraction_failed", error_type=type(exc).__name__)
        raise InvalidUploadError("Impossible de lire ce document DOCX.") from exc
    return "\n".join(lines)

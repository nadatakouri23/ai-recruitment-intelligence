"""Validation et extraction des fichiers : le contenu uploadé est traité comme hostile."""

import io
import zipfile

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from app.modules.documents.extraction import (
    DocumentKind,
    FileTooLargeError,
    InvalidUploadError,
    NoExtractableTextError,
    detect_kind,
    display_filename,
    extract_text,
)
from tests.cv_factory import SYNTHETIC_CVS, blank_pdf, render

MAX_BYTES = 1024 * 1024
PDF_CV = next(c for c in SYNTHETIC_CVS if c.fmt == "pdf")
DOCX_CV = next(c for c in SYNTHETIC_CVS if c.fmt == "docx")


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _pdf_with_pages(pages: int) -> bytes:
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    for number in range(pages):
        canvas.drawString(72, 700, f"Page {number + 1} avec assez de texte pour être extraite " * 2)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


# ------------------------------------------------------------------ détection du type


def test_valid_files_are_detected() -> None:
    assert detect_kind("cv.pdf", render(PDF_CV), MAX_BYTES) is DocumentKind.PDF
    assert detect_kind("CV.DOCX", render(DOCX_CV), MAX_BYTES) is DocumentKind.DOCX


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("cv.pdf", b"", "vide"),
        ("cv.txt", b"Du texte simple", "Format non pris en charge"),
        ("cv.exe", b"MZ\x90\x00", "Format non pris en charge"),
        ("cv", b"%PDF-1.4", "Format non pris en charge"),
        (None, b"%PDF-1.4", "Format non pris en charge"),
        ("cv.pdf", b"PK\x03\x04 ceci est un zip", "ne correspond pas à un PDF"),
        ("cv.docx", b"%PDF-1.4 ceci est un pdf", "ne correspond pas"),
        ("cv.docx", b"PK\x03\x04 pas vraiment un zip", "ne correspond pas"),
    ],
)
def test_wrong_extension_or_signature_is_rejected(
    filename: str | None, content: bytes, message: str
) -> None:
    with pytest.raises(InvalidUploadError, match=message):
        detect_kind(filename, content, MAX_BYTES)


def test_renamed_zip_without_word_document_is_not_a_docx() -> None:
    not_docx = _zip({"hello.txt": b"salut"})

    with pytest.raises(InvalidUploadError):
        detect_kind("cv.docx", not_docx, MAX_BYTES)


def test_oversized_file_is_rejected_with_a_specific_error() -> None:
    with pytest.raises(FileTooLargeError):
        detect_kind("cv.pdf", b"%PDF-" + b"0" * MAX_BYTES, MAX_BYTES)


def test_zip_bomb_docx_is_rejected() -> None:
    # ~60 Mo décompressés mais quelques dizaines de Ko compressés.
    bomb = _zip(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"0" * (60 * 1024 * 1024),
        }
    )
    assert len(bomb) < MAX_BYTES

    with pytest.raises(InvalidUploadError):
        detect_kind("cv.docx", bomb, MAX_BYTES)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\bob\\cv.pdf", "cv.pdf"),
        ("cv\x00.pdf", "cv.pdf"),
        ("", "document"),
        (None, "document"),
        ("a" * 400 + ".pdf", ("a" * 400 + ".pdf")[:255]),
    ],
)
def test_display_filename_is_sanitized(given: str | None, expected: str) -> None:
    assert display_filename(given) == expected


# ------------------------------------------------------------------ extraction


def test_pdf_text_is_extracted() -> None:
    content = render(PDF_CV)

    result = extract_text(content, DocumentKind.PDF, max_pages=10)

    assert PDF_CV.name in result.text
    assert PDF_CV.email in result.text
    assert result.page_count == 1


def test_docx_text_is_extracted() -> None:
    content = render(DOCX_CV)

    result = extract_text(content, DocumentKind.DOCX, max_pages=10)

    assert DOCX_CV.name in result.text
    assert result.page_count is None


def test_pdf_without_text_is_reported_as_unreadable_not_empty_profile() -> None:
    with pytest.raises(NoExtractableTextError, match="OCR"):
        extract_text(blank_pdf(), DocumentKind.PDF, max_pages=10)


def test_pdf_with_too_many_pages_is_rejected() -> None:
    with pytest.raises(InvalidUploadError, match="trop de pages"):
        extract_text(_pdf_with_pages(4), DocumentKind.PDF, max_pages=3)


def test_corrupted_pdf_gives_a_clean_error() -> None:
    with pytest.raises(InvalidUploadError, match="Impossible de lire"):
        extract_text(b"%PDF-1.4\nceci est du bruit \x00\x01 sans structure", DocumentKind.PDF, 10)


def test_corrupted_docx_gives_a_clean_error() -> None:
    broken = _zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<<<pas du xml"})

    with pytest.raises(InvalidUploadError):
        extract_text(broken, DocumentKind.DOCX, 10)

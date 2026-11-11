"""Règles métier : import d'un CV, consultation, suppression."""

import hashlib

import structlog
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.modules.candidates.models import Candidate
from app.modules.candidates.parsing.parser import parse_cv
from app.modules.candidates.parsing.skills import canonical_skill_name
from app.modules.candidates.parsing.text_cleaning import clean_text
from app.modules.candidates.repository import CandidateRepository
from app.modules.documents.extraction import detect_kind, display_filename, extract_text
from app.modules.documents.models import Document
from app.modules.documents.storage import FileStorage
from app.modules.embeddings.service import IndexingService

log = structlog.get_logger()


class CandidateNotFoundError(Exception):
    pass


class DuplicateCVError(Exception):
    def __init__(self, candidate_id: int | None) -> None:
        super().__init__("CV déjà importé")
        self.candidate_id = candidate_id


class CandidateService:
    def __init__(
        self,
        repository: CandidateRepository,
        storage: FileStorage,
        settings: Settings,
        indexer: IndexingService | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._settings = settings
        self._indexer = indexer

    @property
    def max_upload_bytes(self) -> int:
        return self._settings.max_upload_size_mb * 1024 * 1024

    def import_cv(self, owner_id: int, filename: str | None, content: bytes) -> Candidate:
        """Valide, lit, analyse et enregistre un CV. Lève InvalidUploadError / DuplicateCVError."""
        kind = detect_kind(filename, content, self.max_upload_bytes)
        digest = hashlib.sha256(content).hexdigest()

        existing = self._repository.find_by_hash(owner_id, digest)
        if existing is not None:
            raise DuplicateCVError(existing.id)

        extracted = extract_text(content, kind, self._settings.max_pdf_pages)
        text = clean_text(extracted.text)
        profile = parse_cv(text)

        storage_name = self._storage.save(content, kind.value)
        candidate = Candidate(
            owner_id=owner_id,
            full_name=profile.full_name,
            email=profile.email,
            profile=profile.model_dump(mode="json"),
            parser_version=profile.report.parser_version,
            document=Document(
                owner_id=owner_id,
                kind=kind.value,
                original_filename=display_filename(filename),
                storage_name=storage_name,
                size_bytes=len(content),
                sha256=digest,
                page_count=extracted.page_count,
                extracted_text=text,
            ),
        )
        try:
            self._repository.add(candidate)
        except IntegrityError as exc:  # deux imports simultanés du même fichier
            self._storage.delete(storage_name)
            raise DuplicateCVError(None) from exc
        except Exception:
            self._storage.delete(storage_name)  # pas de fichier orphelin si la base échoue
            raise

        self._index(candidate)

        # Jamais de nom, d'e-mail ni de nom de fichier dans les logs : des identifiants seulement.
        log.info(
            "cv_imported",
            candidate_id=candidate.id,
            owner_id=owner_id,
            kind=kind.value,
            size_bytes=len(content),
            page_count=extracted.page_count,
            completeness=profile.report.extraction_completeness,
        )
        return candidate

    def _index(self, candidate: Candidate) -> None:
        """Indexation pour la recherche : best-effort. Un échec n'annule JAMAIS l'import du CV
        (il est journalisé, visible dans /search/status, et rattrapable par /search/reindex)."""
        if self._indexer is None:
            return
        try:
            self._indexer.index_candidate(candidate)
        except Exception as exc:  # noqa: BLE001 - tout échec d'indexation est non bloquant
            log.error("indexing_failed", candidate_id=candidate.id, error=type(exc).__name__)

    def get(self, owner_id: int, candidate_id: int) -> Candidate:
        candidate = self._repository.get(owner_id, candidate_id)
        if candidate is None:
            # Même réponse pour « n'existe pas » et « appartient à un autre » : pas de fuite.
            raise CandidateNotFoundError
        return candidate

    def list(
        self,
        owner_id: int,
        *,
        name_query: str | None,
        skill: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Candidate], int]:
        if skill:
            # « python », « apprentissage automatique », « ML » → nom canonique du référentiel.
            skill = canonical_skill_name(skill) or skill.strip()
        return self._repository.list(
            owner_id, name_query=name_query or None, skill=skill, limit=limit, offset=offset
        )

    def delete(self, owner_id: int, candidate_id: int) -> None:
        candidate = self.get(owner_id, candidate_id)
        storage_name = candidate.document.storage_name
        self._repository.delete(candidate)
        self._storage.delete(storage_name)
        log.info("candidate_deleted", candidate_id=candidate_id, owner_id=owner_id)

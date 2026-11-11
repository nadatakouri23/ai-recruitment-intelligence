"""Schémas de l'API de recherche."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.matching.schemas import CandidateRef

SearchMode = Literal["auto", "keyword", "semantic", "hybrid"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    # auto : hybride si les embeddings sont activés, sinon mots-clés.
    mode: SearchMode = "auto"
    limit: int = Field(default=10, ge=1, le=50)
    # Restreint aux candidats ayant cette compétence (FR ou EN : « apprentissage automatique »…).
    skill: str | None = Field(default=None, max_length=60)
    anonymize: bool = False

    @field_validator("query")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("La requête est trop courte.")
        return value


class Passage(BaseModel):
    section: str
    text: str


class SearchHit(BaseModel):
    candidate: CandidateRef
    # 0 à 1. Sens selon le mode : TF-IDF (mots-clés), cosinus (sémantique), rang fusionné (hybride).
    score: float
    # Le passage du CV qui justifie ce résultat.
    best_passage: Passage
    keyword_rank: int | None = None
    semantic_rank: int | None = None


class SearchResponse(BaseModel):
    mode_used: Literal["keyword", "semantic", "hybrid"]
    results: list[SearchHit]
    # Candidats sans vecteur à jour : invisibles à la recherche sémantique avant réindexation.
    unindexed_candidates: int
    note: str


class IndexStatus(BaseModel):
    provider: str
    model: str | None
    semantic_enabled: bool
    candidates: int
    chunks: int
    vectors: int
    candidates_needing_index: int


class ReindexReport(BaseModel):
    candidates_processed: int
    chunks: int
    with_vectors: int

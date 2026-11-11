"""Poids des composantes du score de matching (configurables)."""

from pydantic import BaseModel, Field, model_validator


class MatchingWeights(BaseModel):
    """Poids RELATIFS : seuls les rapports comptent (ils sont normalisés à la somme 1).

    Un poids à 0 désactive la composante dans le score (elle reste affichée à titre indicatif).
    """

    skills: float = Field(default=0.45, ge=0, le=100)
    experience: float = Field(default=0.20, ge=0, le=100)
    tfidf: float = Field(default=0.20, ge=0, le=100)
    keyword: float = Field(default=0.10, ge=0, le=100)
    education: float = Field(default=0.05, ge=0, le=100)
    # Similarité par le sens (embeddings). 0 par défaut : à n'activer que si une évaluation montre
    # un gain (voir docs/evaluation/semantic.md). Ignorée si les embeddings sont désactivés.
    semantic: float = Field(default=0.0, ge=0, le=100)

    @model_validator(mode="after")
    def _at_least_one_positive(self) -> "MatchingWeights":
        if self.total() <= 0:
            raise ValueError("Au moins un poids doit être strictement positif.")
        return self

    def total(self) -> float:
        return (
            self.skills
            + self.experience
            + self.tfidf
            + self.keyword
            + self.education
            + self.semantic
        )

    def normalized(self) -> "MatchingWeights":
        """Même rapport entre les poids, somme égale à 1."""
        total = self.total()
        return MatchingWeights(
            **{name: round(value / total, 6) for name, value in self.model_dump().items()}
        )

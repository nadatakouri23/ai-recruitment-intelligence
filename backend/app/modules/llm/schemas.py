"""Schémas : sorties BRUTES attendues du modèle, et résultats VÉRIFIÉS renvoyés par l'API."""

from pydantic import BaseModel, Field, field_validator


class ExternalProcessingConsent(BaseModel):
    """Chaque appel envoie du texte à un service externe : consentement exigé à chaque fois."""

    # OBLIGATOIRE, sans valeur par défaut : Pydantic ne valide pas les valeurs par défaut, donc un
    # corps vide `{}` aurait passé la vérification ci-dessous (défaut trouvé par les tests).
    confirm_external_processing: bool

    @field_validator("confirm_external_processing")
    @classmethod
    def _must_be_true(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "Confirmez explicitement l'envoi du texte (anonymisé) à un fournisseur LLM externe "
                "avec confirm_external_processing=true."
            )
        return value


# ------------------------------------------------------------------ sorties brutes du modèle


class RawSkill(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    quote: str = Field(default="", max_length=300)


class RawExperience(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=120)
    period: str | None = Field(default=None, max_length=80)
    quote: str = Field(default="", max_length=300)


class RawEducation(BaseModel):
    degree: str | None = Field(default=None, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    quote: str = Field(default="", max_length=300)


class RawCVExtraction(BaseModel):
    skills: list[RawSkill] = Field(default_factory=list, max_length=80)
    experience: list[RawExperience] = Field(default_factory=list, max_length=20)
    education: list[RawEducation] = Field(default_factory=list, max_length=10)


class RawKeyPoint(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    quote: str = Field(default="", max_length=300)


class RawSummary(BaseModel):
    summary: str = Field(default="", max_length=1500)
    key_points: list[RawKeyPoint] = Field(default_factory=list, max_length=8)


class RawJobAnalysis(BaseModel):
    required_skills: list[RawSkill] = Field(default_factory=list, max_length=60)
    optional_skills: list[RawSkill] = Field(default_factory=list, max_length=60)
    min_experience_years: int | None = Field(default=None, ge=0, le=40)
    experience_quote: str = Field(default="", max_length=300)
    responsibilities: list[RawKeyPoint] = Field(default_factory=list, max_length=10)


class RawExplanation(BaseModel):
    explanation: str = Field(default="", max_length=2000)
    caveats: list[str] = Field(default_factory=list, max_length=5)


# ------------------------------------------------------------------ résultats vérifiés


class CallInfo(BaseModel):
    provider: str
    model: str
    input_chars: int
    truncated: bool  # le texte a dû être raccourci avant l'envoi
    note: str = (
        "Texte anonymisé (sans nom, contacts ni liens) envoyé à un fournisseur externe. Chaque "
        "affirmation ci-dessous a été vérifiée contre le document ; celles qui ne l'étaient pas "
        "ont été écartées."
    )


class GroundedSkill(BaseModel):
    name: str
    canonical: str | None  # nom du référentiel, ou None si la compétence n'y figure pas
    quote: str


class GroundedExperience(BaseModel):
    title: str | None
    company: str | None
    period: str | None
    quote: str


class GroundedEducation(BaseModel):
    degree: str | None
    institution: str | None
    quote: str


class SkillComparison(BaseModel):
    """Accord entre l'extraction par le LLM et l'extraction par règles (noms du référentiel)."""

    both: list[str]
    only_llm: list[str]
    only_rules: list[str]


class DroppedCounts(BaseModel):
    skills: int = 0
    experience: int = 0
    education: int = 0
    key_points: int = 0
    responsibilities: int = 0


class CVExtractionResult(BaseModel):
    call: CallInfo
    skills: list[GroundedSkill]
    experience: list[GroundedExperience]
    education: list[GroundedEducation]
    dropped: DroppedCounts
    comparison: SkillComparison


class KeyPoint(BaseModel):
    text: str
    quote: str


class SummaryResult(BaseModel):
    call: CallInfo
    summary: str | None
    # Renseigné quand le résumé est retenu : il citait une compétence absente du document.
    withheld_reason: str | None = None
    key_points: list[KeyPoint]
    dropped: DroppedCounts


class JobSuggestion(BaseModel):
    required_skills: list[str]
    optional_skills: list[str]
    unknown_skills: list[GroundedSkill]  # citées dans l'offre mais absentes du référentiel
    min_experience_years: int | None
    responsibilities: list[KeyPoint]


class JobAnalysisResult(BaseModel):
    call: CallInfo
    suggestion: JobSuggestion
    # Écarts avec l'analyse par règles actuellement enregistrée pour l'offre.
    differences: SkillComparison
    dropped: DroppedCounts
    applied: bool = False
    note: str = (
        "Suggestion NON appliquée : relisez-la, puis corrigez l'offre vous-même (PATCH /jobs/{id})."
    )


class ExplanationResult(BaseModel):
    call: CallInfo
    explanation: str | None
    withheld_reason: str | None = None
    caveats: list[str]


class LLMStatus(BaseModel):
    enabled: bool
    provider: str
    model: str | None
    note: str

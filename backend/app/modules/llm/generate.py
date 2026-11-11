"""Appel du modèle avec validation stricte de la sortie (JSON, puis schéma Pydantic)."""

import json
import re

import structlog
from pydantic import BaseModel, ValidationError

from app.modules.llm.errors import LLMOutputError
from app.modules.llm.providers import LLMProvider

log = structlog.get_logger()
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def generate[T: BaseModel](
    provider: LLMProvider,
    system: str,
    user: str,
    model_cls: type[T],
    *,
    max_output_tokens: int = 1500,
    attempts: int = 2,
) -> T:
    """Demande une sortie JSON conforme à `model_cls`. Réessaie une fois si elle est invalide.

    Les erreurs de validation ne sont pas relayées (elles citeraient la réponse du modèle, donc
    possiblement des extraits du CV).
    """
    for attempt in range(1, attempts + 1):
        raw = provider.complete_json(system, user, max_output_tokens=max_output_tokens)
        try:
            return model_cls.model_validate(json.loads(_FENCE.sub("", raw.strip())))
        except (ValueError, ValidationError):
            log.warning("llm_invalid_output", provider=provider.name, attempt=attempt)
    raise LLMOutputError(
        "La réponse du modèle n'est pas exploitable (JSON invalide ou non conforme)."
    )

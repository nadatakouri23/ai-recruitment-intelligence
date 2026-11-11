"""Fournisseurs LLM derrière une interface unique : Gemini, Mistral, Groq (+ faux de test).

Le code métier ne connaît que `LLMProvider.complete_json` : changer de fournisseur ne touche rien
d'autre. Les appels sont faits en HTTP direct (httpx), sans SDK, pour garder le contrôle de ce qui
est envoyé et de ce qui peut fuiter.

SÉCURITÉ DES CLÉS : la clé Gemini est transmise dans l'URL (paramètre `key`, d'après la
documentation). Une exception httpx contiendrait donc la clé. Toute erreur réseau est capturée et
réécrite SANS URL (`from None`) ; les corps de réponse d'erreur ne sont jamais relayés.

Formats vérifiés dans la documentation officielle le 2026-11-11 (voir ADR-006). Non vérifiés : le
format des erreurs 429 de Gemini et de Mistral, et les noms de modèles par défaut ci-dessous (à
confirmer et à surcharger avec LLM_MODEL).
"""

import time
from collections.abc import Callable
from typing import Protocol

import httpx
import structlog
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.llm.errors import LLMDisabledError, LLMProviderError

log = structlog.get_logger()

DEFAULT_MODELS = {
    "gemini": "gemini-3.1-flash-lite",  # testé en réel le 2026-11-11 ; « 3.8-flash » a expiré
    "mistral": "mistral-small-latest",  # id d'exemple de la documentation
    "groq": "openai/gpt-oss-20b",  # testé en réel le 2026-11-11
}
_MAX_ATTEMPTS = 3
_MAX_WAIT_SECONDS = 5.0


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str, *, max_output_tokens: int = 1024) -> str:
        """Retourne le texte brut de la réponse (censé être du JSON ; validé par l'appelant)."""
        ...


class _HttpProvider:
    name = ""

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._timeout = timeout
        self._transport = transport
        self._sleep = sleep

    def _post(
        self,
        url: str,
        body: dict,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                    response = client.post(url, json=body, headers=headers, params=params)
            except httpx.TimeoutException:
                raise LLMProviderError("Le fournisseur LLM n'a pas répondu à temps.") from None
            except httpx.HTTPError:
                # httpx met l'URL (donc la clé Gemini) dans ses messages : on ne les relaie pas.
                raise LLMProviderError(
                    "Erreur réseau lors de l'appel au fournisseur LLM."
                ) from None

            status = response.status_code
            if (status == 429 or status >= 500) and attempt < _MAX_ATTEMPTS:
                wait = _retry_after(response)
                log.warning("llm_retry", provider=self.name, status=status, attempt=attempt)
                self._sleep(min(wait, _MAX_WAIT_SECONDS))
                continue
            if status == 429:
                raise LLMProviderError("Quota du fournisseur LLM dépassé : réessayez plus tard.")
            if status in (401, 403):
                raise LLMProviderError("Clé API refusée par le fournisseur LLM.")
            if status >= 400:
                raise LLMProviderError(f"Le fournisseur LLM a refusé la requête (HTTP {status}).")
            try:
                payload = response.json()
            except ValueError:
                raise LLMProviderError("Réponse illisible du fournisseur LLM.") from None
            if not isinstance(payload, dict):
                raise LLMProviderError("Réponse inattendue du fournisseur LLM.")
            return payload
        raise LLMProviderError("Le fournisseur LLM est indisponible.")  # inatteignable


def _retry_after(response: httpx.Response) -> float:
    try:
        return max(0.0, float(response.headers.get("retry-after", "1")))
    except ValueError:
        return 1.0


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LLMProviderError("Réponse vide ou bloquée par le fournisseur LLM.")
    return value


class GeminiProvider(_HttpProvider):
    name = "gemini"

    def complete_json(self, system: str, user: str, *, max_output_tokens: int = 1024) -> str:
        payload = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": max_output_tokens,
                    "responseMimeType": "application/json",
                },
            },
            params={"key": self._api_key.get_secret_value()},
        )
        try:
            return _text(payload["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, TypeError):
            raise LLMProviderError("Réponse vide ou bloquée par le fournisseur LLM.") from None


class _OpenAICompatible(_HttpProvider):
    """Mistral et Groq : même forme de requête et de réponse (chat completions)."""

    url = ""
    max_tokens_field = "max_tokens"

    def complete_json(self, system: str, user: str, *, max_output_tokens: int = 1024) -> str:
        payload = self._post(
            self.url,
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                self.max_tokens_field: max_output_tokens,
            },
            headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
        )
        try:
            return _text(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise LLMProviderError("Réponse vide ou bloquée par le fournisseur LLM.") from None


class MistralProvider(_OpenAICompatible):
    name = "mistral"
    url = "https://api.mistral.ai/v1/chat/completions"
    max_tokens_field = "max_tokens"


class GroqProvider(_OpenAICompatible):
    name = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
    max_tokens_field = "max_completion_tokens"  # « max_tokens » est déprécié chez Groq


_CLASSES: dict[str, type[_HttpProvider]] = {
    "gemini": GeminiProvider,
    "mistral": MistralProvider,
    "groq": GroqProvider,
}
_KEY_SETTING = {"gemini": "gemini_api_key", "mistral": "mistral_api_key", "groq": "groq_api_key"}


def build_provider(
    settings: Settings,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> LLMProvider | None:
    """Le fournisseur configuré, ou None si la fonction est désactivée."""
    name = settings.llm_provider
    if name == "none":
        return None
    key: SecretStr | None = getattr(settings, _KEY_SETTING[name])
    if key is None or not key.get_secret_value().strip():
        raise LLMDisabledError(
            f"Fournisseur « {name} » choisi mais {_KEY_SETTING[name].upper()} est absente de .env."
        )
    return _CLASSES[name](
        key,
        settings.llm_model or DEFAULT_MODELS[name],
        float(settings.llm_timeout_seconds),
        transport,
        sleep,
    )

"""Fournisseurs LLM : forme des requêtes, lecture des réponses, erreurs, et surtout FUITE DE CLÉ.

Aucun appel réseau réel : un faux transport HTTP rejoue les réponses. Ces tests vérifient que notre
code construit les requêtes décrites dans la documentation officielle (consultée le 2026-11-11) ;
ils ne prouvent PAS que les services acceptent ces requêtes aujourd'hui (aucune clé disponible).
"""

import json

import httpx
import pytest

from app.core.config import Settings
from app.modules.llm.errors import LLMDisabledError, LLMProviderError
from app.modules.llm.providers import DEFAULT_MODELS, build_provider

SECRET = "sk-TEST-SECRET-9f8e7d6c5b4a"


def settings(provider: str, **extra) -> Settings:
    keys = {"gemini": "gemini_api_key", "mistral": "mistral_api_key", "groq": "groq_api_key"}
    return Settings(
        postgres_password="x",
        jwt_secret_key="y",
        llm_provider=provider,  # type: ignore[arg-type]
        **{keys[provider]: SECRET},
        **extra,
    )


def make(provider: str, handler, waits: list[float] | None = None, **extra):
    waits = waits if waits is not None else []
    return build_provider(
        settings(provider, **extra), transport=httpx.MockTransport(handler), sleep=waits.append
    )


def ok_openai(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})


def ok_gemini(request: httpx.Request) -> httpx.Response:
    body = {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}
    return httpx.Response(200, json=body)


# ------------------------------------------------------------------ configuration


def test_provider_none_disables_the_feature() -> None:
    assert build_provider(Settings(postgres_password="x", jwt_secret_key="y")) is None


def test_default_is_disabled() -> None:
    assert Settings(postgres_password="x", jwt_secret_key="y").llm_provider == "none"


@pytest.mark.parametrize("provider", ["gemini", "mistral", "groq"])
def test_missing_key_is_reported_by_variable_name_only(provider: str) -> None:
    config = Settings(postgres_password="x", jwt_secret_key="y", llm_provider=provider)  # type: ignore[arg-type]

    with pytest.raises(LLMDisabledError, match=f"{provider.upper()}_API_KEY"):
        build_provider(config)


def test_blank_key_counts_as_missing() -> None:
    config = Settings(
        postgres_password="x", jwt_secret_key="y", llm_provider="groq", groq_api_key="   "
    )

    with pytest.raises(LLMDisabledError):
        build_provider(config)


def test_keys_are_hidden_when_settings_are_printed() -> None:
    printed = (
        repr(settings("gemini")) + str(settings("gemini")) + settings("gemini").model_dump_json()
    )

    assert SECRET not in printed


def test_default_models_and_override() -> None:
    assert make("groq", ok_openai).model == DEFAULT_MODELS["groq"]
    assert (
        make("mistral", ok_openai, llm_model="mistral-large-latest").model == "mistral-large-latest"
    )


# ------------------------------------------------------------------ forme des requêtes


def test_gemini_request_matches_the_documented_format() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["headers"] = request.url, request.headers
        seen["body"] = json.loads(request.content)
        return ok_gemini(request)

    provider = make("gemini", handler, llm_model="gemini-test")

    assert json.loads(provider.complete_json("SYSTEME", "UTILISATEUR", max_output_tokens=321)) == {
        "ok": True
    }
    assert seen["url"].path == "/v1beta/models/gemini-test:generateContent"
    assert seen["url"].host == "generativelanguage.googleapis.com"
    assert seen["url"].params["key"] == SECRET  # d'après la documentation : clé en paramètre d'URL
    assert "authorization" not in seen["headers"]
    body = seen["body"]
    assert body["systemInstruction"] == {"parts": [{"text": "SYSTEME"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "UTILISATEUR"}]}]
    assert body["generationConfig"] == {
        "temperature": 0,
        "maxOutputTokens": 321,
        "responseMimeType": "application/json",
    }


def test_mistral_request_matches_the_documented_format() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["headers"], seen["body"] = (
            request.url,
            request.headers,
            json.loads(request.content),
        )
        return ok_openai(request)

    provider = make("mistral", handler)

    assert json.loads(provider.complete_json("S", "U", max_output_tokens=200)) == {"ok": True}
    assert str(seen["url"]) == "https://api.mistral.ai/v1/chat/completions"
    assert seen["headers"]["authorization"] == f"Bearer {SECRET}"
    assert SECRET not in str(seen["url"])  # ici la clé reste dans l'en-tête, pas dans l'URL
    assert seen["body"] == {
        "model": DEFAULT_MODELS["mistral"],
        "messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 200,
    }


def test_groq_request_uses_the_non_deprecated_token_field() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"] = request.url, json.loads(request.content)
        return ok_openai(request)

    make("groq", handler).complete_json("S", "U", max_output_tokens=150)

    assert str(seen["url"]) == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["body"]["max_completion_tokens"] == 150 and "max_tokens" not in seen["body"]
    assert seen["body"]["response_format"] == {"type": "json_object"}


# ------------------------------------------------------------------ lecture des réponses


@pytest.mark.parametrize(
    ("provider", "payload"),
    [
        ("gemini", {}),
        ("gemini", {"candidates": []}),
        ("gemini", {"candidates": [{"finishReason": "SAFETY"}]}),
        ("gemini", {"candidates": [{"content": {"parts": [{"text": "   "}]}}]}),
        ("mistral", {"choices": []}),
        ("mistral", {"choices": [{"message": {"content": None}}]}),
        ("groq", {"choices": [{"message": {}}]}),
        ("groq", {"unexpected": "shape"}),
    ],
)
def test_empty_or_blocked_responses_give_a_clean_error(provider: str, payload: dict) -> None:
    llm = make(provider, lambda request: httpx.Response(200, json=payload))

    with pytest.raises(LLMProviderError, match="vide ou bloquée"):
        llm.complete_json("S", "U")


def test_non_json_and_non_object_bodies_are_rejected() -> None:
    garbage = make("groq", lambda request: httpx.Response(200, content=b"<html>pas du json</html>"))
    array = make("groq", lambda request: httpx.Response(200, json=["liste"]))

    with pytest.raises(LLMProviderError, match="illisible"):
        garbage.complete_json("S", "U")
    with pytest.raises(LLMProviderError, match="inattendue"):
        array.complete_json("S", "U")


# ---------------------------------------------------- erreurs HTTP et nouvelles tentatives


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "Clé API refusée"), (403, "Clé API refusée"), (400, "HTTP 400"), (404, "HTTP 404")],
)
def test_http_errors_are_translated_and_never_retried(status: int, message: str) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status, json={"error": "message du fournisseur"})

    with pytest.raises(LLMProviderError, match=message):
        make("mistral", handler).complete_json("S", "U")

    assert len(calls) == 1


def test_rate_limit_is_retried_with_a_capped_wait_then_succeeds() -> None:
    answers = [httpx.Response(429, headers={"retry-after": "30"}), httpx.Response(429), None]
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        answer = answers.pop(0)
        return answer if answer is not None else ok_openai(request)

    result = make("groq", handler, waits).complete_json("S", "U")

    assert json.loads(result) == {"ok": True}
    assert waits == [5.0, 1.0]  # retry-after de 30 s plafonné à 5 s ; défaut 1 s sans en-tête


def test_persistent_rate_limit_gives_up_with_a_quota_message() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429)

    with pytest.raises(LLMProviderError, match="Quota"):
        make("groq", handler).complete_json("S", "U")

    assert len(calls) == 3


def test_server_errors_are_retried_then_reported() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(LLMProviderError, match="HTTP 503"):
        make("mistral", handler).complete_json("S", "U")

    assert len(calls) == 3


# ------------------------------------------------------------------ fuite de clé ou de contenu


@pytest.mark.parametrize("provider", ["gemini", "mistral", "groq"])
@pytest.mark.parametrize("failure", ["connect", "timeout", "protocol"])
def test_network_failures_never_expose_the_key_or_the_url(provider: str, failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Comme httpx en vrai : le message de l'exception contient l'URL, donc la clé Gemini.
        errors = {
            "connect": httpx.ConnectError(f"échec de connexion à {request.url}", request=request),
            "timeout": httpx.ReadTimeout(f"délai dépassé pour {request.url}", request=request),
            "protocol": httpx.RemoteProtocolError(
                f"protocole invalide {request.url}", request=request
            ),
        }
        raise errors[failure]

    with pytest.raises(LLMProviderError) as caught:
        make(provider, handler).complete_json("S", "U")

    error = caught.value
    assert SECRET not in str(error) and SECRET not in repr(error)
    assert "http" not in str(error).lower()
    assert error.__cause__ is None and error.__suppress_context__ is True


def test_error_bodies_that_echo_the_prompt_are_never_relayed() -> None:
    echo = {"error": {"message": "requête invalide : CONTENU-CONFIDENTIEL-DU-CV Jean Dupont"}}

    with pytest.raises(LLMProviderError) as caught:
        make("mistral", lambda request: httpx.Response(400, json=echo)).complete_json(
            "S", "CONTENU-CONFIDENTIEL-DU-CV Jean Dupont"
        )

    assert "CONTENU-CONFIDENTIEL" not in str(caught.value) and "Dupont" not in str(caught.value)


@pytest.mark.parametrize("provider", ["gemini", "mistral", "groq"])
def test_logs_never_contain_the_key_or_the_prompt(provider: str, capsys) -> None:
    answers = [httpx.Response(429), httpx.Response(500), None]

    def handler(request: httpx.Request) -> httpx.Response:
        answer = answers.pop(0)
        if answer is not None:
            return answer
        return ok_gemini(request) if provider == "gemini" else ok_openai(request)

    capsys.readouterr()
    make(provider, handler).complete_json("S", "TEXTE-PRIVE-DU-CANDIDAT")
    logs = capsys.readouterr().out

    assert "llm_retry" in logs
    assert SECRET not in logs and "TEXTE-PRIVE" not in logs

"""Faux fournisseur scripté, pour les tests : aucun réseau, aucune clé, résultats reproductibles."""

from collections.abc import Callable


class FakeProvider:
    """Rejoue des réponses prédéfinies (ou calculées) et mémorise les appels reçus."""

    name = "fake"
    model = "fake-1"

    def __init__(self, responses: list[str | Exception] | Callable[[str, str], str]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def script(self, responses: list[str | Exception] | Callable[[str, str], str]) -> None:
        """Remplace les réponses prévues (et oublie les appels précédents)."""
        self._responses = responses
        self.calls.clear()

    def complete_json(self, system: str, user: str, *, max_output_tokens: int = 1024) -> str:
        self.calls.append((system, user))
        if callable(self._responses):
            return self._responses(system, user)
        if not self._responses:
            raise AssertionError("FakeProvider : plus de réponse prévue")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

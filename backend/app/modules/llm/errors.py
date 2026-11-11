"""Erreurs de la couche LLM. Les messages sont destinés à l'utilisateur : ils ne contiennent JAMAIS
d'URL, de clé API, d'en-tête, ni de fragment du document ou de la réponse."""


class LLMError(Exception):
    pass


class LLMDisabledError(LLMError):
    """Fonction désactivée ou mal configurée (clé absente)."""


class LLMProviderError(LLMError):
    """Réseau, authentification, quota ou erreur du fournisseur."""


class LLMOutputError(LLMError):
    """Réponse du modèle inexploitable (JSON invalide ou non conforme au schéma)."""

"""Route de santé : permet à Docker, à un load balancer ou à la CI de savoir
si le service répond."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Contrat de réponse de /health."""

    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Indique que l'API est en vie.

    Ne renvoie volontairement aucune information de configuration.
    """
    return HealthResponse(status="ok")

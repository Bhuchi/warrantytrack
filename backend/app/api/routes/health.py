from fastapi import APIRouter

from app import __version__
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check.

    Used by the frontend landing page, by docker compose, and later by the
    ALB target group. Keep it dependency-free — it must not touch the
    database, or a DB blip will take the whole service out of the load
    balancer.
    """
    return HealthResponse(status="ok", service="warrantytrack-api", version=__version__)

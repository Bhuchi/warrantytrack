from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Mirrors HealthResponse in frontend/src/types/index.ts."""

    status: str
    service: str
    version: str

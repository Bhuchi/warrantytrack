"""Response for scanning a serial-number label with Bedrock."""

from pydantic import BaseModel


class SerialScanResponse(BaseModel):
    serial: str | None
    error: str | None = None

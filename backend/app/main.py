from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import health
from app.core.config import settings

app = FastAPI(
    title="WarrantyTrack API",
    version=__version__,
    description="Warranty management for individuals and organizations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)

# Add your feature router here, one line per resource:
#   from app.api.routes import assets
#   app.include_router(assets.router, prefix="/assets")

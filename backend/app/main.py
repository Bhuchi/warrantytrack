from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import dashboard, health, notifications
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

# One include_router per resource. Give each feature router its own prefix so
# each path is defined in exactly one place; the route files use "" for the
# collection root.
app.include_router(health.router)
app.include_router(notifications.router, prefix="/notifications")
app.include_router(dashboard.router, prefix="/dashboard")
# Next, following the same pattern:
#   from app.api.routes import assets
#   app.include_router(assets.router, prefix="/assets")

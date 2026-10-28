from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import (
    assets,
    catalog,
    dashboard,
    documents,
    health,
    notifications,
)
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
# The four catalog lists the asset pickers are built from. One router each, so
# every path is still defined here and nowhere else.
app.include_router(catalog.categories_router, prefix="/categories")
app.include_router(catalog.vendors_router, prefix="/vendors")
app.include_router(catalog.departments_router, prefix="/departments")
app.include_router(catalog.locations_router, prefix="/locations")
app.include_router(assets.router, prefix="/assets")
# Receipt upload and OCR. Mounted after /assets because confirming a
# document creates assets through the same service that router uses.
app.include_router(documents.router, prefix="/documents")
app.include_router(dashboard.router, prefix="/dashboard")

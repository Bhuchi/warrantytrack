# Backend — WarrantyTrack API

FastAPI (Python) + SQLAlchemy + PostgreSQL. Serves the REST API, business logic,
OCR orchestration, and warranty monitoring.

## Run locally

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in values
alembic upgrade head          # apply DB migrations
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)
```

Run tests: `pytest`.

## Folder guide — where to put things

```
backend/app/
├── main.py       → FastAPI app entry point (creates app, mounts routers).
├── api/routes/   → API endpoints, one file per resource.
│                   e.g. assets.py, warranties.py, auth.py, documents.py
├── core/         → Config, settings, security, dependencies (env vars, auth guards).
├── models/       → SQLAlchemy DB models (the actual tables).
│                   e.g. asset.py, warranty.py, user.py, organization.py
├── schemas/      → Pydantic request/response models (API input/output shapes).
├── services/     → Business logic. Routes stay thin; real work happens here.
│                   e.g. ocr_service.py (Textract), warranty_service.py (status calc),
│                        notification_service.py (SES), import_service.py (bulk CSV)
├── db/           → DB session/engine setup.
└── utils/        → Small shared helpers.

backend/
├── tests/        → Pytest tests, mirroring the app/ structure.
└── alembic/      → Database migrations (schema version history).
```

**The layering rule (important):**
`route` → validates input via `schema` → calls a `service` → service uses
`models` to touch the DB. Keep routes thin and put logic in services so it's
testable and reusable.

## Adding a new endpoint (recipe)

1. Add/'update the SQLAlchemy model in `models/`.
2. Generate a migration: `alembic revision --autogenerate -m "add X"`.
3. Define request/response shapes in `schemas/`.
4. Write the logic in `services/`.
5. Wire up the route in `api/routes/`.
6. Add a test in `tests/`.

## Conventions

- snake_case for files, functions, and variables.
- Never hardcode secrets — read from `core/config.py` (which reads `.env`).
- Every new model change needs an Alembic migration. Don't edit the DB by hand.

# Backend — WarrantyTrack API

FastAPI (Python) + SQLAlchemy + PostgreSQL. Serves the REST API, business
logic, OCR orchestration, and warranty monitoring.

## Run it

Normally you don't run this on its own — `docker compose up` from the repo root
starts it with the database and frontend, with auto-reload.

```bash
# Apply migrations (first run, and whenever someone adds a table)
docker compose exec backend alembic upgrade head

# Run the tests
docker compose exec backend pytest

# Optional sample rows (not a login bypass)
docker compose exec backend python -m scripts.seed_dev

# The daily warranty-expiry scan, by hand (--today to try another date)
docker compose exec backend python -m scripts.scan_warranties
docker compose exec backend python -m scripts.scan_warranties --today 2026-12-01
```

### S3, Textract and SES without an AWS account

`STORAGE_BACKEND`, `OCR_BACKEND` and `EMAIL_BACKEND` default to `local`,
`fake` and `log`, so receipt upload, OCR and the expiry scan all work on
`docker compose up` with nothing configured and nothing spent. On those
defaults the browser PUTs its file to `/documents/{id}/dev-upload` instead of
to S3, OCR returns canned fields, and email goes to the log.

Set all three to `s3` / `textract` / `ses` (plus `S3_BUCKET_NAME` and
`SES_SENDER_EMAIL`) once the account exists — see `backend/.env.example`. The
app refuses to start in production on a development backend.

To run it standalone (needs Python 3.11+ and a PostgreSQL you can reach):

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in values
alembic upgrade head
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)
```

## Folder guide — where to put things

```
backend/app/
├── main.py       → FastAPI app entry point (creates app, mounts routers).
├── api/routes/   → API endpoints, one file per resource.
│                   e.g. assets.py, warranties.py, auth.py, documents.py
├── core/         → Config, settings, security, dependencies (env vars, auth guards).
├── models/       → SQLAlchemy DB models (the actual tables).
│                   e.g. asset.py, warranty.py, user.py, workspace.py
├── schemas/      → Pydantic request/response models (API input/output shapes).
├── services/     → Business logic. Routes stay thin; real work happens here.
│                   e.g. ocr_service.py (Textract), warranty_service.py (status calc),
│                        notification_service.py (SES), import_service.py (bulk CSV)
├── db/           → DB session/engine setup and the declarative Base.
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

1. Add/update the SQLAlchemy model in `models/`, and import it in `models/__init__.py`.
2. Generate a migration: `alembic revision --autogenerate -m "add X"`, then **read it** — autogenerate is a first draft.
3. Apply it: `alembic upgrade head`. Confirm with `alembic check`.
4. Define request/response shapes in `schemas/`, matching [docs/api.md](../docs/api.md).
5. Write the logic in `services/`.
6. Wire up the route in `api/routes/`, and include the router in `main.py`.
7. Add a test in `tests/`.

## Multi-tenancy and permissions

Every tenant-scoped table carries `workspace_id NOT NULL`. Every request runs
inside one workspace, and the caller's role comes from the `memberships`
table — **never** from the Cognito token. A record in a workspace the caller
doesn't belong to returns **404, not 403**.

Set `COGNITO_USER_POOL_ID` and `COGNITO_CLIENT_ID` in `backend/.env`. Send a
Cognito **ID token** as `Authorization: Bearer <token>` and select a workspace
with `X-Workspace-Id: <uuid>` on scoped requests. `GET /me` needs only the ID
token; it creates the user and personal workspace on first sign-in and lists
every current membership. `POST /workspaces` creates an organization owned by
that user. The backend reads the first profile from Cognito AdminGetUser, so
the task role needs `cognito-idp:AdminGetUser` on this user pool.
In Learner Lab mode (`create_iam_roles = false`), confirm the supplied LabRole
grants that action; Terraform cannot change its externally managed policy.

Read [docs/architecture.md](../docs/architecture.md) before writing your first
endpoint. It explains why.

## Conventions

- snake_case for files, functions, and variables.
- Never hardcode secrets — read from `core/config.py` (which reads `.env`).
- Every model change needs an Alembic migration. CI runs `alembic check` and
  will fail your PR otherwise. Don't edit the DB by hand.

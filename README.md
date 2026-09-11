# WarrantyTrack

Cloud-based warranty management for individuals and organizations. Register products/assets, upload receipts (OCR-extracted via AWS Textract), track warranty status, and get expiration notifications.

**Course:** DES424 Cloud-based Application Development · Semester 1, 2026 · Group 5

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React) + TypeScript |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Auth | Amazon Cognito |
| Storage / OCR | Amazon S3 + Amazon Textract |
| Notifications | Amazon SES |
| Hosting | Amazon ECS Fargate + ALB |
| Containers | Docker |
| CI | GitHub Actions |

## Repository Structure

This is a **monorepo**. Each top-level folder has its own README explaining what lives there and how to work in it.

```
warrantytrack/
├── frontend/     → Next.js web app (UI). See frontend/README.md
├── backend/      → FastAPI API + business logic. See backend/README.md
├── infra/        → Docker, AWS deployment configs. See infra/README.md
├── docs/         → Architecture, ERD, API notes. See docs/README.md
├── scripts/      → Helper scripts for local dev. See scripts/README.md
└── .github/      → CI workflows + PR/issue templates
```

## Getting Started (Local Dev)

**Prerequisites:** Docker Desktop, Node.js 20+, Python 3.11+, Git

```bash
# 1. Clone
git clone https://github.com/<org>/warrantytrack.git
cd warrantytrack

# 2. Copy env templates and fill in values (ask a teammate for dev secrets)
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# 3. Start everything with Docker Compose
docker compose up --build
```

- Frontend → http://localhost:3000
- Backend API docs → http://localhost:8000/docs
- PostgreSQL → localhost:5432

To run services individually without Docker, see the README in `frontend/` and `backend/`.

## Branching Strategy — GitHub Flow

We use **GitHub Flow** (simple, one long-lived branch). See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full workflow. Short version:

1. `main` is always deployable. **Never commit directly to `main`.**
2. Branch off `main` for every piece of work:
   - `feat/<short-name>` — new feature (e.g. `feat/asset-list-page`)
   - `fix/<short-name>` — bug fix
   - `chore/<short-name>` — config, deps, docs
3. Open a **Pull Request** into `main`. At least **1 teammate reviews** before merge.
4. CI must pass (lint + tests) before merging.
5. Squash-merge, then delete the branch.

Link each PR to its Jira ticket by putting the key in the title, e.g. `feat: build Assets List screen (CLOUDAPPG5-85)`.

## Team

| Name | Student ID | Focus area |
|---|---|---|
| Chaitawat Boonkitticharoen | 6622780342 | _tbd_ |
| Bhuchi Kumprakob | 6622782215 | _tbd_ |
| Sirawich Narakulsookpipat | 6622782298 | _tbd_ |
| Poonnawit Wongprateepwilai | 6622772455 | _tbd_ |
| Chaiyapat Anantarasuchart | 6622782223 | _tbd_ |

Fill in the focus areas once work is divided.

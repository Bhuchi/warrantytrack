# WarrantyTrack

Cloud-based warranty management for individuals and organizations. Register
products/assets, upload receipts (OCR-extracted via AWS Textract), track
warranty status, and get expiration notifications.

**Course:** DES424 Cloud-based Application Development · Semester 1, 2026 · Group 5

---

## New here? Start with these four things

1. **Run it** — the Getting Started section below. Takes one command.
2. **Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** — how we branch, commit and review.
3. **Read [docs/architecture.md](docs/architecture.md)** — the three decisions that shape all our code.
4. **Do the ["Your first PR"](#your-first-pr) walkthrough** — 10 minutes, gets the workflow into your hands before it matters.

Then find your slice in the [team table](#team-who-owns-what) and start on your Jira tickets.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React) + TypeScript + Tailwind |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Auth | Amazon Cognito |
| Storage / OCR | Amazon S3 + Amazon Textract |
| Notifications | Amazon SES |
| Hosting | Amazon ECS Fargate + ALB |
| Containers | Docker |
| CI | GitHub Actions |

## Repository Structure

This is a **monorepo**. Each top-level folder has its own README explaining
what lives there and how to work in it.

```
warrantytrack/
├── frontend/     → Next.js web app (UI). See frontend/README.md
├── backend/      → FastAPI API + business logic. See backend/README.md
├── infra/        → Docker, AWS deployment configs. See infra/README.md
├── docs/         → Architecture, ERD, API contract. See docs/README.md
├── scripts/      → Helper scripts for local dev. See scripts/README.md
└── .github/      → CI workflows + PR/issue templates
```

---

## Getting Started (Local Dev)

**Prerequisites:** Docker Desktop, Git. (Node 22+ and Python 3.11+ only if you
want to run a service outside Docker.)

```bash
# 1. Clone
git clone https://github.com/Bhuchi/warrantytrack.git
cd warrantytrack

# 2. Start everything
docker compose up --build
```

That's it — no env files needed to get running. Compose ships working defaults.

| What | Where |
|---|---|
| Frontend | <http://localhost:3000> |
| API docs (Swagger) | <http://localhost:8000/docs> |
| PostgreSQL | `localhost:5432` — user `warranty`, password `warranty`, db `warrantytrack` |

The landing page tells you whether the frontend can reach the backend. If it
says **Connected**, your environment is working.

**Apply database migrations** (first run, and whenever someone adds a table):

```bash
docker compose exec backend alembic upgrade head
```

Your source folders are mounted into the containers, so **saving a file
reloads the app**. You only need `--build` again when dependencies change.

```bash
docker compose down       # stop
docker compose down -v    # stop and wipe the database
```

### Adding AWS credentials later

Only needed once we have an AWS account, for S3/Textract/Cognito/SES work:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Compose picks these up automatically if present. **Never commit them.**

### Running a service without Docker

See [frontend/README.md](frontend/README.md) and [backend/README.md](backend/README.md).

---

## Team — who owns what

Work is split into **vertical slices**: each person owns the frontend *and*
backend of their feature. That way nobody is blocked waiting for someone
else's layer, and we rarely touch the same files.

| Name | Student ID | Slice | Figma | Main folders |
|---|---|---|---|---|
| Chaitawat Boonkitticharoen | 6622780342 | Auth & workspaces | D02, D03 | `frontend/src/features/auth/`, `features/workspace/`, `backend/app/api/routes/auth.py` |
| Sirawich Narakulsookpipat | 6622782298 | Assets | D05, D08 | `frontend/src/features/assets/`, `backend/app/api/routes/assets.py`, `services/asset_service.py` |
| Poonnawit Wongprateepwilai | 6622772455 | Documents & OCR | D06, D07 | `frontend/src/features/ocr/`, `backend/app/api/routes/documents.py`, `services/ocr_service.py` |
| Chaiyapat Anantarasuchart | 6622782223 | Dashboard & notifications | D04, D09 | `frontend/src/features/dashboard/`, `features/notifications/`, `services/notification_service.py` |
| Bhuchi Kumprakob | 6622782215 | Infra, CI & deployment | D01 | `infra/`, `.github/`, `docker-compose.yml`, AWS setup |

> Swap slices around if someone would rather work on something else — just
> update this table and `.github/CODEOWNERS` in the same PR.

**Shared foundations** (`backend/app/core/`, `app/db/`, `alembic/`,
`frontend/src/lib/`, `src/types/`) are owned by everyone. Changing one affects
everybody, so say so in the group chat before you do, and keep the PR small.

**Working in parallel without blocking:** the request/response shapes are
already agreed in [docs/api.md](docs/api.md). Build your screen against those
shapes with mock data while the endpoint is still being written — don't wait.

---

## Branching Strategy — GitHub Flow

We use **GitHub Flow** (simple, one long-lived branch). See
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full workflow. Short version:

1. `main` is always deployable. **Never commit directly to `main`.**
2. Branch off `main` for every piece of work:
   - `feat/<short-name>` — new feature (e.g. `feat/asset-list-page`)
   - `fix/<short-name>` — bug fix
   - `chore/<short-name>` — config, deps, docs
3. Open a **Pull Request** into `main`. At least **1 teammate reviews** before merge.
4. CI must pass (lint + types + migrations + tests) before merging.
5. Squash-merge, then delete the branch.

Link each PR to its Jira ticket by putting the key in the title, e.g.
`feat: build Assets List screen (CLOUDAPPG5-85)`.

### Your first PR

Do this once, on something harmless, so the workflow isn't new to you when
you're mid-feature.

```bash
git checkout main && git pull origin main
git checkout -b chore/add-my-name

# Edit the team table above — add your GitHub username next to your name.

git add README.md
git commit -m "chore: add my GitHub username to the team table"
git push -u origin chore/add-my-name
```

Then on GitHub: open a PR into `main`, fill in the template, request a review
from someone, wait for CI to go green, and squash-merge it. Delete the branch.
That's the whole loop.

---

## What CI checks

Every PR runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | Checks |
|---|---|
| Frontend | `npm run lint`, `npm run typecheck`, `npm run build` |
| Backend | `alembic upgrade head`, `alembic check`, `pytest` |

`alembic check` fails if someone changed a model without writing a migration.
If it goes red, run `alembic revision --autogenerate -m "..."` and commit the
result.

Run the same checks locally before pushing:

```bash
docker compose exec frontend npm run lint
docker compose exec backend pytest
```

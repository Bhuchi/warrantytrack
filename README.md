# WarrantyTrack

Cloud-based warranty management for individuals and organizations. Register
products/assets, upload receipts (read by Claude Haiku 5.5 on Amazon Bedrock), track
warranty status, and get expiration notifications.

**What it does**

- **Add assets three ways:** by hand, in bulk from a CSV/Excel file, or by
  uploading a receipt or invoice (PDF, JPG or PNG). Bedrock reads the vendor,
  date, invoice number and each line item with its serial number and warranty
  length. A file that is not an invoice or receipt is refused with a message.
- **Fills in a missing warranty length** by looking the product up on the web
  (optional, off by default; see [Local and AWS backends](#local-and-aws-backends)).
- **Tracks warranty status** (active, expiring soon, expired) and shows it on
  the dashboard and in the asset list.
- **Reminds you before a warranty ends:** a daily scan creates in-app
  notifications and sends emails through Amazon SES. Each person picks their
  channels and how many days ahead to be reminded.
- **Works for a team:** organizations with owner, admin and employee roles,
  invites, assigning assets to people, removing members, leaving or deleting an
  organization.
- **Keeps the paperwork:** the receipt and a photo of the box are stored in a
  private S3 bucket and opened through short-lived links.

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
| Database | PostgreSQL (Amazon RDS on AWS) + SQLAlchemy + Alembic |
| Auth | Amazon Cognito |
| Storage / OCR | Amazon S3 + Amazon Bedrock (Claude Haiku 5.5) |
| Warranty lookup (optional) | Tavily web search, read by Bedrock |
| Notifications | Amazon SES |
| Scheduled scan | Amazon EventBridge Scheduler starting an ECS task |
| Hosting | Amazon ECS Fargate + ALB |
| Infrastructure as code | Terraform (`infra/aws`) |
| Containers | Docker |
| CI/CD | GitHub Actions (checks every PR, deploys `main` to AWS) |

## Repository Structure

This is a **monorepo**. Each top-level folder has its own README explaining
what lives there and how to work in it.

```
warrantytrack/
├── frontend/     → Next.js web app (UI). See frontend/README.md
├── backend/      → FastAPI API + business logic. See backend/README.md
├── infra/        → Dockerfiles and the Terraform for AWS. See infra/README.md
│                   and infra/aws/DEPLOYMENT.md (the deployment runbook)
├── docs/         → Architecture, ERD, API contract. See docs/README.md
├── tests/        → Robot (browser) and Postman (API) tests. See tests/robot/README.md
│                   and tests/postman/README.md
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

### Local and AWS backends

Locally, everything that costs money or needs an account is replaced by a
stand-in, so the whole flow works with no AWS account and no spend:

| Setting | Local default | On AWS | What the local one does |
|---|---|---|---|
| `STORAGE_BACKEND` | `local` | `s3` | Keeps uploads on the API container's disk |
| `OCR_BACKEND` | `fake` | `bedrock` | Returns canned receipt fields |
| `EMAIL_BACKEND` | `log` | `ses` | Writes the email to the log instead of sending it |
| `AUTH_BACKEND` | `dev` (set by `docker-compose.yml`) | `cognito` | Treats every request as one seeded dev user |
| `WARRANTY_SEARCH_PROVIDER` | `none` | `tavily` (optional) | No web lookup of a missing warranty length |

The app **refuses to start in production** on a development backend, so a
misconfigured deploy fails loudly instead of quietly using fake data. All
settings are described in [backend/.env.example](backend/.env.example).

### Trying the real AWS services locally

Only needed if you want to run real Bedrock, S3, Cognito or SES from your
machine; the deployed app already uses them. You need AWS credentials for that.

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Compose picks these up automatically if present. **Never commit them**, and
never paste a key into a chat, a PR or an issue; the `.env` files are
git-ignored for that reason. The optional web lookup also needs a Tavily key
(`TAVILY_API_KEY`) and Bedrock, and costs one search per item.

### Running a service without Docker

See [frontend/README.md](frontend/README.md) and [backend/README.md](backend/README.md).

---

## Deployment (AWS)

The app runs on **Amazon ECS Fargate** behind an Application Load Balancer in
`ap-southeast-1`, with RDS PostgreSQL, a private S3 bucket, Cognito and SES.

**Merging `dev` into `main` deploys to production automatically.** On every
push to `main`, the `Deploy to AWS after CI` job in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) waits for the checks to
pass, then:

1. builds the API and web images and pushes them to ECR, tagged with the commit;
2. runs the database migrations as a one-off ECS task;
3. updates the ECS service to the new images.

Pull requests and pushes to `dev` only run the checks; they never deploy. So
open the "Dev to main" PR only when the team agrees `dev` is ready, and expect
the deploy to start the moment it is merged.

**Daily warranty scan.** An EventBridge Scheduler rule starts a one-off ECS
task every day at 08:00 Bangkok time (the default in
[`infra/aws/scheduler.tf`](infra/aws/scheduler.tf)) that runs
`python -m scripts.scan_warranties`. It creates the notifications and sends the
emails. It is a separate task, not a thread in the API, so it does not run
twice when the API has more than one task. You can run it locally with
`docker compose exec backend python -m scripts.scan_warranties`.

**Infrastructure** is Terraform in [`infra/aws/`](infra/aws/). The first-time
setup, redeploying, reading logs and troubleshooting are in
[infra/aws/DEPLOYMENT.md](infra/aws/DEPLOYMENT.md). The Terraform state is not
shared yet: it lives on the machine of whoever ran `terraform apply`, so
infrastructure changes have to go through that person.

**Testing the deployed app:** `./scripts/run-aws-tests.sh` runs the Robot and
Postman suites against it (see [scripts/README.md](scripts/README.md)).

---

## Team — who owns what

Work is split broadly by **layer** — a frontend pair and a backend/AWS group. The
backend is split into two API **legs** so two people build in parallel: Leg A
(asset write-path) and Leg B (OCR, warranty, dashboard, notifications). The Figma
file is one design system across all screens, so keeping the UI with a single
pair stops the components drifting apart. The detail per person below matches
what's assigned on the Jira board.

| Name | Student ID | GitHub | Owns |
|---|---|---|---|
| Chaiyapat Anantarasuchart | 6622782223 | [@erthcyp](https://github.com/erthcyp) | UX/UI design (Figma, all screens D01–D09 + N03), frontend screens D01–D07, shared UI library, nav/app shell, API wiring (auth + workspace), Postman + end-to-end/accessibility testing |
| Poonnawit Wongprateepwilai | 6622772455 | [@Aphelios514](https://github.com/Aphelios514) | Frontend screens Asset Detail D08, Notifications D09, Settings, loading/empty/error states; requirements docs (functional + roles matrix); backend Pytest + OCR-accuracy testing |
| Chaitawat Boonkitticharoen | 6622780342 | [@fongctw](https://github.com/fongctw) | Foundation: Cognito auth & RBAC, workspace switching; architecture diagram; non-functional requirements; all AWS deployment (VPC, ECS Fargate + ALB + ECR, RDS, IAM + CloudWatch, Docker→ECR, AWS account setup) |
| Sirawich Narakulsookpipat | 6622782298 | [@SirErthh](https://github.com/SirErthh) | Backend **Leg A** — asset write-path: asset data model + CRUD (Asset, Category, Vendor, Department, Location), assignment, bulk import (CSV/Excel), asset-save validation |
| Bhuchi Kumprakob | 6622782215 | [@Bhuchi](https://github.com/Bhuchi) | Backend **Leg B** — pipeline & signals: S3 + Bedrock OCR, multi-line invoices, warranty model + status, Dashboard API, Notifications API + scheduled scan + SES; plus repo/Jira setup, database schema/ERD |

Frontend tickets, owners and dates are in
[docs/frontend-plan.md](docs/frontend-plan.md).

> Changing who owns what means updating this table and `.github/CODEOWNERS` in
> the same PR.

**Shared foundations** (`backend/app/core/`, `app/db/`, `alembic/`,
`frontend/src/lib/`, `src/types/`) are owned by everyone. Changing one affects
everybody, so say so in the group chat before you do, and keep the PR small.

**Working in parallel without blocking:** the request/response shapes are
already agreed in [docs/api.md](docs/api.md). Build your screen against those
shapes with mock data while the endpoint is still being written — don't wait.

---

## Branching Strategy

All work goes through `dev` before it reaches `main`. See
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full workflow. Short version:

1. **Never commit directly to `dev` or `main`.** `main` only receives merges
   from `dev`, when the team agrees `dev` is ready. A merge into `main`
   [deploys to AWS](#deployment-aws).
2. Branch off `dev` for every piece of work:
   - `feat/<short-name>` — new feature (e.g. `feat/asset-list-page`)
   - `fix/<short-name>` — bug fix
   - `chore/<short-name>` — config, deps, docs
3. Open a **Pull Request** into `dev`. At least **1 teammate reviews** before merge.
4. CI must pass (lint + types + migrations + tests) before merging.
5. Squash-merge, then delete the branch.

Link each PR to its Jira ticket by putting the key in the title, e.g.
`feat: build Assets List screen (CLOUDAPPG5-85)`.

### Your first PR

Do this once, on something harmless, so the workflow isn't new to you when
you're mid-feature.

```bash
git checkout dev && git pull origin dev
git checkout -b chore/add-my-name

# Edit the team table above — add your GitHub username next to your name.

git add README.md
git commit -m "chore: add my GitHub username to the team table"
git push -u origin chore/add-my-name
```

Then on GitHub: open a PR into `dev`, fill in the template, request a review
from someone, wait for CI to go green, and squash-merge it. Delete the branch.
That's the whole loop.

---

## What CI checks

Every PR runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | Checks |
|---|---|
| Frontend | `npm run lint`, `npm run typecheck`, `npm run build` |
| Backend | `alembic upgrade head`, `alembic check`, `pytest` |
| Deploy to AWS | Only on a push to `main`, and only after the two jobs above pass: build, migrate, update ECS |

`alembic check` fails if someone changed a model without writing a migration.
If it goes red, run `alembic revision --autogenerate -m "..."` and commit the
result.

Run the same checks locally before pushing:

```bash
docker compose exec frontend npm run lint
docker compose exec backend pytest
```

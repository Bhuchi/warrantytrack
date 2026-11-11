# Architecture

How WarrantyTrack is put together, and *why* — so we all build in the same
direction. The full service list and the AWS system diagram are in the
Kick-off Report; this file covers the decisions that shape the code.

---

## Shape of the system

```
Browser ──▶ ALB ──▶ ECS Fargate ──┬──▶ RDS PostgreSQL   (assets, warranties, users)
                                  ├──▶ S3               (receipts, invoices)
                                  ├──▶ Textract         (OCR extraction)
                                  └──▶ SES              (expiry emails)
            Cognito ── sign-in ───┘
```

Locally the same shape runs in Docker Compose, minus the AWS services.

---

## Decision 1 — A personal account is just a workspace

Individual users and organizations need ~80% of the same features. Rather than
writing each feature twice, there is **one `workspaces` table**:

- `type = 'personal'` → exactly one member, role `owner`
- `type = 'organization'` → many members, roles `admin` / `employee`

**Every tenant-scoped table carries `workspace_id NOT NULL`.** No nullable
tenant columns — that is how cross-tenant data leaks happen.

**What this buys us:** one query path, one permission check, one dashboard
aggregation. Figma frame D03 (Workspace Selection) already assumes a user picks
among workspaces, so the UI matches the model.

**The cost:** if a user only has a personal workspace, hide the workspace
picker in the UI. That is a presentation concern, not a data one.

---

## Decision 2 — Cognito owns identity, PostgreSQL owns permissions

Cognito authenticates. It does **not** decide what you're allowed to do.

Why not Cognito Groups: groups are global to the user pool, not per
organization. A user who is an admin of one org and an employee of another
cannot be expressed without hacks like `admin_org_17`. Role changes also
wouldn't take effect until the token refreshed.

So, on every request:

1. Verify the JWT signature against Cognito's JWKS.
2. Take `sub` from the token — **and nothing else**.
3. Look up `users` by `cognito_sub`; on first sign-in, fetch email/name from
   Cognito AdminGetUser using that verified subject, then create the user and
   personal workspace.
4. Look up `memberships` for the requested `X-Workspace-Id`.
5. No membership → **404**. Not 403 — see `docs/api.md`.

Employees get a second check: they may only touch assets where
`assigned_to_user_id` is them.

**Never trust `email`, `groups`, or any custom claim from the token.**

---

## Decision 3 — OCR runs outside the request

Textract takes seconds, and multi-page PDFs need the async API. Holding an
HTTP request open that long ties up a worker and risks load-balancer timeouts.

The flow instead:

1. `POST /documents/presign` → backend returns a presigned S3 PUT URL.
2. Browser uploads **directly to S3**. The file never passes through the API.
3. `POST /documents/{id}/submit` → row moves to `pending`, extraction starts.
4. Browser polls `GET /documents/{id}` with backoff until the status changes.

```
pending ──▶ processing ──▶ extracted ──▶ confirmed
                │
                └──▶ failed
```

Bulk CSV import reuses this exact machinery — a different processor, the same
job states.

**Known limitation:** extraction runs in-process, so a crash can strand a job
in `processing`. We store `attempts` and `updated_at` so a stuck job can be
retried. The production answer is S3 event → Lambda → Textract; that is the
documented next step, not something we build this semester.

**The S3 bucket is private.** Uploads use presigned PUT, viewing uses
presigned GET with a short expiry. No public objects, ever.

---

## Warranty status

Computed, never stored as a stale column:

| Status | Rule |
|---|---|
| `active` | `warranty_end_date` is more than 30 days away |
| `expiring_soon` | `warranty_end_date` is within the next 30 days |
| `expired` | `warranty_end_date` is in the past |
| `unknown` | No warranty end date recorded |

The expiry-email job is a **scheduled task, not an in-process timer**. With
more than one Fargate task running, an in-process scheduler would fire on every
task and send duplicate emails. Use EventBridge Scheduler to run a one-off
task, or take a Postgres advisory lock so only one instance wins.

---

## Layering (backend)

```
route  →  validates input via schema  →  calls a service  →  service uses models
```

Routes stay thin. Business logic lives in `services/` so it can be tested
without HTTP. See `backend/README.md`.

---

## Cost discipline

The project budget is ฿4,000 for the whole semester, and an always-on
multi-AZ setup burns roughly that in a month. Decisions we've taken:

- **No NAT Gateway** (~$33/month on its own). ECS tasks run in public subnets
  with security groups that only accept traffic from the ALB, plus the free S3
  gateway VPC endpoint.
- **Single-AZ RDS.** Multi-AZ is the production answer and is documented as
  such in the report, but doubles the database bill.
- **One task per service** except on demo day.
- **Tear the stack down when not demoing**, and keep an AWS Budgets alert at
  ฿2,000.

Secrets on AWS come from **SSM Parameter Store** (free at standard tier), not
from `.env` files and not from Secrets Manager.

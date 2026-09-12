# API Reference

This is the **contract between the frontend and the backend**. It is written
before the endpoints exist on purpose: agreeing the shapes up front means the
frontend half of a slice can be built against a mock while the backend half is
still being written, instead of waiting for it.

**If you change a shape here, change it in the same PR in:**

- `backend/app/schemas/` (Pydantic)
- `frontend/src/types/index.ts` (TypeScript)

Live interactive docs once the backend is running: <http://localhost:8000/docs>

---

## Conventions

**Base URL** — `http://localhost:8000` locally, from `NEXT_PUBLIC_API_URL`.

**Auth** — every endpoint except `/health` requires a Cognito ID token:

```
Authorization: Bearer <jwt>
```

The backend trusts exactly one claim from that token: `sub`. Roles and
permissions are read from the `memberships` table, never from the token.

**Workspace scoping** — every request acts inside one workspace, passed as:

```
X-Workspace-Id: <uuid>
```

The backend verifies the caller has a membership in that workspace before
doing anything else.

**Errors** — JSON body `{"detail": "..."}` with standard status codes.

| Status | Meaning |
|---|---|
| 400 | Malformed request |
| 401 | Missing or invalid token |
| 403 | Authenticated, but not allowed to do this *in a workspace you belong to* |
| 404 | Not found **or** in a workspace you don't belong to |
| 422 | Validation error (FastAPI's default shape) |

> **Important:** a record in someone else's workspace returns **404, not 403**.
> A 403 would confirm the record exists, which leaks information across
> tenants. There is a test for this — don't "fix" it to 403.

**Dates** — ISO 8601 UTC strings (`2026-09-12T04:20:00Z`). IDs are UUID v4.

---

## Implemented

### `GET /health`

No auth. Used by the frontend landing page, Docker Compose, and later the ALB
target group.

```json
{ "status": "ok", "service": "warrantytrack-api", "version": "0.1.0" }
```

---

## Planned

Shapes below are agreed but not yet built. The owner of each slice implements
them — see the team table in the root `README.md`. Update the section from
*Planned* to *Implemented* in the PR that builds it.

### Auth and workspaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/me` | Current user + every workspace they belong to |
| `POST` | `/workspaces` | Create an organization workspace |
| `GET` | `/workspaces/{id}/members` | List members (admin only) |
| `POST` | `/workspaces/{id}/members` | Invite a member (admin only) |

```jsonc
// GET /me
{
  "user": { "id": "uuid", "email": "a@b.com", "display_name": "Bhuchi" },
  "memberships": [
    {
      "workspace": { "id": "uuid", "name": "Personal", "type": "personal",
                     "created_at": "2026-09-12T04:20:00Z" },
      "role": "owner"
    }
  ]
}
```

### Assets

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/assets` | List; filters `status`, `category_id`, `vendor_id`, `q`, `page` |
| `POST` | `/assets` | Create |
| `GET` | `/assets/{id}` | Detail |
| `PATCH` | `/assets/{id}` | Update |
| `DELETE` | `/assets/{id}` | Delete (admin/owner) |

```jsonc
// GET /assets  → paginated
{
  "items": [
    {
      "id": "uuid",
      "name": "Dell Latitude 5540",
      "serial_number": "ABC123",
      "purchase_date": "2025-03-01",
      "warranty_end_date": "2028-03-01",
      "warranty_status": "active",       // active | expiring_soon | expired | unknown
      "assigned_to_user_id": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Documents and OCR

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents/presign` | Get a presigned S3 PUT URL + document id |
| `POST` | `/documents/{id}/submit` | Tell the backend the upload finished; starts OCR |
| `GET` | `/documents/{id}` | Poll for OCR status and extracted fields |

The browser uploads **straight to S3** with the presigned URL — the file never
passes through the API. Then it polls `GET /documents/{id}` until `status`
leaves `pending`/`processing`.

```jsonc
// GET /documents/{id}
{
  "id": "uuid",
  "status": "extracted",   // pending | processing | extracted | confirmed | failed
  "extracted": {
    "vendor_name": "Power Buy",
    "purchase_date": "2025-03-01",
    "total_amount": "32900.00",
    "currency": "THB"
  },
  "error": null
}
```

Store the raw `extracted` values alongside whatever the user confirms, so the
OCR Review screen (D07) can show what changed — and so we can report OCR
accuracy in the final presentation.

### Dashboard and notifications

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/dashboard/summary` | Counts by warranty status |
| `GET` | `/notifications` | In-app notification list |

```jsonc
// GET /dashboard/summary
{ "total": 128, "active": 90, "expiring_soon": 12, "expired": 20, "no_warranty": 6 }
```

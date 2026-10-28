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

Shapes below are agreed but not yet built. Each slice's owner implements them.
Move a block from *Planned* to *Implemented* in the PR that builds it.

**Backend API legs** (see the team table in the root `README.md`):

- **Leg A — Sirawich:** `/assets` CRUD, `/assets/{id}/assign`, `/assets/import` (bulk), catalog (`/categories` `/vendors` `/departments` `/locations`). Owns the Asset table + `asset_service.create_asset()`.
- **Leg B — Bhuchi:** `/documents` + OCR, warranty **status** computation, `/dashboard`, `/notifications`.
- **Foundation — Chaitawat:** `/me`, `/workspaces`, Cognito auth, workspace switching.

> **Boundary rule:** OCR confirm (Leg B) creates assets **only** by calling
> Leg A's `asset_service.create_asset()` — it never writes the Asset table
> directly. The agreed function signature is the backend-side contract between
> the two legs, the same way the shapes here are the contract with the frontend.

### Validation errors (422)

Manual entry requires certain fields (Leg A, CLOUDAPPG5-118). A save with
missing/invalid fields returns `422` with per-field messages the form shows
inline:

```jsonc
// 422 Unprocessable Entity
{
  "detail": "Validation failed",
  "errors": {
    "serial_number": "required",
    "purchase_date": "must be a valid date (YYYY-MM-DD)",
    "condition": "required"
  }
}
```

### Auth and workspaces · owner: Chaitawat (foundation)

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

// POST /workspaces   (request)
{ "name": "Acme Co", "type": "organization" }
// → 201
{ "id": "uuid", "name": "Acme Co", "type": "organization",
  "role": "owner", "created_at": "..." }

// POST /workspaces/{id}/members   (request)
{ "email": "new@acme.com", "role": "employee" }   // role: admin | employee
// → 201
{ "user_id": "uuid", "email": "new@acme.com", "role": "employee",
  "status": "invited" }
```

### Assets · owner: Sirawich (Leg A)

> **Built:** the full CRUD set — `GET /assets`, `GET /assets/{id}`,
> `POST /assets`, `PATCH /assets/{id}`, `DELETE /assets/{id}`.
> **Still planned:** `assign`, `import`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/assets` | List; filters `status`, `category_id`, `vendor_id`, `q`, `page`, `page_size` |
| `POST` | `/assets` | Create (manual entry D06, or confirmed single OCR) |
| `GET` | `/assets/{id}` | Detail (D08) |
| `PATCH` | `/assets/{id}` | Update |
| `DELETE` | `/assets/{id}` | Delete (admin/owner) |
| `POST` | `/assets/{id}/assign` | Assign / unassign to an employee (admin only) |
| `POST` | `/assets/import` | Bulk CSV/Excel import |

```jsonc
// GET /assets  → paginated (lightweight rows for the list screen D05)
{
  "items": [
    {
      "id": "uuid",
      "name": "Dell Latitude 5540",
      "serial_number": "ABC123",
      "purchase_date": "2025-03-01",
      "warranty_end_date": "2028-03-01",   // null when there is no warranty
      "warranty_status": "active",       // active | expiring_soon | expired | unknown
      "assigned_to_user_id": null,
      // Flattened, not nested: the D05 table draws these as plain cells.
      "category_name": "Laptop",
      "vendor_name": "Power Buy",
      "location": "HQ Floor 3"       // the SITE, from /locations
    }
  ],
  "total": 1, "page": 1, "page_size": 20
}
```

`q` matches **name, serial number or invoice number**, case-insensitively.
`total` counts every asset matching the filters, not just the returned page.
Rows are newest-first. `page_size` defaults to 20 and is capped at 100.

**Employees see only the assets assigned to them** — on the list, on the detail
and on `PATCH`. Their `total` is their own count, not the organization's, and
an asset assigned to someone else (or to nobody) is a **404**, the same as one
in another workspace. Owners and admins see everything. This is the second of
the two checks in [architecture.md](architecture.md): `workspace_id` separates
tenants, `assigned_to_user_id` separates people inside one.

```jsonc
// POST /assets   (request)
// required: name, serial_number, condition, purchase_date, price, vendor
//           (the 18 Oct decision — see docs/frontend-plan.md)
// optional: category, location (site), department_id, invoice_number,
//           storage_note, *_image_key, document_ids, assigned_to_user_id,
//           warranty
{
  "name": "Dell Latitude 5540",
  "serial_number": "ABC123",
  "condition": "new",                  // new | good | fair | damaged
  "purchase_date": "2025-03-01",
  "price": "32900.00",
  "currency": "THB",                   // optional, defaults to THB
  "invoice_number": "INV-2025-001",
  // Vendor and category take EITHER an id OR a name. A name is looked up in
  // this workspace's catalog and created if missing — the Add Asset form and
  // OCR both produce "Power Buy", not a UUID. An id wins if both are sent.
  "vendor_name": "Power Buy",          // or "vendor_id": "uuid"
  "category_name": "Laptop",           // or "category_id": "uuid"
  "location_name": "HQ Floor 3",       // or "location_id": "uuid" — the SITE
  "department_id": "uuid",             // optional
  "storage_note": "Box is on the top shelf",   // optional, free text
  "location_image_key": null,          // optional S3 key
  "document_ids": ["uuid"],            // optional: receipts already uploaded
  "assigned_to_user_id": null,         // optional
  "warranty": {                        // optional
    "provider": "Dell",
    "start_date": "2025-03-01",
    "duration_months": 36
  }
}
// → 201  (body = GET /assets/{id} below)
```

**`end_date` is computed**, never sent: `start_date` plus `duration_months`
calendar months. Month-end purchases roll over rather than clamp — 31 Jan + 1
month is 3 Mar, not 28 Feb — because that is what the form's own preview shows
(`warrantyEndLabel` in add-asset/draft.ts uses JavaScript's `setMonth`). The
two must agree or the saved date contradicts what the user was shown.

**`409 Conflict`** if the serial number already exists *in this workspace*.
Serials are unique per workspace, never globally: two organizations can own
hardware with the same serial. This is what makes the bulk importer's
`"serial_number": "duplicate"` error possible.

`workspace_id` and `created_by_user_id` are taken from the request context and
ignored if sent in the body.

```jsonc
// GET /assets/{id}  → detail (D08)
{
  "id": "uuid",
  "name": "Dell Latitude 5540",
  "serial_number": "ABC123",
  "condition": "new",
  "purchase_date": "2025-03-01",
  "price": "32900.00",
  "currency": "THB",
  "invoice_number": "INV-2025-001",
  "category":   { "id": "uuid", "name": "Laptop" },
  "vendor":     { "id": "uuid", "name": "Power Buy" },
  "department": { "id": "uuid", "name": "IT" },
  "location":   { "id": "uuid", "name": "HQ Floor 3" },   // the site
  "storage_note": "Box is on the top shelf",
  "assigned_to": { "user_id": "uuid", "display_name": "Earth" },
  "warranty": {
    "provider": "Dell",
    "start_date": "2025-03-01",
    "end_date": "2028-03-01",
    "status": "active"                 // computed by Leg B
  },
  "documents": [
    { "id": "uuid", "s3_key": "...", "status": "confirmed", "kind": "invoice" }
  ],
  "created_at": "..."
}

// PATCH /assets/{id}   → any subset of the POST fields. Returns the asset.
//
// Omitting a field leaves it unchanged; sending it as null clears it. These
// are different instructions — { } changes nothing, { "invoice_number": null }
// clears the invoice number.
//
// "warranty": { ... }  replaces the warranty and recomputes end_date
// "warranty": null     removes it; the asset's status becomes "unknown"
//
// Not accepted here: assigned_to_user_id (use POST /assets/{id}/assign, which
// is admin-only) and document_ids (replace-vs-append is not agreed).
// 409 if the new serial number is already used by another asset in the
// workspace; resending the asset's own serial is fine.

// POST /assets/{id}/assign   (request)
{ "assigned_to_user_id": "uuid" }      // null to unassign
// → 200  (updated asset)

// DELETE /assets/{id}   → 204, no body
//
// Owners and admins only. The codes mean different things:
//   404  no membership in this workspace — not 403, which would confirm the
//        workspace exists
//   403  an employee: they belong here, they are just not allowed. Checked
//        before the asset is looked up, so it cannot be used to probe for ids
//   404  the asset does not exist, or is in another workspace
//
// The warranty and the asset_documents links go with it; the documents
// themselves stay, since one invoice can back several assets. Notifications
// survive with asset_id set to NULL.
//
// Permanent — there is no soft-delete column in the schema. Archiving instead
// would be a migration and a contract change.
```

```jsonc
// Bulk import is two-step so the user sees errors before anything is saved.
// POST /assets/import?mode=validate   (multipart file)  → dry run, saves nothing
{
  "total_rows": 50,
  "valid": 47,
  "errors": [
    { "row": 12, "field": "serial_number", "message": "duplicate" },
    { "row": 30, "field": "purchase_date", "message": "invalid date" }
  ]
}
// POST /assets/import?mode=commit      → creates the valid rows
{ "created": 47, "skipped": 3 }
```

### Catalog · owner: Sirawich (Leg A)

The four lookup lists an asset points at. They fill the pickers on Add Asset
(D06) and the filters on the Assets List (D05).

**Workspace-scoped, not global.** One organization's "IT" department is not
another's, and a shared list would leak names across tenants. A new workspace
therefore starts with four empty lists — an empty dropdown, not an error.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/categories` | What kind of thing an asset is — "Laptop", "Monitor" |
| `GET` | `/vendors` | Who it was bought from — "Power Buy", "JIB" |
| `GET` | `/departments` | Which part of the organization holds it — "IT" |
| `GET` | `/locations` | The site it lives at — "HQ Floor 3" |
| `POST` | each of the four | Add one option. **Owner or admin only** |
| `PATCH` | `…/{id}` | Rename one. **Owner or admin only** |
| `DELETE` | `…/{id}` | Remove one. **Owner or admin only** |

**Reading is open to everyone in the workspace** — an employee filling in Add
Asset needs the same pickers as an admin. **Writing is owner/admin**, matching
"Organization Administrator … manages departments, locations, vendors, asset
categories". An employee gets **403**, not 404: they belong here, they are
simply not allowed.

```jsonc
// GET /categories  (/vendors, /departments and /locations are identical)
{
  "items": [
    { "id": "uuid", "name": "Laptop" },
    { "id": "uuid", "name": "Monitor" }
  ]
}
```

Sorted A–Z. **Not paginated** — the caller is filling a dropdown and wants the
whole list; a page of 20 would just make the frontend loop to rebuild it.

`{id, name}` is the same object a catalog row already appears as when nested
in `GET /assets/{id}`, so the frontend sees one shape either way.

> **Two things, two names.** `location` on an asset is the **site** from this
> list ("HQ Floor 3"), nested like `category` and `vendor`. The free text about
> where the box is kept ("Box is on the top shelf") is `storage_note` — the Add
> Asset form labels that field "Note", and it is what FE-11 calls a free-text
> note. The database column behind `storage_note` is still named
> `assets.location`; only the API field was renamed, so there is no migration.

```jsonc
// POST /categories  (/vendors, /departments and /locations are identical)
{ "name": "Laptop" }
// → 201
{ "id": "uuid", "name": "Laptop" }
```

Names are trimmed, and must not be blank once trimmed. **409** if the name is
already on this workspace's list, matched without regard to case — otherwise
"laptop" would sit beside "Laptop" and the dashboard would count them as two
different things.

`POST /assets` also creates categories and vendors by name, as a side effect of
saving an asset. These endpoints are for managing a list directly — and are the
only way to create a **department** or a **location**, which `POST /assets`
references by id but never creates.

```jsonc
// PATCH /categories/{id}
{ "name": "Notebook" }
// → 200
{ "id": "uuid", "name": "Notebook" }

// DELETE /categories/{id}   → 204, no body
```

Renaming follows the same rules as creating: trimmed, non-blank, and **409** if
another row already has the name (case-insensitively). A row does not clash
with itself, so re-sending its current name succeeds — a form that submits
every field should not fail because one did not change.

**Deleting a catalog row never deletes assets.** Every catalog foreign key on
`assets` is `ON DELETE SET NULL` (docs/erd.md — *"deleting a category or a user
must not delete assets"*), so the assets survive and simply lose that
classification. There is therefore no "in use" check and no 409 for it.

### Documents and OCR · owner: Bhuchi (Leg B)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents/presign` | Get a presigned S3 PUT URL + document id |
| `POST` | `/documents/{id}/submit` | Upload finished; start Textract |
| `GET` | `/documents/{id}` | Poll OCR status + extracted fields |
| `POST` | `/documents/{id}/confirm` | Create asset(s) from reviewed OCR (multi-line) |

The browser uploads **straight to S3** with the presigned URL — the file never
passes through the API. Then it polls `GET /documents/{id}` until `status`
leaves `pending`/`processing`.

```jsonc
// POST /documents/presign   (request)
{ "filename": "receipt.jpg", "content_type": "image/jpeg" }
// → 200
{ "document_id": "uuid",
  "upload_url": "https://s3.amazonaws.com/...signed...",
  "s3_key": "ws/<workspace>/receipt.jpg" }

// POST /documents/{id}/submit   → 202, then poll GET /documents/{id}

// GET /documents/{id}
{
  "id": "uuid",
  "status": "extracted",   // pending | processing | extracted | confirmed | failed
  "extracted": {
    "vendor_name": "Power Buy",
    "purchase_date": "2025-03-01",
    "total_amount": "32900.00",
    "currency": "THB",
    "line_items": [                    // one invoice can hold several assets
      { "name": "Dell Latitude 5540", "serial_number": "ABC123", "price": "32900.00" }
    ]
  },
  "error": null
}
```

Store the raw `extracted` values alongside whatever the user confirms, so the
OCR Review screen (D07) can show what changed — and so we can report OCR
accuracy in the final presentation.

```jsonc
// POST /documents/{id}/confirm
// One entry per asset the user kept, pre-filled from OCR + their edits.
// Backend creates each via asset_service.create_asset() (Leg A).
{
  "assets": [
    { "name": "Dell Latitude 5540", "serial_number": "ABC123",
      "condition": "new", "purchase_date": "2025-03-01",
      "price": "32900.00", "category_id": "uuid", "vendor_id": "uuid" }
  ]
}
// → 201
{ "created_asset_ids": ["uuid"], "document_id": "uuid" }
```

### Warranty status · owner: Bhuchi (Leg B)

No standalone endpoints — warranty is embedded in the asset (set via
`POST`/`PATCH /assets`). Leg B owns the **status computation** surfaced as
`warranty_status` (list) / `warranty.status` (detail) wherever an asset appears:

- `active` — today is before `end_date − 30 days`
- `expiring_soon` — within 30 days of `end_date`
- `expired` — today is after `end_date`
- `unknown` — the asset has no warranty

### Dashboard · owner: Bhuchi (Leg B)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/dashboard/summary` | Counts by status + by department (D04 cards + charts) |
| `GET` | `/dashboard/expiring?days=30` | Assets expiring within N days (D04 table) |

```jsonc
// GET /dashboard/summary
{
  "total": 128, "active": 90, "expiring_soon": 12, "expired": 20, "no_warranty": 6,
  "by_department": [
    { "department_id": "uuid", "name": "IT", "count": 45 },
    { "department_id": "uuid", "name": "Marketing", "count": 28 }
  ]
}

// GET /dashboard/expiring?days=30
{
  "items": [
    { "asset_id": "uuid", "name": "Dell Latitude 5540", "vendor": "Power Buy",
      "department": "IT", "end_date": "2026-11-10", "status": "expiring_soon" }
  ]
}
```

### Notifications · owner: Bhuchi (Leg B)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/notifications` | In-app list (bell + Notifications screen D09) |
| `POST` | `/notifications/mark-all-read` | Mark all as read |

```jsonc
// GET /notifications
{
  "unread": 2,
  "items": [
    { "id": "uuid", "type": "warranty_expiring", "read": false,
      "asset_id": "uuid",
      "title": "Dell Latitude 5540 warranty expires in 30 days",
      "created_at": "2026-10-19T07:00:00Z" }
  ]
}
// POST /notifications/mark-all-read  → 204
```

The scheduled job (Leg B) that scans expiring warranties writes these rows and
sends the SES email; the frontend bell just reads this list.

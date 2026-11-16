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

**Workspace scoping** — routes that act on a selected workspace pass:

```
X-Workspace-Id: <uuid>
```

The backend verifies the caller has a membership in that workspace before
doing anything else. `/me`, workspace creation, and accepting or declining an
invite use only the signed-in user and do not need this header.

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

### Auth and workspace foundation

`GET /me` returns the signed-in user and every current workspace membership.
It creates the user's personal workspace on first successful Cognito sign-in.
`POST /workspaces` creates an organization and makes the caller its owner.
The contracts are listed below. Role checks on scoped routes
read `memberships` on every scoped request.

### Organization invitations

An owner or admin can list members and invite an email address to an
organization. A pending invitation is separate from `memberships` because the
person may not have an account yet. They must accept before becoming a member.

| Method | Path | Result |
|---|---|---|
| `GET` | `/me` | User, active `memberships`, and pending `invites` matched by email |
| `POST` | `/workspaces` | Create an organization and become its owner |
| `GET` | `/workspaces/{id}/members` | Active members first, then pending invites; owner/admin only |
| `POST` | `/workspaces/{id}/members` | Invite an email as admin or employee; owner/admin only |
| `POST` | `/workspaces/{id}/invite/accept` | Join the organization; returns a membership |
| `POST` | `/workspaces/{id}/invite/decline` | Delete one's own pending invite; returns 204 |
| `DELETE` | `/workspaces/{id}/invites?email=` | Cancel a pending invite; owner/admin only; 204 |
| `DELETE` | `/workspaces/{id}/members/{user_id}` | Remove a member; owner/admin only; 204 |
| `POST` | `/workspaces/{id}/leave` | The caller leaves; admin/employee only; 204 |
| `DELETE` | `/workspaces/{id}` | Delete the organization and everything in it; owner only; 204 |
| `DELETE` | `/me` | Delete the caller's data so the email can sign up again; 204 |

`POST /workspaces` accepts `{ "name": "Acme Co", "type": "organization" }`
and returns 201 with the new workspace's `id`, `name`, `type`, `created_at`,
and `role: "owner"`.

`GET /me` adds an `invites` array, empty when there are none:

```jsonc
{
  "user": { "id": "uuid", "email": "new@acme.com", "display_name": "New User" },
  "memberships": [{ "workspace": { "id": "uuid", "name": "Personal",
    "type": "personal", "created_at": "..." }, "role": "owner" }],
  "invites": [{ "workspace": { "id": "uuid", "name": "Acme Co",
    "type": "organization", "created_at": "..." }, "role": "employee",
    "invited_by": "Bhuchi", "invited_at": "..." }]
}
```

`POST /workspaces/{id}/members` accepts `{ "email": "new@acme.com", "role":
"employee" }` and returns 201 with `{ "user_id": null, "email": "new@acme.com",
"display_name": null, "role": "employee", "status": "invited", "invited_at":
"..." }`. `GET /workspaces/{id}/members` returns these rows alongside active
members, whose `status` is `active` and `invited_at` is null. A duplicate member
or invite returns 409. Invalid email, `owner` role, or a personal workspace
returns 422. An employee receives 403; a nonmember receives 404.

`POST /workspaces/{id}/invite/accept` has no body and returns 200 with
`{ "workspace": { ... }, "role": "employee" }`; declining has no body and
returns 204. Only the signed-in user whose email matches the invitation can
act on it. No pending invite returns 404.

Undoing membership (GitHub #80). All three return 204 with no body. They check
the caller's role in the workspace in the path, not the `X-Workspace-Id`
header. No membership there is 404; deleting an organization is out of scope.

- **Cancel invite** matches `email` case-insensitively. No pending invite for
  it is 404; an employee is 403; a missing `email` is 422.
- **Remove member**: the owner can't be removed (409), nor can the caller
  remove themselves (409, use leave). Not a member is 404; an employee is 403.
- **Leave**: the owner can't leave (409); a personal workspace is 422. Use
  `POST .../leave`, not `DELETE .../members/me`, so it can't clash with
  `DELETE .../members/{user_id}`.
- **Delete organization**: owner only (an admin or employee is 403); a
  personal workspace is 422, because it belongs to the account. Every table
  that points at a workspace is `ON DELETE CASCADE`, so its assets, warranties,
  documents, catalog, members, invites and notifications go with it. Receipt
  files in S3 stay, as they do when one asset is deleted.
- **Delete account** (`DELETE /me`): refused with 409 while the caller owns an
  organization (the detail names them). Otherwise deletes the caller's personal
  workspace, invites they sent or that wait for their email, and the user row;
  assets elsewhere that were assigned to or created by them become null. The
  frontend then deletes the Cognito account with Cognito `DeleteUser` and the
  user's own access token, so the backend needs no extra IAM permission.
- Removing or leaving sets `assigned_to_user_id` back to null on that person's
  assets **in this workspace**, so no asset points at someone who can no longer
  see it.

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
    "price": "required"
  }
}
```

### Assets · owner: Sirawich (Leg A)

> **Built:** the full CRUD set — `GET /assets`, `GET /assets/{id}`,
> `POST /assets`, `PATCH /assets/{id}`, `DELETE /assets/{id}` — plus
> `POST /assets/{id}/assign`, `POST /assets/import` (CSV and .xlsx), and
> `POST /assets/scan-serial` for Bedrock serial-label scanning.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/assets` | List; filters `status`, `category_id`, `vendor_id`, `q`, `page`, `page_size` |
| `POST` | `/assets` | Create (manual entry D06, or confirmed single OCR) |
| `GET` | `/assets/{id}` | Detail (D08) |
| `PATCH` | `/assets/{id}` | Update |
| `DELETE` | `/assets/{id}` | Delete (admin/owner) |
| `POST` | `/assets/{id}/assign` | Assign / unassign to an employee (admin only) |
| `POST` | `/assets/import` | Bulk CSV/Excel import |
| `POST` | `/assets/photos/presign` | Upload URL + key for a box / storage photo |
| `POST` | `/assets/scan-serial` | Read a device serial or clearly identified barcode label code with Bedrock |

`POST /assets/scan-serial` requires an authenticated workspace member. Send the
raw photo bytes with `Content-Type: image/jpeg`, `image/png`, or `image/webp`;
the maximum size is 10 MB. The backend resizes the photo and sends it directly
to Bedrock for this request. It does not save the photo. It supports labeled
serials and clear human-readable codes printed by barcodes, including Dell
PPID codes such as `CN-XXXXXX-XXXXX-XXX-XXXX`; it does not decode barcode bars
by themselves. The response is `{"serial":"...","error":null}` when a serial
is read, or has `serial: null` and an `error` message when it cannot identify
one. The user can then enter it manually.

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
// required: name, serial_number, purchase_date, price, vendor, category,
//           invoice_number, warranty (with a provider)
// optional: condition, location (site), department_id, storage_note, *_image_key,
//           document_ids, assigned_to_user_id
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
  "location_image_key": null,          // optional: key from POST /assets/photos/presign
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

**Required fields** come from `docs/database/WarrantyTrack-ERD-v1.2/README.md`
("Explicit design decisions"), which traces them to the kick-off report and
Jira CLOUDAPPG5-116 / -118: product name, purchase date, price, serial number,
vendor, category, invoice number — and **a warranty**, because "a committed
asset must have 1..N warranties" and "the old `No Warranty Info` status is no
longer generated for valid committed assets".

> **Frontend impact, flagged by that same document** ("if existing UI shows it,
> update the frontend separately"): Add Asset has no Category field yet, marks
> Invoice Number optional, and offers a "No warranty" duration. All three need
> to change before the wizard can save. The dashboard's `no_warranty` count and
> the Assets List "No warranty" filter will stop matching anything.

`PATCH` will not let an edit remove one of these either — clearing a required
field is a **422**, not a silent null.

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
  "location_image_url": "https://...",   // short-lived link to the box photo, or null
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
//
// Owners and admins only. One endpoint covers assign, reassign and unassign:
// reassigning is the same call with a different id.
//
//   403  an employee — they belong here but may not hand assets around,
//        settled before the asset is read so it cannot probe for ids
//   404  no such asset, or one in another workspace
//   422  the proposed assignee is not a member of this workspace; the body
//        omits assigned_to_user_id ({} is not a silent unassign); or the
//        workspace is personal — "exactly one member, role owner"
//        (architecture.md), so there is no employee to assign to. Creating an
//        asset with assigned_to_user_id is refused there for the same reason.
//        Unassigning stays allowed everywhere.
//
// Assignment is what brings an asset into an employee's scope: afterwards it
// appears in their GET /assets and they may PATCH it. Unassigning removes it
// from their view without deleting anything.

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
// Owner/admin only. The file is the **raw request body** with
// `Content-Type: text/csv` — not multipart, because FastAPI's UploadFile
// needs python-multipart, which is not a dependency. Same choice as
// PUT /documents/{id}/dev-upload.
//
// CSV or .xlsx, told apart by the bytes rather than by Content-Type —
// an .xlsx is a zip and always starts "PK". .xls is not supported.
//
// Excel quirks are handled: real date cells, numeric cells, cached formula
// results, and the trailing blank rows Excel keeps. Only the first worksheet
// is read.
//
// POST /assets/import?mode=validate   → dry run, saves nothing
{
  "total_rows": 50,
  "valid": 47,
  "errors": [
    { "row": 12, "field": "serial_number", "message": "duplicate" },
    { "row": 30, "field": "purchase_date", "message": "invalid date" }
  ]
}
// POST /assets/import?mode=commit      → creates the valid rows
{ "created": 47, "skipped": 3, "errors": [ ... ] }
```

**Partial by design.** Three bad rows do not discard forty-seven good ones —
each row is created in its own savepoint. `commit` repeats every check first,
so a clean dry run cannot be followed by a surprise.

**Rows are judged by exactly the rules `POST /assets` uses.** Import owns no
validation of its own, so a row rejected here would be rejected there, with
the same wording.

`row` counts the header as row 1, so it is the line number in the user's own
file. `field` is the **column name**.

**Columns** — required: `name`, `serial_number`, `purchase_date`,
`price`, `invoice_number`, `vendor`, `category`, `warranty_provider`,
`warranty_start_date`, `warranty_duration_months`. Optional, and may be left
out entirely: `condition`, `currency`, `department`, `location`, `storage_note`.

Vendor, category and location are given **by name**; a name not yet in the
workspace's list is added to it, exactly as `POST /assets` does.

A whole-file problem — not UTF-8, a missing required column, more than 1000
rows — is a **422 with a plain message**, because there is no row to blame.
Empty body is **400**; over 15MB is **413**.

#### Box / storage photo (CLOUDAPPG5-147, GitHub #98)

```jsonc
// POST /assets/photos/presign
{ "filename": "box.jpg", "content_type": "image/jpeg" }
// → 200
{ "upload_url": "https://<bucket>.s3...?X-Amz-...", "key": "workspaces/.../photos/<uuid>-box.jpg" }
```

PUT the photo to `upload_url` with the same `Content-Type`, then send `key` as
`location_image_key` on `POST /assets` or `PATCH /assets/{id}` (`null` removes
the photo). Images only: JPEG, PNG, WEBP, HEIC/HEIF; anything else is `422` on
`content_type`.

`location_image_key` must be a key from this endpoint **in the caller's
workspace**; anything else is `422` on that field. That stops an asset from
pointing at another workspace's file, or at a receipt, which would otherwise be
served through `location_image_url` past the receipt routes' employee check.

`GET /assets/{id}` (and the POST/PATCH responses) carry `location_image_url`,
a presigned GET for an `<img src>`. It expires; reload the asset for a fresh
one rather than storing it.

On `STORAGE_BACKEND=local` the upload goes to `PUT /assets/photos/dev-upload?key=…`
(auth required) and `location_image_url` points at
`GET /assets/photos/dev-view?key=…&expires=…&signature=…`. Both 404 on any
other backend.

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

### Documents and OCR · owner: Bhuchi (Leg B) — **built**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents/presign` | Get a presigned S3 PUT URL + document id |
| `POST` | `/documents/{id}/submit` | Upload finished; start OCR (Bedrock) |
| `GET` | `/documents/{id}` | Poll OCR status + extracted fields |
| `POST` | `/documents/{id}/confirm` | Create asset(s) from reviewed OCR (multi-line) |
| `GET` | `/documents/{id}/download` | Short-lived link that opens the uploaded file |

The browser uploads **straight to S3** with the presigned URL — the file never
passes through the API. Then it polls `GET /documents/{id}` until `status`
leaves `pending`/`processing`.

**Running it without AWS.** `STORAGE_BACKEND` and `OCR_BACKEND` default to
`local` and `fake`, so the whole flow works on `docker compose up` with no AWS
account and no spend. On those defaults `upload_url` points at
`PUT /documents/{id}/dev-upload` instead of at S3 — the one case where a file
passes through the API. That route 404s on any other backend, and the app
refuses to start in production on a development backend. Set
`STORAGE_BACKEND=s3 OCR_BACKEND=bedrock EMAIL_BACKEND=ses` (plus
`BEDROCK_MODEL_ID`, the Claude Haiku 5.5 model) once the account exists;
nothing else changes. `OCR_BACKEND=textract` is still supported.

**Errors.** `submit` before anything was uploaded is `409`. A *failed*
extraction is not an error here — the row carries `status: "failed"` and the
reason in `error`, which is what the review screen shows. `confirm` on a
document that is not `extracted` (including one already confirmed, so a
double-tap cannot create the assets twice) is `409`.

**A file that is not an invoice or receipt** (a product photo, a screenshot, an
ID) is also `failed`, with `error` set to *"This doesn't look like an invoice or
receipt. Please upload only an invoice or receipt."* — written to be shown as
is. The `bedrock` backend decides this from an `is_receipt` flag the model
returns; only an explicit `false` rejects, so an unclear answer or a blurry real
receipt still reaches the review screen. The frontend also refuses anything
that is not a PDF, JPG, PNG or WEBP before uploading.

**An employee sees only the receipts they uploaded themselves** — a receipt
shows what the company paid for things that are none of their business, even
for an asset assigned to them. Anything else is `404`, never `403`.

```jsonc
// POST /documents/presign   (request)
{ "filename": "receipt.jpg", "content_type": "image/jpeg" }
// → 200
{ "document_id": "uuid",
  "upload_url": "https://s3.amazonaws.com/...signed...",
  "s3_key": "workspaces/<workspace-name>-<workspace-uuid>/users/<uploader-name>-<user-uuid>/<document-uuid>-receipt.jpg" }

// POST /documents/{id}/submit   → 202, then poll GET /documents/{id}
// Extraction is still synchronous, so the first poll usually already says
// "extracted". The contract is written for the async version that replaces
// it — see docs/architecture.md, Decision 3.

// GET /documents/{id}
{
  "id": "uuid",
  "status": "extracted",   // pending | processing | extracted | confirmed | failed
  "extracted": {
    "vendor_name": "Power Buy",
    "purchase_date": "2025-03-01",
    "invoice_number": "INV-2025-001",  // null when none is printed
    "total_amount": "32900.00",
    "currency": "THB",
    "line_items": [                    // one invoice can hold several assets
      { "name": "Dell Latitude 5540", "serial_number": "ABC123", "price": "32900.00",
        "warranty_months": 36,       // null when the receipt prints no warranty length
        "category": "Laptop",        // suggested; null when unsure
        "warranty_source": null }    // {url, evidence} when warranty_months was looked up on the web
    ]
  },
  "error": null
}
```

`line_items[].warranty_months` is the warranty length printed on the receipt
for that item, as a whole number of months from 1 to 120 ("3-Y" is 36, "ประกัน
1 ปี" is 12). It is `null` when nothing is printed or the warranty is for life,
and the Add Asset screen uses it to pre-select Duration. `invoice_number` and
`line_items[].category` pre-fill Invoice Number and Category the same way;
the category is one label from a short fixed list in the OCR prompt (Laptop,
Monitor, Computer Component, …) so the catalog does not fill with variants. Only the `bedrock`
OCR backend fills it; `textract` leaves it `null`. The uploaded file may be an
image or, with the `bedrock` backend, a PDF.

Every field in `extracted` is optional, including `purchase_date`: a receipt
photographed at an angle gives some of them up, and the review screen is built
to be filled in by hand. A wrong guess is worse than a blank field, because the
user accepts it without looking.

The raw `extracted` values are kept alongside whatever the user confirms (in
`documents.confirmed_json`), so the OCR Review screen (D07) can show what
changed — and so we can report OCR accuracy in the final presentation.

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

**Confirm is all or nothing.** A five-line invoice where line two has a
duplicate serial number creates nothing, so there is one clean state to retry
from. The `422` names the offending entry by position, which is what lets the
review screen mark that row rather than show one unattributable error:

```jsonc
// 422 Unprocessable Content
{ "detail": [
    { "type": "value_error",
      "loc": ["body", "assets", 1, "serial_number"],
      "msg": "An asset with serial number ABC123 already exists." }
] }
```

Each asset is created through Leg A's `asset_service.create_asset()`, so the
required fields, the vendor-by-name lookup and the warranty end-date
calculation are identical to `POST /assets`. The document is linked to every
asset it produced, without the client having to ask for it.

#### Opening an uploaded file (GitHub #95)

```jsonc
// GET /documents/{id}/download
// → 200
{ "url": "https://<bucket>.s3.ap-southeast-1.amazonaws.com/...?X-Amz-...", "expires_in": 900 }
```

`url` is a presigned S3 GET: the bucket stays private and the file does not
pass through the API. It opens the file **inline** (browsers show JPG, PNG and
PDF directly) under its original filename, so one link serves both "view" and
"download". Open it straight away (`window.open(url)`) and ask again next
time rather than storing it; it stops working after `expires_in` seconds.

Visibility is the same as `GET /documents/{id}`: `404` for another
workspace's document or, for an employee, a colleague's upload. `404` also
when nothing was ever uploaded to the document.

On `STORAGE_BACKEND=local`, `url` points at
`GET /documents/{id}/dev-download?expires=…&signature=…`, which streams the file
from the container's disk. It needs no auth headers, because a new tab sends
none; the signed, expiring query string stands in for them, the way S3's own
signature does. Like `dev-upload`, it 404s on any other backend.

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

`days` accepts 1–365; outside that is `422`. It selects **which rows appear**
and does not change what `status` means — asked for 60 days, a warranty 45 days
out is listed but still reports `active`, so the word matches every other
screen. Already-expired assets are excluded; they are still counted in
`summary.expired`.

An **employee** sees only assets assigned to them, so their numbers are theirs,
not the organization's. Owners and admins see the whole workspace. A caller
with no membership gets `404`, never `403`.

Assets with no department are counted in `total` but have no `by_department`
row — the API does not invent an "Others" label. The chart can show the
remainder as `total − Σ count` if it wants one.

`expiring[].vendor` and `.department` are **nullable**: both are optional on an
asset, and the row still appears without them.

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
| `GET` | `/me/notification-settings` | The signed-in person's alert settings (defaults if never saved) |
| `PUT` | `/me/notification-settings` | Replace all three settings |

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

**The job is built** — `backend/scripts/scan_warranties.py`, run as a one-off
ECS task by EventBridge Scheduler, not as a thread inside the API (with more
than one Fargate task an in-process timer fires in each of them and everyone
gets duplicate mail). It also takes a Postgres advisory lock, so a double-fired
schedule still sends once.

It tells the workspace's owners and admins, plus the employee an asset is
assigned to. Each person gets **one digest email**, not one per asset. The
in-app row is written and committed before the email is attempted, so a broken
mailer still leaves the bell menu correct.

#### Notification settings (GitHub #82)

Per person, not per workspace: the same choices apply in every workspace. No
`X-Workspace-Id` needed. Stored in `notification_settings`; no row means the
defaults.

```jsonc
// GET /me/notification-settings  → 200 (the defaults if never saved)
{ "in_app_enabled": true, "email_enabled": true, "remind_days": [30, 14, 7] }

// PUT /me/notification-settings  (all three fields)  → 200, the saved settings
{ "in_app_enabled": true, "email_enabled": false, "remind_days": [30, 7] }
```

- `remind_days` values come from `60, 30, 14, 7, 1`, no duplicates, returned
  largest first. Anything else, a missing field, or an unknown field is `422`.
  An empty list is allowed: no reminders before expiry.
- Signed out is `401`.

How the daily scan uses them:

- **Reminder days.** A reminder goes out when a warranty *crosses* one of the
  person's days (`days_left <= t`), once per day chosen, so a missed run still
  reminds the next day. The scan looks 60 days ahead; each person's days decide
  whether they hear about it.
- **Expired.** Unchanged: one "expired" alert within 7 days after the end date,
  whatever `remind_days` says, at most once every 30 days per asset.
- **Email off.** The row is written; it is left out of that person's email.
- **In-app off.** The row is still written (it is the de-duplication record),
  but `GET /notifications` and its `unread` count leave out
  `warranty_expiring` and `warranty_expired` rows for that person.

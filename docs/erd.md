# Database Schema

Current tables live in `backend/app/models/`. Every schema change needs an
Alembic migration — CI runs `alembic check` and fails the build if a model was
changed without one.

## Tenancy (migration `0001_initial_tenancy`)

```mermaid
erDiagram
    WORKSPACES ||--o{ MEMBERSHIPS : has
    USERS      ||--o{ MEMBERSHIPS : has

    WORKSPACES {
        uuid     id PK
        string   name
        enum     type "personal | organization"
        datetime created_at
    }
    USERS {
        uuid     id PK
        string   cognito_sub UK "the only claim we trust"
        string   email UK
        string   display_name
        datetime created_at
    }
    MEMBERSHIPS {
        uuid id PK
        uuid user_id FK
        uuid workspace_id FK
        enum role "owner | admin | employee"
    }
```

`memberships` is unique on `(user_id, workspace_id)` — one role per person per
workspace.

## Pending invitations (migration `0004_workspace_invites`)

```mermaid
erDiagram
    WORKSPACES ||--o{ WORKSPACE_INVITES : has
    USERS ||--o{ WORKSPACE_INVITES : sends
    WORKSPACE_INVITES {
        uuid id PK
        uuid workspace_id FK
        string email "lowercase; unique per workspace"
        enum role "admin | employee"
        uuid invited_by FK
        datetime created_at
    }
```

An invitation is matched to the signed-in user's email. It remains separate
from `memberships` until accepted because the invited person may not have a
`users` row yet. Accepting creates a membership and removes the invitation in
one transaction; declining only removes it.

## Features (migration `0002_assets_documents`)

Eight more tables: the asset, its warranty, the documents it was proved by,
the four lookup lists, and the notification feed.

**Every one of them carries `workspace_id NOT NULL`**, and every index leads
with that column, because every query starts by narrowing to one workspace.

```mermaid
erDiagram
    WORKSPACES ||--o{ ASSETS : contains
    ASSETS     ||--o| WARRANTIES : has
    ASSETS     ||--o{ ASSET_DOCUMENTS : cites
    DOCUMENTS  ||--o{ ASSET_DOCUMENTS : backs
    USERS      ||--o{ ASSETS : "assigned to"
    USERS      ||--o{ NOTIFICATIONS : receives
    ASSETS     ||--o{ NOTIFICATIONS : "is about"
    CATEGORIES  ||--o{ ASSETS : classifies
    VENDORS     ||--o{ ASSETS : supplies
    DEPARTMENTS ||--o{ ASSETS : holds
    LOCATIONS   ||--o{ ASSETS : stores

    ASSETS {
        uuid    id PK
        uuid    workspace_id FK
        string  name
        string  serial_number "unique per workspace"
        enum    condition "new | good | fair | damaged"
        date    purchase_date
        numeric price "12,2 — never float"
        string  currency "default THB"
        string  invoice_number
        uuid    category_id FK
        uuid    vendor_id FK
        uuid    department_id FK
        uuid    location_id FK
        string  location "free text: Shelf B2"
        string  image_key "S3 key, not a URL"
        string  location_image_key
        uuid    assigned_to_user_id FK "employees see only these"
        uuid    created_by_user_id FK
    }
    WARRANTIES {
        uuid   id PK
        uuid   workspace_id FK
        uuid   asset_id FK "unique — at most one per asset"
        string provider
        date   start_date
        date   end_date
        int    duration_months
    }
    DOCUMENTS {
        uuid   id PK
        uuid   workspace_id FK
        uuid   uploaded_by_user_id FK
        string s3_key UK
        enum   kind "invoice | receipt | warranty_card | other"
        enum   status "pending|processing|extracted|confirmed|failed"
        json   extracted_json "raw Textract output"
        json   confirmed_json "what the user approved"
        int    attempts
        string error
        string textract_job_id
    }
    ASSET_DOCUMENTS {
        uuid asset_id PK_FK
        uuid document_id PK_FK
        uuid workspace_id FK
    }
    NOTIFICATIONS {
        uuid   id PK
        uuid   workspace_id FK
        uuid   user_id FK "one row per recipient"
        uuid   asset_id FK
        enum   type "warranty_expiring | warranty_expired | asset_assigned"
        string title
        bool   read
    }
    CATEGORIES  { uuid id PK
                  uuid workspace_id FK
                  string name "unique per workspace" }
    VENDORS     { uuid id PK
                  uuid workspace_id FK
                  string name }
    DEPARTMENTS { uuid id PK
                  uuid workspace_id FK
                  string name }
    LOCATIONS   { uuid id PK
                  uuid workspace_id FK
                  string name }
```

### Decisions worth knowing before you query this

**There is no `status` column on `warranties`, and there must not be one.**
Warranty status is a function of `end_date` and today's date, so a stored copy
is wrong as soon as the clock passes it. `warranty_service` computes it on
read; the rules are in [architecture.md](architecture.md). What *is* stored is
`end_date`, because that is what the dashboard, the expiring list and the
nightly e-mail job all filter on — hence the index on
`(workspace_id, end_date)`.

**Documents link to assets through a join table, not a column.** The draft ERD
had `documents.asset_id`, which cannot express either direction that actually
happens: one asset can have an invoice *and* a warranty card, and one invoice
with several line items becomes several assets that all cite it (which is why
`POST /documents/{id}/confirm` returns `created_asset_ids`, plural). A document
row is also created by `POST /documents/presign` *before* any asset exists, so
the column would start out NULL anyway.

**Deletes never cascade sideways.** `workspace_id` is `ON DELETE CASCADE` —
deleting a workspace takes its data. Everything else (`category_id`,
`vendor_id`, `department_id`, `location_id`, `assigned_to_user_id`,
`created_by_user_id`, `notifications.asset_id`) is `ON DELETE SET NULL`:
deleting a category or a user must not delete assets. A notification outlives
the asset it was about — it just stops being a link.

**`serial_number` is unique per workspace, not globally.** That is what makes
the bulk importer's `"serial_number": "duplicate"` error possible, while still
letting two organizations own hardware with the same serial.

**`locations` vs `assets.location`.** The table is the site picker ("HQ Floor
3"), the column is free text for the spot inside it ("Shelf B2"). `docs/api.md`
currently only returns the free-text one; if the detail payload should also
return `location: {id, name}` like category and vendor do, that is a contract
change for Leg A to make in api.md first.

**S3 keys, never URLs** (`image_key`, `location_image_key`, `documents.s3_key`).
The bucket is private and the API hands out short-lived presigned GETs, so a
stored URL would be expired by the time anyone read it.

**`asset_documents` carries a redundant `workspace_id`.** Both sides already
have one. It is there because the house rule is that every tenant-scoped table
has it, and the rule holds precisely because exceptions are where cross-tenant
leaks start.

## Adding a table

```bash
# 1. Write the model in backend/app/models/, import it in models/__init__.py
# 2. Generate the migration (needs the DB running: docker compose up db)
cd backend
alembic revision --autogenerate -m "add assets table"
# 3. Read the generated file — autogenerate is a first draft, not the answer
# 4. Apply and verify
alembic upgrade head
alembic check          # must say "No new upgrade operations detected"
```

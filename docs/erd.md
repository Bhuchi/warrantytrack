# Database Schema

Current tables live in `backend/app/models/`. Every schema change needs an
Alembic migration — CI runs `alembic check` and fails the build if a model was
changed without one.

## Now (migration `0001_initial_tenancy`)

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

## Planned

Each slice owner adds their own tables. **Every one of them carries
`workspace_id NOT NULL`** and is indexed on `(workspace_id, ...)`.

```mermaid
erDiagram
    WORKSPACES ||--o{ ASSETS : contains
    ASSETS     ||--o| WARRANTIES : has
    ASSETS     ||--o{ DOCUMENTS : has
    USERS      ||--o{ ASSETS : "assigned to"
    VENDORS    ||--o{ ASSETS : supplies
    CATEGORIES ||--o{ ASSETS : classifies

    ASSETS {
        uuid   id PK
        uuid   workspace_id FK
        string name
        string serial_number
        date   purchase_date
        uuid   assigned_to_user_id FK "employees see only these"
    }
    WARRANTIES {
        uuid   id PK
        uuid   workspace_id FK
        uuid   asset_id FK
        string provider
        date   start_date
        date   end_date
    }
    DOCUMENTS {
        uuid   id PK
        uuid   workspace_id FK
        uuid   asset_id FK
        string s3_key
        enum   status "pending|processing|extracted|confirmed|failed"
        json   extracted_json "raw Textract output, kept for accuracy reporting"
        int    attempts
    }
```

Departments and locations follow the same pattern when that slice starts.

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

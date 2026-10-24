# WarrantyTrack — Database ERD & PostgreSQL schema (v1.2)

## Files
- `warrantytrack_erd_core.png` / `.svg` — identity, ownership, master data, assets, warranties, documents.
- `warrantytrack_erd_workflow.png` / `.svg` — Add Asset draft/OCR review + notification/email delivery.
- `schema.sql` — PostgreSQL 15+ DDL: 16 tables, foreign keys, checks, indexes, updated_at triggers, warranty-status view.
- `smoke_test.sql` — manual transaction-based checks against a fresh PostgreSQL schema; rolls back test records.
- `render_erd.py` — source code to regenerate color-coded diagrams; requires `graphviz` Python package and Graphviz `dot`.

## Legend
- Violet — identity, memberships, and draft review.
- Blue — assets / data finalized after review.
- Cyan — category, vendor, departments, locations.
- Amber — warranties.
- Teal — S3 document and temporary upload metadata.
- Green — notifications / user preferences / Amazon SES deliveries.
- Dark gray — reference-only tables (shown again to help read diagram 2).
- `PK` primary key, `FK` foreign key, `REQ` not-null core field, `!` required, `?` nullable.
- **Arrow points from the FK-holding table to its referenced table.** E.g. `warranties → assets` means warranty records belong to assets. `assets → warranties` is an intentional additional deferred FK ensuring each asset has a *primary warranty* belonging to itself; this makes **1..N warranties required**.
- Diagram intentionally shows a representative subset of columns for readability. SQL is the complete source of truth.

## How Add Asset maps into the database

1. **Step 1 Receipt/Invoice — required**: `asset_drafts` holds the draft and user-reviewed `draft_payload`. If receipt/photo was uploaded, stage its S3 metadata in `draft_files` and OCR attempts in `ocr_extractions`. The UI must let the user correct extracted fields, and manually enter them if OCR fails. The manual path does not require an S3 receipt file.
2. **Step 2 Serial Number — required**: the editable serial is recorded in `asset_drafts.draft_payload`; users must provide a nonblank serial number before proceeding, and **cannot skip Step 2**. An optional serial sticker photo uses `draft_files(file_kind='serial_photo')`, which may be OCR'd and reviewed. If OCR fails, the user can type the serial manually.
3. **Step 3 Box/Storage — optional**: optional box/storage photo(s) and note. A photo uses `file_kind='box_photo'`; the note becomes `assets.storage_note`. Physical condition is deferred entirely.
4. **Confirm final step**: run **one DB transaction** to validate required draft fields (product, purchase date, price, vendor, category, invoice number, serial number, and warranty), generate both asset and primary-warranty UUIDs, insert `assets` with `primary_warranty_id` pointing at the planned warranty UUID, insert that warranty and any extended warranties/documents, then set `asset_drafts.draft_status='completed'` plus `completed_asset_id`. The FK is deferred and validated at COMMIT.
5. **Cancel**: transition to `draft_status='cancelled'`; cleanup staged S3 uploads out of band. Step 2 cannot be skipped; skipping Step 3 creates no corresponding box photo or storage note.

## Explicit design decisions / items to align with Jira

- **Final approved flow**: `serial_number` is mandatory (`TEXT NOT NULL` plus nonblank `CHECK`). This matches the kickoff report and Jira CLOUDAPPG5-116 and -118. The UI must not offer Skip on Step 2.
- **Physical condition is postponed**: no `physical_condition` column and no `condition_photo` document kind for now. If the feature is approved later, add fields/tables through a migration. This differs from the older kickoff report/Jira task descriptions and those documents should be aligned before implementation.
- Receipt/invoice **information** is required in step 1; receipt **file** is not mandated, because manual fallback must work after OCR failure. This resolves the difference between UI behavior and the original kickoff report's optional upload clause.
- The final asset requires **product name, purchase date, price, serial number, vendor, category, and invoice number**. `category_id` and `vendor_id` are `NOT NULL` FKs. `invoice_number` is `NOT NULL` and nonblank even on manual entry (OCR failure never bypasses business required fields).
- **A committed asset must have 1..N warranties**; the primary warranty is non-null and constrained to the same asset using a deferred composite foreign key. Additional standard/extended warranties are permitted. The old `No Warranty Info` status is no longer generated for valid committed assets. If existing UI shows it, update the frontend separately.
- `asset_warranty_status` is derived (not stored). This DDL uses a **30-day** expiring-soon window and only produces `active`, `expiring_soon`, or `expired` for valid committed assets. Future-start warranties and multi-warranty presentation policy need explicit product decisions.
- `departments` and `locations` are **organization-scoped**; personal storage text is captured by `assets.storage_note`. A reusable personal location directory can be added later if needed.
- `vendors` and `categories` are shared lookups; if per-organization catalogs are needed, add tenant scope before deployment.
- Authentication credentials are managed by **Amazon Cognito**, file bytes by **Amazon S3**; the database stores only related IDs and metadata.
- Cross-tenant security is **not fully solved by these table constraints**. Enforce who can view/edit assets through FastAPI authorization and/or PostgreSQL RLS before production. For organization assets, employees should only access assigned assets unless granted additional permissions.

## Run

1. Create an empty PostgreSQL 15+ database (e.g. RDS PostgreSQL).
2. Run `psql -v ON_ERROR_STOP=1 -f schema.sql` as the designated migrations role.
3. To insert an asset, start a transaction and **pre-generate the asset UUID and primary warranty UUID**. Insert the asset with `primary_warranty_id`, insert the warranty pointing to that asset, then COMMIT. The DEFERRABLE FK will fail on COMMIT if the primary warranty is missing or belongs to another asset.
4. Execute `psql -v ON_ERROR_STOP=1 -f smoke_test.sql` on a separate test database after loading the schema. It checks the required fields, the mandatory warranty FK, and rolls back test rows.
5. Create migrations (e.g. Alembic), implement API/authorization, and add integration tests before real user data.

**Important:** `schema.sql` is for a **fresh empty database**, not a migration for existing data. For an existing database, plan a data backfill and migration before making fields `NOT NULL` and requiring primary warranties.

**Validation note:** Diagrams generated using Graphviz. The SQL has **not been executed against a running PostgreSQL server** in this environment; treat it as a reviewed starter schema, not verified production migration.

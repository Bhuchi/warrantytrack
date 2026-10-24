-- WarrantyTrack · PostgreSQL 15+ · initial schema, v1.2
-- Basis: kickoff report + latest user-approved Add Asset requirements (2026-10-24).
-- Decisions: serial_number, vendor, category, invoice_number and warranty REQUIRED.
-- Physical condition is OUT OF SCOPE for now (no text field / condition photo).
-- Receipt fields are required but receipt file may be omitted on the OCR/manual path.
-- Box/storage photo and storage_note OPTIONAL.
-- Run in a fresh database. Review authorization/RLS before production deployment.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- 1. Identity and workspaces -------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub TEXT NOT NULL UNIQUE,
    email CITEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organization_members (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'employee')),
    member_status TEXT NOT NULL DEFAULT 'active'
        CHECK (member_status IN ('active', 'invited', 'disabled')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE CHECK (length(btrim(name)) > 0)
);

CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE CHECK (length(btrim(name)) > 0),
    website_url TEXT
);

CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    UNIQUE (organization_id, name),
    UNIQUE (organization_id, id)
);

CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    description TEXT,
    UNIQUE (organization_id, name),
    UNIQUE (organization_id, id)
);

-- 2. Assets and warranties --------------------------------------------------
CREATE TABLE assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Exactly one owner: personal user OR organization.
    personal_owner_user_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    created_by UUID NOT NULL REFERENCES users(id),
    assigned_to_user_id UUID REFERENCES users(id),
    product_name TEXT NOT NULL CHECK (length(btrim(product_name)) > 0),
    model_name TEXT,
    serial_number TEXT NOT NULL CHECK (length(btrim(serial_number)) > 0),  -- Step 2 REQUIRED
    category_id UUID NOT NULL REFERENCES categories(id),
    vendor_id UUID NOT NULL REFERENCES vendors(id),
    department_id UUID,
    location_id UUID,
    purchase_date DATE NOT NULL,
    invoice_number TEXT NOT NULL CHECK (length(btrim(invoice_number)) > 0),
    purchase_price NUMERIC(14,2) NOT NULL CHECK (purchase_price >= 0),
    currency_code CHAR(3) NOT NULL DEFAULT 'THB'
        CHECK (currency_code ~ '^[A-Z]{3}$'),
    primary_warranty_id UUID NOT NULL,  -- referenced after warranties are defined
    storage_note TEXT,   -- Step 3 OPTIONAL
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT assets_one_owner CHECK
        ((personal_owner_user_id IS NULL) <> (organization_id IS NULL)),
    CONSTRAINT assets_org_only_fields CHECK
        (organization_id IS NOT NULL OR
          (assigned_to_user_id IS NULL AND department_id IS NULL AND location_id IS NULL)),
    CONSTRAINT assets_assigned_is_org_member FOREIGN KEY (organization_id, assigned_to_user_id)
        REFERENCES organization_members(organization_id, user_id),
    CONSTRAINT assets_department_same_org FOREIGN KEY (organization_id, department_id)
        REFERENCES departments(organization_id, id),
    CONSTRAINT assets_location_same_org FOREIGN KEY (organization_id, location_id)
        REFERENCES locations(organization_id, id)
);

CREATE TABLE warranties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    warranty_type TEXT NOT NULL DEFAULT 'standard'
        CHECK (warranty_type IN ('standard', 'extended', 'other')),
    provider_name TEXT NOT NULL CHECK (length(btrim(provider_name)) > 0),
    starts_on DATE NOT NULL,
    expires_on DATE NOT NULL,
    duration_months INTEGER NOT NULL CHECK (duration_months > 0),
    coverage_details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT valid_warranty_dates CHECK (expires_on >= starts_on),
    CONSTRAINT warranties_id_asset_unique UNIQUE (id, asset_id)
);

-- Every committed asset MUST have at least one warranty, and the nominated primary
-- warranty MUST belong to the same asset. This intentionally forms a deferred
-- FK cycle: assets.primary_warranty_id -> warranties.id -> assets.id.
-- Insert both rows in the SAME transaction; assign asset_id/warranty_id UUIDs
-- before inserting. PostgreSQL validates this FK at transaction COMMIT.
ALTER TABLE assets ADD CONSTRAINT assets_primary_warranty_same_asset
    FOREIGN KEY (primary_warranty_id, id)
    REFERENCES warranties (id, asset_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    document_kind TEXT NOT NULL CHECK (document_kind IN
        ('receipt','invoice','warranty_certificate','serial_photo',
         'box_photo','other')),
    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (s3_bucket, s3_key)
);

-- 3. Add Asset workflow: receipt OCR, required serial review, optional box, finalize -----
CREATE TABLE asset_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by UUID NOT NULL REFERENCES users(id),
    personal_owner_user_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    current_step SMALLINT NOT NULL DEFAULT 1 CHECK (current_step BETWEEN 1 AND 3),
    entry_method TEXT NOT NULL CHECK (entry_method IN ('upload','camera','manual')),
    draft_status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (draft_status IN ('in_progress','cancelled','completed')),
    receipt_review_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    serial_review_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    -- Editable, provisional values before final typed rows are committed.
    draft_payload JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(draft_payload) = 'object'),
    completed_asset_id UUID UNIQUE REFERENCES assets(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT drafts_one_owner CHECK
        ((personal_owner_user_id IS NULL) <> (organization_id IS NULL)),
    CONSTRAINT drafts_completion_consistency CHECK
        (draft_status <> 'completed' OR completed_asset_id IS NOT NULL)
);

CREATE TABLE draft_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES asset_drafts(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    file_kind TEXT NOT NULL CHECK (file_kind IN
        ('receipt','invoice','serial_photo','box_photo')),
    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (s3_bucket, s3_key)
);

CREATE TABLE ocr_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_file_id UUID NOT NULL REFERENCES draft_files(id) ON DELETE CASCADE,
    extraction_kind TEXT NOT NULL CHECK (extraction_kind IN ('receipt','serial')),
    provider TEXT NOT NULL DEFAULT 'aws_textract',
    ocr_status TEXT NOT NULL CHECK
        (ocr_status IN ('pending','processing','succeeded','failed')),
    raw_result JSONB,
    extracted_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT ocr_fields_object CHECK (jsonb_typeof(extracted_fields) = 'object')
);

-- 4. Notification preferences + email delivery ------------------------------
CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    warning_days SMALLINT NOT NULL DEFAULT 30 CHECK (warning_days BETWEEN 1 AND 365),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    warranty_id UUID REFERENCES warranties(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL CHECK (notification_type IN
        ('warranty_expiring','warranty_expired','system')),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notification_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    channel TEXT NOT NULL DEFAULT 'email' CHECK (channel = 'email'),
    delivery_status TEXT NOT NULL CHECK
        (delivery_status IN ('queued','sent','failed')),
    ses_message_id TEXT,
    error_message TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Useful indexes --------------------------------------------------------
CREATE INDEX idx_org_members_user ON organization_members (user_id);
CREATE INDEX idx_assets_personal ON assets (personal_owner_user_id, created_at DESC)
    WHERE personal_owner_user_id IS NOT NULL;
CREATE INDEX idx_assets_org ON assets (organization_id, created_at DESC)
    WHERE organization_id IS NOT NULL;
CREATE INDEX idx_assets_assignee ON assets (assigned_to_user_id)
    WHERE assigned_to_user_id IS NOT NULL;
CREATE INDEX idx_assets_category ON assets (category_id);
CREATE INDEX idx_assets_vendor ON assets (vendor_id);
CREATE INDEX idx_warranties_asset ON warranties (asset_id);
CREATE INDEX idx_warranties_expiry ON warranties (expires_on);
CREATE INDEX idx_documents_asset_kind ON documents (asset_id, document_kind);
CREATE INDEX idx_drafts_user_state ON asset_drafts (created_by, draft_status);
CREATE INDEX idx_draft_files_draft_kind ON draft_files (draft_id, file_kind);
CREATE INDEX idx_ocr_draft_file ON ocr_extractions (draft_file_id, created_at DESC);
CREATE INDEX idx_notifications_user_unread ON notifications (recipient_user_id, created_at DESC)
    WHERE read_at IS NULL;
CREATE INDEX idx_notification_deliveries_notification ON notification_deliveries (notification_id);

-- 6. Dashboard status: derived (not duplicated in assets) -------------------
-- Rule: > 30 days remaining = active; 0..30 days = expiring_soon;
-- all warranties past expiry = expired. All committed assets have warranties.
-- Future-start warranty behavior should be agreed before production.
CREATE VIEW asset_warranty_status AS
SELECT
    a.id AS asset_id,
    CASE
        WHEN coalesce(bool_or(w.expires_on > current_date + 30), false) THEN 'active'
        WHEN coalesce(bool_or(w.expires_on >= current_date), false) THEN 'expiring_soon'
        ELSE 'expired'
    END AS warranty_status,
    max(w.expires_on) AS latest_warranty_expiry
FROM assets a
JOIN warranties w ON w.asset_id = a.id
GROUP BY a.id;

-- 7. Updated_at helper for mutable main entities ---------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER assets_updated_at BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER warranties_updated_at BEFORE UPDATE ON warranties
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER asset_drafts_updated_at BEFORE UPDATE ON asset_drafts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER notification_preferences_updated_at BEFORE UPDATE ON notification_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- SECURITY / APPLICATION RULES TO IMPLEMENT BEFORE PRODUCTION:
-- A. Validate organization membership and permissions for reads/writes;
--    assigned employee scope must be enforced in API and/or RLS.
-- B. Ensure document upload ownership and OCR file kind match the draft.
-- C. Steps 1 and 2 cannot be skipped. Verify receipt_review_confirmed AND
--    serial_review_confirmed; validate vendor/category/invoice, serial, purchase
--    information and required warranty in draft_payload before finalizing.
--    Finalize Step 3 in ONE transaction: pre-generate asset and warranty UUIDs,
--    insert linked assets/warranties/documents, set draft_status='completed'.
--    No physical-condition field or photo is required or collected for now.
--    ONLY Step 3 may be skipped.
-- D. Cancel removes/invalidates draft and cleans staged S3 files asynchronously.
-- E. Ensure vendor/category global catalogs respect your tenant data policy.
-- F. Mandatory warranty is enforced via the circular DEFERRABLE composite FK,
--    and a non-null primary_warranty_id. Do not disable constraints in production.

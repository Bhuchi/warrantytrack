/**
 * Asset request and response shapes, from docs/api.md "Assets". Keep in sync
 * with the backend's Pydantic schemas (backend/app/schemas/asset.py).
 */
import type { AssetCondition, DocumentStatus } from "./documents";
import type { WarrantyStatus } from "./index";

/** A catalog entry (category, vendor, department or site) as the API nests it. */
export interface CatalogRef {
  id: string;
  name: string;
}

/** GET /assets/{id}, the Asset Detail screen (D08). */
export interface AssetDetail {
  id: string;
  name: string;
  serial_number: string;
  condition: AssetCondition;
  /** "YYYY-MM-DD". */
  purchase_date: string;
  /** Decimal as a string, e.g. "51599.00". */
  price: string | null;
  currency: string;
  invoice_number: string | null;
  category: CatalogRef | null;
  vendor: CatalogRef | null;
  department: CatalogRef | null;
  /** The site ("HQ Floor 3"). */
  location: CatalogRef | null;
  /** Free text from Add Asset step 3, shown under "Box / Storage". */
  storage_note: string | null;
  assigned_to: { user_id: string; display_name: string | null } | null;
  /** Null only for assets saved before a warranty became required. */
  warranty: {
    provider: string | null;
    /** "YYYY-MM-DD". */
    start_date: string | null;
    end_date: string;
    status: WarrantyStatus;
  } | null;
  documents: {
    id: string;
    /** Where the file is in S3; the bucket is private, so this is not a link. */
    s3_key: string;
    status: DocumentStatus;
    kind: "invoice" | "receipt" | "warranty_card" | "other";
  }[];
  created_at: string;
}

/** The warranty part of POST /assets. The backend works out end_date. */
export interface WarrantyInput {
  provider: string | null;
  /** "YYYY-MM-DD". */
  start_date: string;
  duration_months: number;
}

/** POST /assets. Required: name, serial_number, condition, purchase_date (+ purchase info). */
export interface CreateAssetRequest {
  name: string;
  serial_number: string;
  condition: AssetCondition;
  /** "YYYY-MM-DD". */
  purchase_date: string;
  /** Decimal as a string, e.g. "51599.00". */
  price: string;
  currency: string;
  invoice_number?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  vendor_id?: string | null;
  vendor_name?: string | null;
  department_id?: string | null;
  /**
   * The site the asset lives at ("HQ Floor 3"), from the /locations list.
   * Send either the id or the name — a name that is not on the list yet is
   * added to it, the same way vendor works.
   */
  location_id?: string | null;
  location_name?: string | null;
  /** Free text about where the box is kept — the "Note" field in step 3. */
  storage_note?: string | null;
  /** S3 key of the box / storage photo. */
  location_image_key?: string | null;
  /** Receipts already uploaded, e.g. the OCR document. */
  document_ids?: string[];
  assigned_to_user_id?: string | null;
  warranty?: WarrantyInput | null;
}

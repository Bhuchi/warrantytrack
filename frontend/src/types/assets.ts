/**
 * Asset request shapes, from docs/api.md "Assets". Keep in sync with the
 * backend's Pydantic schemas.
 */
import type { AssetCondition } from "./documents";

/** The warranty part of POST /assets. The backend works out end_date. */
export interface WarrantyInput {
  /** Required (issue #34). The form fills it from the vendor. */
  provider: string;
  /** "YYYY-MM-DD". */
  start_date: string;
  duration_months: number;
}

/**
 * POST /assets. Required (issue #34): name, serial number, purchase date,
 * price, vendor, category, invoice number and a warranty with a provider.
 * Condition is optional.
 */
export interface CreateAssetRequest {
  name: string;
  serial_number: string;
  condition?: AssetCondition;
  /** "YYYY-MM-DD". */
  purchase_date: string;
  /** Decimal as a string, e.g. "51599.00". */
  price: string;
  currency: string;
  invoice_number: string;
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
  warranty: WarrantyInput;
}

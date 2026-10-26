/**
 * Asset request shapes, from docs/api.md "Assets". Keep in sync with the
 * backend's Pydantic schemas.
 */
import type { AssetCondition } from "./documents";

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
  vendor_id?: string | null;
  department_id?: string | null;
  /** Box / storage location note. */
  location?: string | null;
  /** S3 key of the box / storage photo. */
  location_image_key?: string | null;
  /** Receipts already uploaded, e.g. the OCR document. */
  document_ids?: string[];
  assigned_to_user_id?: string | null;
  warranty?: WarrantyInput | null;
}

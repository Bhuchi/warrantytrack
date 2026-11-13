/**
 * Receipt upload and OCR shapes, from docs/api.md "Documents and OCR".
 * Keep in sync with the backend's Pydantic schemas.
 */

/** Where a receipt is in the OCR pipeline. Poll GET /documents/{id} until it leaves pending/processing. */
export type DocumentStatus = "pending" | "processing" | "extracted" | "confirmed" | "failed";

/**
 * One item read from the receipt. A receipt can list several; the Add Asset
 * flow uses the first for now (multi-item invoices are a later improvement).
 */
export interface ExtractedLineItem {
  name: string;
  serial_number: string | null;
  /** Decimal as a string, e.g. "32900.00", so no precision is lost. */
  price: string;
  /** Warranty length printed on the receipt, in months. Null when none is printed. */
  warranty_months?: number | null;
  /**
   * Set only when `warranty_months` was looked up on the web because the
   * receipt printed none. Absent when the length came from the receipt itself.
   */
  warranty_source?: { url: string; evidence: string | null } | null;
  /** Suggested category name, e.g. "Laptop". Null when OCR is unsure. */
  category?: string | null;
}

/**
 * What OCR read from the receipt. The contract only shows filled-in
 * values; the nulls are assumed for fields OCR could not find.
 * Confirm with Bhuchi (CLOUDAPPG5-95).
 */
export interface ExtractedReceipt {
  vendor_name: string | null;
  /** "YYYY-MM-DD". */
  purchase_date: string | null;
  /** Printed invoice or receipt number. Null when none was found. */
  invoice_number?: string | null;
  total_amount: string | null;
  currency: string | null;
  line_items: ExtractedLineItem[];
}

/** GET /documents/{id}. */
export interface OcrDocument {
  id: string;
  status: DocumentStatus;
  /** Filled once status is "extracted". */
  extracted: ExtractedReceipt | null;
  /** Why OCR failed, when status is "failed". */
  error: string | null;
}

/** Physical condition. Optional when saving an asset since issue #34. */
export type AssetCondition = "new" | "good" | "fair" | "damaged";

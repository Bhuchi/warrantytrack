import type { CreateAssetRequest } from "@/types/assets";
import type { AssetCondition, OcrDocument } from "@/types/documents";

/**
 * Everything the user enters across the three Add Asset steps. Nothing is
 * saved until the end, when this becomes one POST /assets (or
 * /documents/{id}/confirm). Field names follow the API so that step is a
 * near-direct copy. Kept as strings while editing, like the inputs.
 */
export interface AssetDraft {
  /** The OCR document this came from; null for manual entry. */
  document_id: string | null;
  name: string;
  vendor_name: string;
  /** "YYYY-MM-DD", the same format <input type="date"> uses. */
  purchase_date: string;
  /** Decimal as a string, e.g. "51599.00". */
  price: string;
  currency: string;
  invoice_number: string;
  /** Empty until the user picks one. */
  condition: AssetCondition | "";
  warranty_provider: string;
  warranty_start_date: string;
  /** Months as a string from the dropdown ("12"), or "" for none. */
  warranty_duration_months: string;
  /** Step 2 (FE-10). OCR sometimes reads it from the receipt already. */
  serial_number: string;
  /** Step 3 (FE-11), optional: where the box is kept. */
  location: string;
  /** Step 3, optional: photo of the box or where it is kept. Uploaded on save. */
  location_photo: File | null;
}

export const EMPTY_DRAFT: AssetDraft = {
  document_id: null,
  name: "",
  vendor_name: "",
  purchase_date: "",
  price: "",
  currency: "THB",
  invoice_number: "",
  condition: "",
  warranty_provider: "",
  warranty_start_date: "",
  warranty_duration_months: "",
  serial_number: "",
  location: "",
  location_photo: null,
};

/**
 * A draft pre-filled from what OCR read. Uses the first line item only:
 * receipts listing several assets are a later improvement.
 * The contract has no invoice number in `extracted`, so that stays empty.
 */
export function draftFromScan(scan: OcrDocument): AssetDraft {
  const receipt = scan.extracted;
  const item = receipt?.line_items[0];

  return {
    ...EMPTY_DRAFT,
    document_id: scan.id,
    name: item?.name ?? "",
    vendor_name: receipt?.vendor_name ?? "",
    purchase_date: receipt?.purchase_date ?? "",
    price: item?.price ?? receipt?.total_amount ?? "",
    currency: receipt?.currency ?? EMPTY_DRAFT.currency,
    // The warranty usually starts on the purchase date; the user can change it.
    warranty_start_date: receipt?.purchase_date ?? "",
    serial_number: item?.serial_number ?? "",
  };
}

/** Step 1's required fields (CLOUDAPPG5-118). Confirm stays disabled until all are filled. */
export function isReceiptComplete(draft: AssetDraft): boolean {
  return [draft.name, draft.vendor_name, draft.purchase_date, draft.price, draft.condition].every(
    (value) => value.trim() !== "",
  );
}

/**
 * When the warranty ends, as "19 May 2026", or null if start or duration is
 * missing. Display only: the backend computes the real end date.
 *
 * Same date style as features/dashboard/format.ts (PR #5). Once both are on
 * dev, move the formatting into one shared helper.
 */
export function warrantyEndLabel(draft: AssetDraft): string | null {
  const months = Number(draft.warranty_duration_months);
  if (!draft.warranty_start_date || !months) return null;

  const end = new Date(`${draft.warranty_start_date}T00:00:00`);
  end.setMonth(end.getMonth() + months);
  return end.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * The draft as the API's POST /assets body. `photoKey` is the S3 key of the
 * uploaded box photo, or null.
 *
 * TODO: the API wants vendor_id, but OCR and the form give a vendor name, and
 * nothing turns one into the other yet (/vendors is Leg A). Asked the team
 * whether POST /assets should accept vendor_name, or the frontend looks it up.
 */
export function toCreateAssetRequest(draft: AssetDraft, photoKey: string | null): CreateAssetRequest {
  const months = Number(draft.warranty_duration_months);

  return {
    name: draft.name.trim(),
    serial_number: draft.serial_number.trim(),
    // Only reachable after step 1's Confirm, which requires a condition.
    condition: draft.condition as AssetCondition,
    purchase_date: draft.purchase_date,
    price: draft.price.trim(),
    currency: draft.currency,
    invoice_number: draft.invoice_number.trim() || null,
    location: draft.location.trim() || null,
    location_image_key: photoKey,
    document_ids: draft.document_id ? [draft.document_id] : [],
    warranty:
      draft.warranty_start_date && months
        ? { provider: draft.warranty_provider.trim() || null, start_date: draft.warranty_start_date, duration_months: months }
        : null,
  };
}

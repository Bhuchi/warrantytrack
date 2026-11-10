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
  /** A name, e.g. "Laptop". POST /assets adds it to the category list if it is new. */
  category_name: string;
  /** Optional (issue #34). Empty until the user picks one. */
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
  category_name: "",
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
    // Receipts rarely name the warranty provider, so start from the vendor
    // (Bhuchi's suggestion on issue #34). Same for the start date: the
    // warranty usually starts on the purchase date. The user can change both.
    warranty_provider: receipt?.vendor_name ?? "",
    warranty_start_date: receipt?.purchase_date ?? "",
    serial_number: item?.serial_number ?? "",
  };
}

/**
 * Step 1's required fields (CLOUDAPPG5-118, issue #34): everything except
 * condition. Confirm stays disabled until all are filled.
 */
export function isReceiptComplete(draft: AssetDraft): boolean {
  return [
    draft.name,
    draft.vendor_name,
    draft.purchase_date,
    draft.price,
    draft.invoice_number,
    draft.category_name,
    draft.warranty_provider,
    draft.warranty_start_date,
    draft.warranty_duration_months,
  ].every((value) => value.trim() !== "");
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
 * Vendor and category go as names: POST /assets adds a name it has not seen
 * to the workspace's list, so the form does not need a picker first.
 *
 * Only call it once isReceiptComplete(draft) is true: the warranty fields
 * are assumed filled.
 */
export function toCreateAssetRequest(draft: AssetDraft, photoKey: string | null): CreateAssetRequest {
  const months = Number(draft.warranty_duration_months);

  return {
    name: draft.name.trim(),
    serial_number: draft.serial_number.trim(),
    // Left out when not chosen, rather than sent empty.
    condition: draft.condition || undefined,
    purchase_date: draft.purchase_date,
    price: draft.price.trim(),
    currency: draft.currency,
    invoice_number: draft.invoice_number.trim(),
    vendor_name: draft.vendor_name.trim(),
    category_name: draft.category_name.trim(),
    // Step 3's "Note" field. The draft still calls it `location`; the API
    // calls it storage_note, because `location` there is the site.
    storage_note: draft.location.trim() || null,
    location_image_key: photoKey,
    document_ids: draft.document_id ? [draft.document_id] : [],
    warranty: {
      provider: draft.warranty_provider.trim(),
      start_date: draft.warranty_start_date,
      duration_months: months,
    },
  };
}

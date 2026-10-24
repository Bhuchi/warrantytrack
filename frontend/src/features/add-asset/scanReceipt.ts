import type { ExtractedReceipt, OcrDocument } from "@/types/documents";

/** What the mock "reads" from every receipt: the values in Figma M07 (3382:566). */
const MOCK_RECEIPT: ExtractedReceipt = {
  vendor_name: "Apple",
  purchase_date: "2024-05-19",
  total_amount: "51599.00",
  currency: "THB",
  line_items: [
    { name: "MacBook Pro 14-inch (M3)", serial_number: "C02X1234ABC", price: "51599.00" },
  ],
};

/** A Promise that resolves after `ms` milliseconds, so the mock feels like a real request. */
function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Sends a receipt to OCR and waits for the result. The one place the Add
 * Asset flow talks to OCR.
 *
 * Mock for now: waits 2 seconds, then returns MOCK_RECEIPT. A file whose name
 * contains "fail" (e.g. fail.jpg) comes back as failed, so the "OCR failed"
 * screen can be tested.
 *
 * Real flow, once CLOUDAPPG5-95 exists (docs/api.md "Documents and OCR"):
 *   1. POST /documents/presign  -> { document_id, upload_url }
 *   2. PUT the file to upload_url (straight to S3, not through the API)
 *   3. POST /documents/{id}/submit
 *   4. GET /documents/{id} every ~2 s until status is "extracted" or "failed"
 * All four go through lib/api; the screens keep calling scanReceipt(file).
 */
export async function scanReceipt(file: File): Promise<OcrDocument> {
  await wait(2000);

  if (file.name.toLowerCase().includes("fail")) {
    return {
      id: "mock-document",
      status: "failed",
      extracted: null,
      error: "We couldn't read this receipt.",
    };
  }

  return { id: "mock-document", status: "extracted", extracted: MOCK_RECEIPT, error: null };
}

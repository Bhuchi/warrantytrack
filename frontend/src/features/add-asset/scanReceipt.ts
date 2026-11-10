import { api } from "@/lib/api";
import type { OcrDocument } from "@/types/documents";

/** A Promise that resolves after `ms` milliseconds. Also used by scanSerial.ts. */
export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** POST /documents/presign response. */
interface PresignResponse {
  document_id: string;
  upload_url: string;
  s3_key: string;
}

/** How often to ask whether OCR is done, and when to stop asking. */
const POLL_EVERY_MS = 2000;
const GIVE_UP_AFTER_MS = 60_000;

/** A "failed" result the wizard shows on its OCR-failed screen. */
function failed(id: string, error: string): OcrDocument {
  return { id, status: "failed", extracted: null, error };
}

/**
 * Sends a receipt to OCR and waits for the result. The one place the Add
 * Asset flow talks to OCR (docs/api.md "Documents and OCR"):
 *
 *   1. POST /documents/presign     → document_id and upload_url
 *   2. PUT the file to upload_url  (S3 when deployed; the API's dev-only
 *      upload route locally)
 *   3. POST /documents/{id}/submit → starts OCR
 *   4. GET /documents/{id} every 2 s until it is "extracted" or "failed"
 *
 * Never throws: any problem comes back as status "failed" with a message,
 * which the wizard turns into the OCR-failed screen with manual entry.
 */
export async function scanReceipt(file: File): Promise<OcrDocument> {
  let id = "";

  try {
    const presign = await api.post<PresignResponse>("/documents/presign", {
      filename: file.name,
      content_type: file.type || null,
    });
    id = presign.document_id;

    // Plain fetch, not lib/api: upload_url may be S3, which must not get our
    // JSON or Authorization headers. The Content-Type has to match what was
    // sent to presign, or S3 rejects the signature.
    const upload = await fetch(presign.upload_url, {
      method: "PUT",
      body: file,
      headers: file.type ? { "Content-Type": file.type } : undefined,
    });
    if (!upload.ok) return failed(id, "We couldn't upload this file. Please try again.");

    let document = await api.post<OcrDocument>(`/documents/${encodeURIComponent(id)}/submit`);

    const giveUpAt = Date.now() + GIVE_UP_AFTER_MS;
    while (document.status === "pending" || document.status === "processing") {
      if (Date.now() > giveUpAt) {
        return failed(id, "Reading the receipt took too long. Enter the details yourself.");
      }
      await wait(POLL_EVERY_MS);
      document = await api.get<OcrDocument>(`/documents/${encodeURIComponent(id)}`);
    }

    return document;
  } catch {
    return failed(id, "We couldn't reach the server. Check your connection and try again.");
  }
}

import { ApiError, api } from "@/lib/api";
import { API_BASE_URL } from "@/lib/config";
import type { OcrDocument } from "@/types/documents";

/** A Promise that resolves after `ms` milliseconds. Also used by scanSerial.ts. */
export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface PresignResponse {
  document_id: string;
  upload_url: string;
  s3_key: string;
}

const POLL_EVERY_MS = 2000;
const GIVE_UP_AFTER_MS = 90_000;

function failed(id: string, error: string): OcrDocument {
  return { id, status: "failed", extracted: null, error };
}

/**
 * Sends a receipt to OCR and waits for the result. The one place the Add
 * Asset flow talks to OCR (docs/api.md "Documents and OCR"):
 *
 *   1. POST /documents/presign  -> { document_id, upload_url }
 *   2. PUT the file to upload_url
 *   3. POST /documents/{id}/submit
 *   4. GET /documents/{id} until status leaves pending/processing
 *
 * Never throws: any failure comes back as a `failed` document, which the
 * wizard already shows with the manual-entry fallback.
 */
export async function scanReceipt(file: File): Promise<OcrDocument> {
  let documentId = "";
  try {
    const contentType = file.type || "application/octet-stream";

    const reserved = await api.post<PresignResponse>("/documents/presign", {
      filename: file.name,
      content_type: contentType,
    });
    documentId = reserved.document_id;

    // Two different destinations. The local dev route is our own API and
    // needs the bearer token, so it goes through lib/api. A presigned S3 URL
    // must NOT get our Authorization header (S3 would reject the signature),
    // so it is a plain fetch.
    if (reserved.upload_url.startsWith(API_BASE_URL)) {
      await api.put(reserved.upload_url, file, {
        headers: { "Content-Type": contentType },
      });
    } else {
      const upload = await fetch(reserved.upload_url, {
        method: "PUT",
        headers: { "Content-Type": contentType },
        body: file,
      });
      if (!upload.ok) return failed(documentId, "The upload did not finish. Please try again.");
    }

    let document = await api.post<OcrDocument>(`/documents/${encodeURIComponent(documentId)}/submit`);

    const startedAt = Date.now();
    while (document.status === "pending" || document.status === "processing") {
      if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
        return failed(documentId, "Reading the receipt took too long.");
      }
      await wait(POLL_EVERY_MS);
      document = await api.get<OcrDocument>(`/documents/${encodeURIComponent(documentId)}`);
    }
    return document;
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      return failed(documentId, "The receipt was not uploaded. Please try again.");
    }
    return failed(documentId, "We couldn't read this receipt.");
  }
}

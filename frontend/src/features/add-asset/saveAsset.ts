import { type AssetDraft, toCreateAssetRequest } from "./draft";
import { wait } from "./scanReceipt";

/**
 * Saves the finished draft as a new asset. The one place Add Asset writes.
 *
 * Mock for now: waits 1 second and returns a fake id. In development it prints
 * the exact request it would send, so the shape can be checked in the browser
 * console before the backend exists.
 *
 * Real flow, once the endpoints exist (docs/api.md):
 *   1. If there is a box photo: presign, PUT it to S3, keep its s3_key.
 *   2. From OCR (draft.document_id set): POST /documents/{id}/confirm.
 *      Manual entry: POST /assets with toCreateAssetRequest(draft, s3Key).
 * All through lib/api; the wizard keeps calling saveAsset(draft).
 */
export async function saveAsset(draft: AssetDraft): Promise<{ id: string }> {
  const photoKey = draft.location_photo ? `mock/${draft.location_photo.name}` : null;
  const request = toCreateAssetRequest(draft, photoKey);

  if (process.env.NODE_ENV !== "production") {
    console.info("[mock] POST /assets", request);
  }

  await wait(1000);
  return { id: "mock-asset" };
}

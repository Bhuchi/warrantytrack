import { uploadAssetPhoto } from "@/features/assets/assetPhoto";
import { api } from "@/lib/api";

import { type AssetDraft, toCreateAssetRequest } from "./draft";

/** POST /documents/{id}/confirm response. */
interface ConfirmResponse {
  created_asset_ids: string[];
  document_id: string;
}

/**
 * Saves the finished draft as a new asset. The one place Add Asset writes.
 * Throws if the backend refuses; the wizard shows the error toast.
 *
 * - From OCR (draft.document_id set): POST /documents/{id}/confirm, which
 *   creates the asset and links the receipt to it. One receipt can hold
 *   several assets, so the body is a list; this form always sends one.
 * - Manual entry: POST /assets.
 *
 * The box photo (step 3) is uploaded first and saved as location_image_key.
 * If that upload fails nothing is saved, so the photo is never silently lost.
 */
export async function saveAsset(draft: AssetDraft): Promise<{ id: string }> {
  const photoKey = draft.location_photo ? await uploadAssetPhoto(draft.location_photo) : null;
  const request = toCreateAssetRequest(draft, photoKey);

  if (draft.document_id) {
    const result = await api.post<ConfirmResponse>(
      `/documents/${encodeURIComponent(draft.document_id)}/confirm`,
      { assets: [request] },
    );
    return { id: result.created_asset_ids[0] };
  }

  // The response is the whole asset (the AssetDetail shape); only the id is needed.
  const created = await api.post<{ id: string }>("/assets", request);
  return { id: created.id };
}

import { uploadAssetPhoto } from "@/features/assets/assetPhoto";
import { api } from "@/lib/api";

import { type AssetDraft, toCreateAssetRequest } from "./draft";

interface ConfirmResponse {
  created_asset_ids: string[];
  document_id: string;
}

/** Save all drafts from one receipt together, or save the single manual entry. */
export async function saveAssets(drafts: AssetDraft[]): Promise<{ ids: string[] }> {
  if (drafts.length === 0) throw new Error("At least one asset is required.");

  const requests = await Promise.all(drafts.map(async (draft) => {
    const photoKey = draft.location_photo ? await uploadAssetPhoto(draft.location_photo) : null;
    return toCreateAssetRequest(draft, photoKey);
  }));
  const documentId = drafts[0].document_id;

  if (documentId) {
    if (drafts.some((draft) => draft.document_id !== documentId)) {
      throw new Error("All assets must come from the same document.");
    }
    const result = await api.post<ConfirmResponse>(
      `/documents/${encodeURIComponent(documentId)}/confirm`,
      { assets: requests },
    );
    return { ids: result.created_asset_ids };
  }

  if (drafts.length !== 1) {
    throw new Error("Multiple manual entries require a receipt document.");
  }

  const created = await api.post<{ id: string }>("/assets", requests[0]);
  return { ids: [created.id] };
}

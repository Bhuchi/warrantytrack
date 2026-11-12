import { ApiError, api } from "@/lib/api";
import type { AssetDetail, UpdateAssetRequest } from "@/types/assets";

/**
 * Saves changes to one asset. PATCH /assets/{id} (docs/api.md "Assets").
 *
 * Send only the fields that changed: anything left out stays as it is.
 * Returns the updated asset. Throws an Error whose message can go straight on
 * the screen.
 */
export async function updateAsset(
  id: string,
  changes: UpdateAssetRequest,
): Promise<AssetDetail> {
  try {
    return await api.patch<AssetDetail>(`/assets/${encodeURIComponent(id)}`, changes);
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      throw new Error("Another asset in this workspace already has that serial number.");
    }
    if (error instanceof ApiError && error.status === 404) {
      throw new Error("This asset no longer exists, or you are not allowed to edit it.");
    }
    throw new Error("Couldn't save your changes. Check the fields and try again.");
  }
}

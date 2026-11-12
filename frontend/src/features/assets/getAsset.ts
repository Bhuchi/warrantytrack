import { ApiError, api } from "@/lib/api";
import type { AssetDetail } from "@/types/assets";

/**
 * One asset in full, for Asset Detail. GET /assets/{id} (docs/api.md "Assets").
 *
 * Returns null when the backend answers 404: no such asset, or one you are not
 * allowed to see (the backend does not say which, on purpose). Also for 422,
 * which is what an id that is not a UUID gets, e.g. the mock Dashboard's
 * "/assets/1". Any other failure, like the API not running, is thrown for the
 * screen to show.
 *
 * Call it from the browser only, like getAssets.
 */
export async function getAsset(id: string): Promise<AssetDetail | null> {
  try {
    // encodeURIComponent keeps a strange id from changing the path.
    return await api.get<AssetDetail>(`/assets/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) return null;
    throw error;
  }
}

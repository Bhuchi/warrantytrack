import { ApiError, api } from "@/lib/api";

/**
 * Deletes one asset for good. DELETE /assets/{id} (docs/api.md "Assets").
 *
 * Owners and admins only, and there is no undo: the backend has no soft
 * delete. Resolves with nothing on success (204). Throws an Error whose
 * message can go straight on the screen.
 */
export async function deleteAsset(id: string): Promise<void> {
  try {
    await api.delete(`/assets/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      throw new Error("Only an owner or admin can delete assets.");
    }
    if (error instanceof ApiError && error.status === 404) {
      throw new Error("This asset no longer exists. It may have been deleted already.");
    }
    throw new Error("Couldn't delete the asset. Check your connection and try again.");
  }
}

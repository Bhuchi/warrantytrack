/** Keep the save confirmation through a full reload if a route request fails. */
const KEY = "warrantytrack:asset-saved-toast";
const MAX_AGE_MS = 30_000;

export interface SavedToastMessage {
  title: string;
  message: string;
}

export function queueSavedToast(title: string, message: string) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ title, message, savedAt: Date.now() }));
  } catch {
    // Saving the asset has already succeeded; storage restrictions must not report a failure.
  }
}

export function takeSavedToast(): SavedToastMessage | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const saved: unknown = JSON.parse(raw);
    if (
      typeof saved === "object" &&
      saved !== null &&
      "title" in saved &&
      typeof saved.title === "string" &&
      "message" in saved &&
      typeof saved.message === "string" &&
      "savedAt" in saved &&
      typeof saved.savedAt === "number" &&
      saved.savedAt <= Date.now() &&
      Date.now() - saved.savedAt < MAX_AGE_MS
    ) {
      return { title: saved.title, message: saved.message };
    }
  } catch {
    // An old or invalid session value should not affect the dashboard.
  }
  return null;
}

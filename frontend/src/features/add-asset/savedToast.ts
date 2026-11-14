/** Keep the save confirmation through a full reload if a route request fails. */
const KEY = "warrantytrack:asset-saved-toast";
const MAX_AGE_MS = 30_000;

export function queueSavedToast(name: string) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ name, savedAt: Date.now() }));
  } catch {
    // Saving the asset has already succeeded; storage restrictions must not report a failure.
  }
}

export function takeSavedToast(): string | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const saved: unknown = JSON.parse(raw);
    if (
      typeof saved === "object" &&
      saved !== null &&
      "name" in saved &&
      typeof saved.name === "string" &&
      "savedAt" in saved &&
      typeof saved.savedAt === "number" &&
      saved.savedAt <= Date.now() &&
      Date.now() - saved.savedAt < MAX_AGE_MS
    ) {
      return saved.name;
    }
  } catch {
    // An old or invalid session value should not affect the dashboard.
  }
  return null;
}

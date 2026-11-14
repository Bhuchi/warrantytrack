import { ApiError, api } from "@/lib/api";
import { COGNITO_CLIENT_ID } from "@/lib/config";
import type { NotificationSettings } from "@/types";

/**
 * Load and save the signed-in person's alert settings (CLOUDAPPG5-145).
 * Contract: GitHub #82.
 *
 *   getNotificationSettings()      → GET /me/notification-settings
 *   saveNotificationSettings(next) → PUT /me/notification-settings
 *
 * Local UI work without Cognito keeps the settings in this browser. A Cognito
 * build uses the signed-in API so the choices persist across browsers and the
 * daily warranty scan can respect them.
 */
const USE_MOCK = !COGNITO_CLIENT_ID;

/** The reminder chips, in the order they are shown. */
export const REMIND_DAY_OPTIONS = [60, 30, 14, 7, 1] as const;

/** What a person gets before they ever change anything (same as the backend). */
export const DEFAULT_SETTINGS: NotificationSettings = {
  in_app_enabled: true,
  email_enabled: true,
  remind_days: [30, 14, 7],
};

const MOCK_KEY = "warrantytrack.mock-notification-settings";

/** No duplicates, largest first: the order the backend returns them in. */
function tidy(settings: NotificationSettings): NotificationSettings {
  return { ...settings, remind_days: [...new Set(settings.remind_days)].sort((a, b) => b - a) };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  if (USE_MOCK) {
    await delay(200);
    try {
      const saved = localStorage.getItem(MOCK_KEY);
      return saved ? (JSON.parse(saved) as NotificationSettings) : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS; // Storage blocked (private window): show the defaults.
    }
  }
  try {
    return await api.get<NotificationSettings>("/me/notification-settings");
  } catch {
    throw new Error("Couldn't load your notification settings. Refresh the page to try again.");
  }
}

/** Saves all three settings at once. Throws an Error whose message can go on screen. */
export async function saveNotificationSettings(next: NotificationSettings): Promise<NotificationSettings> {
  const body = tidy(next);
  if (USE_MOCK) {
    await delay(300);
    try {
      localStorage.setItem(MOCK_KEY, JSON.stringify(body));
    } catch {
      throw new Error("Couldn't save in this browser. Check that site storage is allowed.");
    }
    return body;
  }
  try {
    return await api.put<NotificationSettings>("/me/notification-settings", body);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      throw new Error("Those reminder days can't be saved. Pick from 60, 30, 14, 7 and 1 days.");
    }
    throw new Error("Couldn't save your settings. Check your connection and try again.");
  }
}

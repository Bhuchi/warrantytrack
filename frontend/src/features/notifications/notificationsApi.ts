import { api } from "@/lib/api";
import type { NotificationListResponse } from "@/types/notifications";

/**
 * The Notifications screen's two backend calls (docs/api.md → Notifications).
 * Call them from the browser: the deployed API address is relative ("/api"),
 * which only works there.
 */

/** Every notification for the signed-in user in this workspace, newest first. */
export function getNotifications(): Promise<NotificationListResponse> {
  return api.get<NotificationListResponse>("/notifications");
}

/** Marks every notification as read. The server answers 204, with no body. */
export function markAllNotificationsRead(): Promise<void> {
  return api.post<void>("/notifications/mark-all-read");
}

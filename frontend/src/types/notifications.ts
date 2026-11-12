/**
 * GET /notifications (docs/api.md → Notifications). Mirrors the backend's
 * `NotificationItem` and `NotificationList` in app/schemas/notification.py.
 */

/** The kinds the backend creates (NotificationType in app/models/notification.py). */
export type NotificationType = "warranty_expiring" | "warranty_expired" | "asset_assigned";

/** One row of the list. */
export interface NotificationItem {
  id: string;
  type: NotificationType;
  read: boolean;
  /** The asset it is about. Null if that asset has been deleted. */
  asset_id: string | null;
  /** The full sentence, e.g. "Dell Latitude 5540 warranty expires in 30 days". */
  title: string;
  /** ISO timestamp, e.g. "2026-10-19T07:00:00Z". */
  created_at: string;
}

/** The whole response: the unread badge count plus every item, newest first. */
export interface NotificationListResponse {
  unread: number;
  items: NotificationItem[];
}

import type { NavUser, NavWorkspace } from "@/components/NavPanel";

/** The two kinds of workspace a person can be in. */
export type WorkspaceKind = "personal" | "organization";

/** Name of the browser cookie that remembers the chosen workspace. */
export const WORKSPACE_COOKIE = "workspace";

/** Reads the cookie's value; anything unexpected (or no cookie) means organization, as before. */
export function toWorkspaceKind(value: string | undefined): WorkspaceKind {
  return value === "personal" ? "personal" : "organization";
}

/**
 * What the signed-in screens show for each workspace: the nav panel's
 * workspace card, its user card (personal has none) and the unread count.
 * Values from Figma M10: personal 3455:536, organization 3392:2. Avatar
 * initials are the first letters of the first and last name (CA), not Figma's EM.
 *
 * TODO (FE-05, CLOUDAPPG5-123): replace with the real workspace from
 * GET /me once /workspaces exists (CLOUDAPPG5-92).
 */
export const WORKSPACE_PLACEHOLDERS: Record<
  WorkspaceKind,
  { workspace: NavWorkspace; user: NavUser | null; unreadCount: number }
> = {
  personal: {
    workspace: { name: "Chaiyapat Inventory", kind: "Personal workspace", initials: "CA" },
    user: null,
    unreadCount: 1,
  },
  organization: {
    workspace: { name: "SIIT Organization", kind: "Organization workspace", initials: "SI" },
    user: { name: "Chaiyapat A.", department: "IT Department", initials: "CA" },
    unreadCount: 3,
  },
};

/**
 * Remembers the chosen workspace for a year. Runs in the browser (it uses
 * `document`), so call it from a click handler, not from a server component.
 */
export function rememberWorkspace(kind: WorkspaceKind): void {
  document.cookie = `${WORKSPACE_COOKIE}=${kind}; path=/; max-age=31536000; samesite=lax`;
}

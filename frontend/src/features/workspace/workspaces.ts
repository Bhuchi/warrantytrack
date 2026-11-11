import type { NavUser, NavWorkspace } from "@/components/NavPanel";

/** The two kinds of workspace a person can be in. */
export type WorkspaceKind = "personal" | "organization";

/** Name of the browser cookie that remembers the chosen workspace. */
export const WORKSPACE_COOKIE = "workspace";

/** Name of the cookie holding an organization created on /workspace (CLOUDAPPG5-132). */
export const WORKSPACE_NAME_COOKIE = "workspace_name";
export const WORKSPACE_ID_COOKIE = "workspace_id";

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
 * FE-05 will replace the remaining signed-in page placeholders with the
 * current workspace from GET /me.
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
 * First letters of the first and last word, the same rule as a person's
 * initials: "Acme Trading Co" → "AC". One word gives its first two letters.
 */
export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/);
  const letters = words.length > 1 ? words[0][0] + words[words.length - 1][0] : words[0].slice(0, 2);
  return letters.toUpperCase();
}

/**
 * Remembers the chosen workspace for a year. Runs in the browser (it uses
 * `document`), so call it from a click handler, not from a server component.
 *
 * `name` gives server-rendered navigation the selected workspace's label.
 * `id` is sent to the API on scoped requests; the backend checks membership.
 */
export function rememberWorkspace(kind: WorkspaceKind, name?: string, id?: string): void {
  const options = "path=/; max-age=31536000; samesite=lax";
  document.cookie = `${WORKSPACE_COOKIE}=${kind}; ${options}`;
  document.cookie = name
    ? `${WORKSPACE_NAME_COOKIE}=${encodeURIComponent(name)}; ${options}`
    : `${WORKSPACE_NAME_COOKIE}=; path=/; max-age=0`;
  document.cookie = id
    ? `${WORKSPACE_ID_COOKIE}=${encodeURIComponent(id)}; ${options}`
    : `${WORKSPACE_ID_COOKIE}=; path=/; max-age=0`;
}

export function selectedWorkspaceId(): string | null {
  return document.cookie.split("; ").find((value) => value.startsWith(`${WORKSPACE_ID_COOKIE}=`))
    ?.slice(WORKSPACE_ID_COOKIE.length + 1) ?? null;
}

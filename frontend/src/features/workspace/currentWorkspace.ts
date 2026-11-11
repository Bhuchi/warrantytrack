import { cookies } from "next/headers";

import {
  WORKSPACE_COOKIE,
  WORKSPACE_NAME_COOKIE,
  WORKSPACE_PLACEHOLDERS,
  initialsOf,
  toWorkspaceKind,
} from "./workspaces";

/**
 * The workspace chosen on /workspace, for server components (layouts and
 * pages). Kept apart from workspaces.ts because `cookies()` only works on the
 * server, and workspaces.ts is also used in the browser.
 *
 * A selected workspace name from /workspace replaces the placeholder's
 * label and initials until FE-05 loads the whole server-side profile.
 *
 * TODO (FE-05, CLOUDAPPG5-123): return the real workspace from GET /me.
 */
export async function getCurrentWorkspace() {
  const cookieStore = await cookies();
  const kind = toWorkspaceKind(cookieStore.get(WORKSPACE_COOKIE)?.value);
  const placeholder = WORKSPACE_PLACEHOLDERS[kind];

  const createdName = cookieStore.get(WORKSPACE_NAME_COOKIE)?.value;
  if (createdName) {
    const name = decodeURIComponent(createdName);
    return {
      kind,
      ...placeholder,
      workspace: { ...placeholder.workspace, name, initials: initialsOf(name) },
    };
  }

  return { kind, ...placeholder };
}

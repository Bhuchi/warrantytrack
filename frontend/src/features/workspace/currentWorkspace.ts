import { cookies } from "next/headers";

import { WORKSPACE_COOKIE, WORKSPACE_PLACEHOLDERS, toWorkspaceKind } from "./workspaces";

/**
 * The workspace chosen on /workspace, for server components (layouts and
 * pages). Kept apart from workspaces.ts because `cookies()` only works on the
 * server, and workspaces.ts is also used in the browser.
 *
 * TODO (FE-05, CLOUDAPPG5-123): return the real workspace from GET /me.
 */
export async function getCurrentWorkspace() {
  const cookieStore = await cookies();
  const kind = toWorkspaceKind(cookieStore.get(WORKSPACE_COOKIE)?.value);
  return { kind, ...WORKSPACE_PLACEHOLDERS[kind] };
}

import type { MembershipRole, Workspace } from "@/types";

/** POST /workspaces response: the new workspace and your role in it (always owner). */
export type CreatedWorkspace = Workspace & { role: MembershipRole };

/**
 * Creates an organization workspace owned by the signed-in user.
 *
 * Mock for now: waits 1 second and returns a fake workspace. In development it
 * prints the request it would send, so the shape can be checked in the browser
 * console before the backend exists.
 *
 * Real call, once Chaitawat's endpoint exists (docs/api.md):
 *   POST /workspaces  { "name": name, "type": "organization" }  → 201
 * through lib/api; the modal keeps calling createWorkspace(name).
 */
export async function createWorkspace(name: string): Promise<CreatedWorkspace> {
  const request = { name, type: "organization" as const };

  if (process.env.NODE_ENV !== "production") {
    console.info("[mock] POST /workspaces", request);
  }

  await new Promise((resolve) => setTimeout(resolve, 1000));
  return {
    id: "mock-workspace",
    ...request,
    role: "owner",
    created_at: new Date().toISOString(),
  };
}

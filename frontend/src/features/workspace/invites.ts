import { api } from "@/lib/api";
import { COGNITO_CLIENT_ID } from "@/lib/config";
import type { Invite, MeResponse, Membership } from "@/types";

/**
 * Pending organization invites: list, accept, decline (CLOUDAPPG5-133).
 * The contract is the one agreed on GitHub issue #37.
 *
 * Cognito sessions use the API. A local UI demo without Cognito keeps a mock:
 *
 *   getInvites()     → GET /me, its `invites` array
 *   acceptInvite(id) → POST /workspaces/{id}/invite/accept  → 200 Membership
 *   declineInvite(id)→ POST /workspaces/{id}/invite/decline → 204
 *
 * Call them from the browser (they read the URL, and the real ones fetch).
 */

/** The invite the mock shows: the values in Figma 3641:18 and 3642:187. */
const MOCK_INVITE: Invite = {
  workspace: {
    id: "mock-siit",
    name: "SIIT",
    type: "organization",
    created_at: "2026-11-01T00:00:00Z",
  },
  role: "employee",
  invited_by: "Dr. Aphichon",
  invited_at: "2026-11-10T04:20:00Z",
};

/** Invites accepted or declined since the page loaded, so they stop showing. */
const handled = new Set<string>();

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function logMock(request: string): void {
  if (process.env.NODE_ENV !== "production") console.info(`[mock] ${request}`);
}

/**
 * The signed-in user's pending invites.
 *
 * Mock: one invite, but only when the address has `?invite=1`, so ordinary
 * demos and user tests don't show an invite nobody sent.
 */
export async function getInvites(): Promise<Invite[]> {
  if (COGNITO_CLIENT_ID) return (await api.get<MeResponse>("/me")).invites;
  await delay(300);
  const wantsMock = new URLSearchParams(window.location.search).get("invite") === "1";
  return wantsMock && !handled.has(MOCK_INVITE.workspace.id) ? [MOCK_INVITE] : [];
}

/** Joins the organization. Returns the new membership, for its workspace card. */
export async function acceptInvite(workspaceId: string): Promise<Membership> {
  if (COGNITO_CLIENT_ID) {
    return api.post<Membership>(`/workspaces/${encodeURIComponent(workspaceId)}/invite/accept`);
  }
  logMock(`POST /workspaces/${workspaceId}/invite/accept`);
  await delay(800);
  handled.add(workspaceId);
  return { workspace: MOCK_INVITE.workspace, role: MOCK_INVITE.role };
}

/** Turns the invite down. The admin can invite again later. */
export async function declineInvite(workspaceId: string): Promise<void> {
  if (COGNITO_CLIENT_ID) {
    await api.post<void>(`/workspaces/${encodeURIComponent(workspaceId)}/invite/decline`);
    return;
  }
  logMock(`POST /workspaces/${workspaceId}/invite/decline`);
  await delay(800);
  handled.add(workspaceId);
}

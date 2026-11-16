import { ApiError, api } from "@/lib/api";
import { COGNITO_CLIENT_ID } from "@/lib/config";
import type { WorkspaceMember } from "@/types";

/**
 * Organization members and invites. Contract: GitHub #69 and #80.
 *
 *   getMembers(id)               → GET    /workspaces/{id}/members
 *   inviteMember(id, email, role)→ POST   /workspaces/{id}/members
 *   cancelInvite(id, email)      → DELETE /workspaces/{id}/invites?email=
 *   removeMember(id, userId)     → DELETE /workspaces/{id}/members/{userId}
 *   leaveOrganization(id)        → POST   /workspaces/{id}/leave
 *   deleteOrganization(id)       → DELETE /workspaces/{id}
 *
 * The local UI demo uses a mock when Cognito is not configured. Signed-in
 * sessions call the backend so team membership survives a page reload.
 */
const USE_MOCK = !COGNITO_CLIENT_ID;

/** The roles you can invite someone as. Nobody is invited as owner. */
export type InviteRole = "admin" | "employee";

/** A loose check, so obvious typos are caught before a request is sent. */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(email: string): boolean {
  return EMAIL_PATTERN.test(email.trim());
}

// --- real API ---------------------------------------------------------------

async function getMembersFromApi(workspaceId: string): Promise<WorkspaceMember[]> {
  try {
    return await api.get<WorkspaceMember[]>(`/workspaces/${encodeURIComponent(workspaceId)}/members`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      throw new Error("Only an owner or admin can see the team.");
    }
    throw new Error("Couldn't load the team. Check your connection and try again.");
  }
}

async function inviteMemberToApi(workspaceId: string, email: string, role: InviteRole): Promise<WorkspaceMember> {
  try {
    return await api.post<WorkspaceMember>(`/workspaces/${encodeURIComponent(workspaceId)}/members`, {
      email: email.trim().toLowerCase(),
      role,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      throw new Error("That email is already in this organization or has already been invited.");
    }
    if (error instanceof ApiError && error.status === 403) {
      throw new Error("Only an owner or admin can invite people.");
    }
    if (error instanceof ApiError && error.status === 422) {
      throw new Error("Check the email address and try again.");
    }
    throw new Error("Couldn't send the invite. Check your connection and try again.");
  }
}

/** Turns a failed membership change into a sentence for the screen. */
function membershipError(error: unknown, fallback: string): Error {
  if (error instanceof ApiError && error.status === 403) {
    return new Error("Only an owner or admin can do this.");
  }
  if (error instanceof ApiError && error.status === 404) {
    return new Error("That person or invite is no longer in this organization. Refresh to see the latest list.");
  }
  if (error instanceof ApiError && error.status === 409) {
    return new Error("The owner can't be removed and can't leave the organization.");
  }
  return new Error(fallback);
}

async function cancelInviteInApi(workspaceId: string, email: string): Promise<void> {
  try {
    await api.delete(`/workspaces/${encodeURIComponent(workspaceId)}/invites?email=${encodeURIComponent(email)}`);
  } catch (error) {
    throw membershipError(error, "Couldn't cancel the invite. Check your connection and try again.");
  }
}

async function removeMemberInApi(workspaceId: string, userId: string): Promise<void> {
  try {
    await api.delete(`/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`);
  } catch (error) {
    throw membershipError(error, "Couldn't remove them. Check your connection and try again.");
  }
}

async function leaveInApi(workspaceId: string): Promise<void> {
  try {
    await api.post(`/workspaces/${encodeURIComponent(workspaceId)}/leave`);
  } catch (error) {
    throw membershipError(error, "Couldn't leave the organization. Check your connection and try again.");
  }
}

// --- mock -------------------------------------------------------------------

/** Lives as long as the browser tab, so invites survive moving between pages. */
const mockMembers: WorkspaceMember[] = [
  {
    user_id: "mock-you",
    email: "you@example.com",
    display_name: "You",
    role: "owner",
    status: "active",
    invited_at: null,
  },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getMembersFromMock(): Promise<WorkspaceMember[]> {
  await delay(300);
  return [...mockMembers];
}

async function inviteMemberToMock(email: string, role: InviteRole): Promise<WorkspaceMember> {
  await delay(600);
  const normalized = email.trim().toLowerCase();
  if (mockMembers.some((member) => member.email === normalized)) {
    throw new Error("That email is already in this organization or has already been invited.");
  }
  const invited: WorkspaceMember = {
    user_id: null,
    email: normalized,
    display_name: null,
    role,
    status: "invited",
    invited_at: new Date().toISOString(),
  };
  mockMembers.push(invited);
  return invited;
}

/** Removes one row from the mock list: an invite by email, a member by id. */
async function removeFromMock(match: (member: WorkspaceMember) => boolean): Promise<void> {
  await delay(600);
  const index = mockMembers.findIndex(match);
  if (index >= 0) mockMembers.splice(index, 1);
}

// --- what the screens call --------------------------------------------------

/** Cancels a pending invite (owner or admin). GitHub #80. */
export function cancelInvite(workspaceId: string, email: string): Promise<void> {
  return USE_MOCK
    ? removeFromMock((member) => member.status === "invited" && member.email === email)
    : cancelInviteInApi(workspaceId, email);
}

/** Removes someone who has joined (owner or admin). Never the owner. GitHub #80. */
export function removeMember(workspaceId: string, userId: string): Promise<void> {
  return USE_MOCK
    ? removeFromMock((member) => member.user_id === userId)
    : removeMemberInApi(workspaceId, userId);
}

/** The signed-in user leaves (admin or employee; the owner can't). GitHub #80. */
export async function leaveOrganization(workspaceId: string): Promise<void> {
  if (USE_MOCK) {
    await delay(600);
    return;
  }
  await leaveInApi(workspaceId);
}

/** The owner deletes the organization and everything in it. Cannot be undone. */
export async function deleteOrganization(workspaceId: string): Promise<void> {
  if (USE_MOCK) {
    await delay(600);
    return;
  }
  try {
    await api.delete(`/workspaces/${encodeURIComponent(workspaceId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      throw new Error("Only the owner can delete the organization.");
    }
    throw new Error("Couldn't delete the organization. Check your connection and try again.");
  }
}

/** Everyone in the organization, active members first, then pending invites. */
export function getMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  return USE_MOCK ? getMembersFromMock() : getMembersFromApi(workspaceId);
}

/** Invites an email. Throws an Error whose message can go straight on screen. */
export function inviteMember(workspaceId: string, email: string, role: InviteRole): Promise<WorkspaceMember> {
  return USE_MOCK ? inviteMemberToMock(email, role) : inviteMemberToApi(workspaceId, email, role);
}

import { ApiError, api } from "@/lib/api";
import type { WorkspaceMember } from "@/types";

/**
 * Organization members and invites (CLOUDAPPG5-141). Contract: GitHub #69.
 *
 *   getMembers(id)               → GET  /workspaces/{id}/members
 *   inviteMember(id, email, role)→ POST /workspaces/{id}/members
 *
 * The backend endpoints are not deployed yet (CLOUDAPPG5-140), so this runs
 * on a mock. When they are, set USE_MOCK to false. Nothing else changes: the
 * real calls below already follow the contract.
 */
const USE_MOCK = true;

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

// --- what the screens call --------------------------------------------------

/** Everyone in the organization, active members first, then pending invites. */
export function getMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  return USE_MOCK ? getMembersFromMock() : getMembersFromApi(workspaceId);
}

/** Invites an email. Throws an Error whose message can go straight on screen. */
export function inviteMember(workspaceId: string, email: string, role: InviteRole): Promise<WorkspaceMember> {
  return USE_MOCK ? inviteMemberToMock(email, role) : inviteMemberToApi(workspaceId, email, role);
}

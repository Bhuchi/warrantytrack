"use client";

import { createContext, useContext } from "react";

import type { MembershipRole } from "@/types";

/**
 * The signed-in user's role in the chosen workspace. SignedInShell loads it
 * from GET /me and provides it to every signed-in page; `null` means not
 * known (for example while /me is still loading).
 *
 * Only for showing or hiding buttons. The backend checks the role again on
 * every request, so hiding a button is about a tidy screen, not security.
 */
export const WorkspaceRoleContext = createContext<MembershipRole | null>(null);

/** Read the role from anywhere inside SignedInShell. */
export function useWorkspaceRole(): MembershipRole | null {
  return useContext(WorkspaceRoleContext);
}

/** Owners and admins may delete assets (DELETE /assets/{id}, docs/api.md). */
export function canManageAssets(role: MembershipRole | null): boolean {
  return role === "owner" || role === "admin";
}

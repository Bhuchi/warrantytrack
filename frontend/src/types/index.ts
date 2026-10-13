/**
 * Shared API types. These mirror the contract in docs/api.md.
 *
 * Keep this file in sync with the backend's Pydantic schemas — if you change
 * one, change the other in the same PR.
 */

export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
};

/** A personal account is modelled as a workspace with exactly one owner. */
export type WorkspaceType = "personal" | "organization";

export type MembershipRole = "owner" | "admin" | "employee";

export interface Workspace {
  id: string;
  name: string;
  type: WorkspaceType;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string | null;
}

/** What the current user may do inside one workspace. */
export interface Membership {
  workspace: Workspace;
  role: MembershipRole;
}

export type WarrantyStatus = "active" | "expiring_soon" | "expired" | "unknown";

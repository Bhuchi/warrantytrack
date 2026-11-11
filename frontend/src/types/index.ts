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

export interface MeResponse {
  user: User;
  memberships: Membership[];
}

/**
 * A pending invite to an organization, from GET /me → `invites`. The person
 * must accept it before they join (issue #37).
 */
export interface Invite {
  workspace: Workspace;
  /** The role they will have once they accept. Nobody is invited as owner. */
  role: Exclude<MembershipRole, "owner">;
  /** Display name of the admin who sent it. */
  invited_by: string;
  /** ISO timestamp, e.g. "2026-11-10T04:20:00Z". */
  invited_at: string;
}

export type WarrantyStatus = "active" | "expiring_soon" | "expired" | "unknown";

/** One bar in "Assets by Department". */
export interface DepartmentCount {
  department_id: string;
  name: string;
  count: number;
}

/** GET /dashboard/summary: the D04 stat cards and charts. */
export interface DashboardSummary {
  total: number;
  active: number;
  expiring_soon: number;
  expired: number;
  /** Assets with no warranty. The asset itself reports these as status `unknown`. */
  no_warranty: number;
  by_department: DepartmentCount[];
}

/** One row of GET /dashboard/expiring?days=30. */
export interface ExpiringAsset {
  asset_id: string;
  name: string;
  /** Null when the asset has no vendor recorded — it is optional on an asset. */
  vendor: string | null;
  /** Null when the asset is in no department. */
  department: string | null;
  /** Warranty end date, "YYYY-MM-DD". */
  end_date: string;
  status: WarrantyStatus;
}

export interface ExpiringAssetsResponse {
  items: ExpiringAsset[];
}

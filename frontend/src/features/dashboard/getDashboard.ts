import type { DashboardSummary, ExpiringAsset } from "@/types";

/** Everything the Dashboard screen shows, in one object. */
export interface DashboardData {
  summary: DashboardSummary;
  expiring: ExpiringAsset[];
}

/**
 * Mock data copied from Figma D04 (3348:2), so the built screen can be checked
 * against the design side by side. The dates are the ones in the frame.
 */
const MOCK_DASHBOARD: DashboardData = {
  summary: {
    total: 128,
    active: 96,
    expiring_soon: 8,
    expired: 12,
    no_warranty: 12,
    by_department: [
      { department_id: "it", name: "IT Department", count: 45 },
      { department_id: "marketing", name: "Marketing Department", count: 28 },
      { department_id: "sales", name: "Sales Department", count: 22 },
      { department_id: "admin", name: "Admin Department", count: 15 },
      { department_id: "others", name: "Others", count: 18 },
    ],
  },
  expiring: [
    {
      asset_id: "1",
      name: "MacBook Pro 14-inch (M3)",
      vendor: "Apple",
      department: "IT Department",
      end_date: "2026-05-19",
      status: "expiring_soon",
    },
    {
      asset_id: "2",
      name: 'Dell Monitor 27"',
      vendor: "Dell",
      department: "IT Department",
      end_date: "2026-05-21",
      status: "expiring_soon",
    },
    {
      asset_id: "3",
      name: "Canon EOS R50",
      vendor: "Canon",
      department: "Marketing Department",
      end_date: "2026-05-30",
      status: "expiring_soon",
    },
  ],
};

/**
 * The one place the Dashboard gets its data from.
 *
 * Mock for now. When GET /dashboard/summary and /dashboard/expiring exist
 * (CLOUDAPPG5-130), replace the body with:
 *
 *   const summary = await api.get<DashboardSummary>("/dashboard/summary");
 *   const expiring = await api.get<ExpiringAssetsResponse>("/dashboard/expiring", {
 *     query: { days: 30 },
 *   });
 *   return { summary, expiring: expiring.items };
 */
export async function getDashboard(): Promise<DashboardData> {
  return MOCK_DASHBOARD;
}

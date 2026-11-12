import { api } from "@/lib/api";
import type {
  DashboardSummary,
  ExpiringAsset,
  ExpiringAssetsResponse,
} from "@/types";

/** Everything the Dashboard screen shows, in one object. */
export interface DashboardData {
  summary: DashboardSummary;
  expiring: ExpiringAsset[];
}

/** The "Expiring in 30 days" table looks 30 days ahead. */
const EXPIRING_DAYS = 30;

/**
 * The one place the Dashboard gets its data from (docs/api.md -> Dashboard).
 *
 * Call it from the browser: the deployed API address is relative ("/api"),
 * which only works there. Both requests are independent, so they go out
 * together.
 */
export async function getDashboard(): Promise<DashboardData> {
  const [summary, expiring] = await Promise.all([
    api.get<DashboardSummary>("/dashboard/summary"),
    api.get<ExpiringAssetsResponse>("/dashboard/expiring", {
      query: { days: EXPIRING_DAYS },
    }),
  ]);
  return { summary, expiring: expiring.items };
}

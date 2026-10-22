import type { Metadata } from "next";

import { getDashboard } from "@/features/dashboard/getDashboard";
import StatCard from "@/features/dashboard/StatCard";

export const metadata: Metadata = {
  title: "Dashboard",
};

/** Share of `part` in `total` as a whole percentage; 0 when there is nothing yet. */
function percent(part: number, total: number): number {
  return total === 0 ? 0 : Math.round((part / total) * 100);
}

/**
 * Dashboard. Mobile M04 (3382:141), personal M04 (3418:385), desktop D04 (3348:2).
 *
 * TODO: the name is the Figma placeholder; read it from the session once auth
 * exists (FE-04). The desktop "This Month" dropdown in D04 is left out on
 * purpose: the API has no date range yet, so it would change nothing. Add it
 * when /dashboard/summary accepts a period.
 *
 * TODO: a new workspace with no assets sees a page of zeros. Show the
 * EmptyState from FE-03 (CLOUDAPPG5-121) with an "Add your first asset" action
 * when summary.total is 0. Figma has no empty Dashboard frame yet.
 */
export default async function DashboardPage() {
  const { summary } = await getDashboard();
  const departments = summary.by_department.length;

  return (
    <main className="flex flex-1 flex-col gap-3 px-5 pt-4 pb-6 md:gap-5 md:px-8 md:pt-6 md:pb-8">
      <div className="flex flex-col gap-1 md:gap-1.5">
        <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand md:text-[30px] md:tracking-[-0.6px]">
          Welcome back, Chaiyapat
        </h1>
        <p className="text-[13px] tracking-[-0.26px] text-muted md:text-[15px] md:tracking-[-0.3px]">
          Here&apos;s what&apos;s happening with your warranties.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-5 md:gap-5">
        <StatCard
          label="Total Assets"
          value={summary.total}
          tone="total"
          caption={departments > 0 ? `Across ${departments} departments` : undefined}
        />
        <StatCard
          label="Active"
          value={summary.active}
          tone="active"
          caption={`${percent(summary.active, summary.total)}% of all assets`}
        />
        <StatCard
          label="Expiring Soon"
          value={summary.expiring_soon}
          tone="expiring"
          caption="Within 30 days"
        />
        <StatCard
          label="Expired"
          value={summary.expired}
          tone="expired"
          caption="Action required"
        />
        {/* Desktop only: mobile M04 has four cards in a 2 by 2 grid. */}
        <div className="hidden md:block">
          <StatCard
            label="No Warranty Info"
            value={summary.no_warranty}
            tone="none"
            caption="Needs review"
          />
        </div>
      </div>
    </main>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { AddAssetIcon, ChevronDownIcon } from "@/components/NavIcons";

import DepartmentBreakdown from "@/features/dashboard/DepartmentBreakdown";
import ExpiringList from "@/features/dashboard/ExpiringList";
import { percent } from "@/features/dashboard/format";
import { getDashboard } from "@/features/dashboard/getDashboard";
import StatCard from "@/features/dashboard/StatCard";
import StatusBreakdown from "@/features/dashboard/StatusBreakdown";

export const metadata: Metadata = {
  title: "Dashboard",
};

/**
 * Dashboard. Mobile M04 (3382:141), personal M04 (3418:385), desktop D04 (3348:2).
 *
 * TODO: the name and the mobile workspace card are Figma placeholders (the same
 * ones as in (app)/layout.tsx); read them from the session once auth and
 * /workspaces exist (FE-04, FE-05). The desktop "This Month" dropdown in D04 is left out on
 * purpose: the API has no date range yet, so it would change nothing. Add it
 * when /dashboard/summary accepts a period.
 *
 * TODO: a new workspace with no assets sees a page of zeros. Show the
 * EmptyState from FE-03 (CLOUDAPPG5-121) with an "Add your first asset" action
 * when summary.total is 0. Figma has no empty Dashboard frame yet.
 */
export default async function DashboardPage() {
  const { summary, expiring } = await getDashboard();
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

      {/* Mobile only: desktop shows the workspace in the sidebar. M04 3382:169. */}
      <Link
        href="/workspace"
        className="flex items-center gap-2.5 rounded-[10px] border border-border bg-surface px-3 py-2.5 md:hidden"
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand text-[10px] font-bold text-brand-foreground">
          SI
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-px">
          <span className="truncate text-[13px] font-semibold tracking-[-0.26px] text-foreground">
            SIIT Organization
          </span>
          <span className="truncate text-[10px] tracking-[-0.2px] text-muted-light">
            Organization workspace
          </span>
        </span>
        <ChevronDownIcon className="size-4 shrink-0 text-muted-light" />
      </Link>

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

      {/* Desktop D04: status bars stretch, departments sit beside them at 440px. */}
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:gap-6">
        <div className="min-w-0 md:flex-1">
          <StatusBreakdown summary={summary} />
        </div>
        <DepartmentBreakdown summary={summary} />
      </div>

      <ExpiringList items={expiring} total={summary.expiring_soon} />

      {/* Mobile only: desktop has Add Asset in the top bar. M04 3460:178. */}
      <Link
        href="/assets/new"
        className="flex h-[54px] items-center justify-center gap-2 rounded-lg bg-brand text-[14px] font-bold tracking-[-0.28px] text-brand-foreground md:hidden"
      >
        <AddAssetIcon className="size-[17px]" />
        Add Asset
      </Link>
    </main>
  );
}

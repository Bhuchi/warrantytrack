import type { Metadata } from "next";
import Link from "next/link";

import { AddAssetIcon, ChevronDownIcon } from "@/components/NavIcons";

import DashboardContent from "@/features/dashboard/DashboardContent";
import { getCurrentWorkspace } from "@/features/workspace/currentWorkspace";

export const metadata: Metadata = {
  title: "Dashboard",
};

/**
 * Dashboard. Mobile M04 (3382:141), personal M04 (3418:385), desktop D04 (3348:2).
 *
 * The mobile workspace card shows the workspace chosen on /workspace, the same
 * one as the nav panel. The numbers come from GET /dashboard/summary and /dashboard/expiring.
 *
 * TODO: the name in "Welcome back" is a Figma placeholder; read it from the
 * session once auth exists (FE-04). The desktop "This Month" dropdown in D04 is left out on
 * purpose: the API has no date range yet, so it would change nothing. Add it
 * when /dashboard/summary accepts a period.
 *
 * TODO: a new workspace with no assets sees a page of zeros. Show the
 * EmptyState from FE-03 (CLOUDAPPG5-121) with an "Add your first asset" action
 * when summary.total is 0. Figma has no empty Dashboard frame yet.
 */
export default async function DashboardPage() {
  const { workspace } = await getCurrentWorkspace();

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
          {workspace.initials}
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-px">
          <span className="truncate text-[13px] font-semibold tracking-[-0.26px] text-foreground">
            {workspace.name}
          </span>
          <span className="truncate text-[10px] tracking-[-0.2px] text-muted-light">
            {workspace.kind}
          </span>
        </span>
        <ChevronDownIcon className="size-4 shrink-0 text-muted-light" />
      </Link>

      <DashboardContent />

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

"use client";

import { useEffect, useState } from "react";

import ErrorState from "@/components/ErrorState";
import Skeleton from "@/components/Skeleton";

import DepartmentBreakdown from "./DepartmentBreakdown";
import ExpiringList from "./ExpiringList";
import { percent } from "./format";
import { type DashboardData, getDashboard } from "./getDashboard";
import StatCard from "./StatCard";
import StatusBreakdown from "./StatusBreakdown";

/**
 * The numbers, charts and expiring list. A client component because the API
 * address and the sign-in token only exist in the browser.
 */
export default function DashboardContent() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let ignore = false;
    getDashboard()
      .then((result) => {
        if (!ignore) setData(result);
      })
      .catch(() => {
        if (!ignore) setFailed(true);
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (failed) {
    return (
      <ErrorState message="We could not load the dashboard. Check your connection and refresh the page." />
    );
  }

  if (!data) {
    return (
      <div role="status" aria-label="Loading dashboard" className="flex flex-col gap-3 md:gap-5">
        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-5 md:gap-5">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24 md:h-28" />
          ))}
        </div>
        <Skeleton className="h-48" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const { summary, expiring } = data;
  const departments = summary.by_department.length;

  return (
    <>
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
    </>
  );
}

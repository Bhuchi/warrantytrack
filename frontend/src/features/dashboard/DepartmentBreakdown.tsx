import Link from "next/link";

import Card from "@/components/Card";
import type { DashboardSummary } from "@/types";

import { percent } from "./format";

interface DepartmentBreakdownProps {
  summary: DashboardSummary;
}

/**
 * "Assets by Department": one bar per department, sized by its share of all
 * assets. Desktop only (D04 3351:113); mobile M04 leaves it out.
 */
export default function DepartmentBreakdown({ summary }: DepartmentBreakdownProps) {
  // A personal workspace has no departments, so there is nothing to show.
  if (summary.by_department.length === 0) return null;

  return (
    <Card className="hidden w-[440px] shrink-0 flex-col gap-5 px-6 pt-[22px] pb-6 md:flex">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[17px] font-bold tracking-[-0.34px] text-foreground">
          Assets by Department
        </h2>
        {/* Goes to the Assets List (FE-07, CLOUDAPPG5-85) once it exists. */}
        <Link href="/assets" className="shrink-0 text-[12px] font-semibold tracking-[-0.24px] text-brand">
          View all
        </Link>
      </div>

      <ul className="flex flex-col gap-4">
        {summary.by_department.map((department) => (
          <li key={department.department_id} className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3">
              <span className="min-w-0 truncate text-[13px] font-medium tracking-[-0.26px] text-foreground">
                {department.name}
              </span>
              <span className="shrink-0 text-[14px] font-bold text-brand">{department.count}</span>
            </div>
            <div className="h-[7px] overflow-hidden rounded-full bg-track">
              <div
                className="h-full rounded-full bg-brand"
                style={{ width: `${percent(department.count, summary.total)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

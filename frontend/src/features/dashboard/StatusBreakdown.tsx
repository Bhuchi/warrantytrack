import Card from "@/components/Card";
import type { DashboardSummary } from "@/types";

import { percent } from "./format";

interface StatusBreakdownProps {
  summary: DashboardSummary;
}

/**
 * "Warranties by Status": one bar per status, sized by its share of all
 * assets. Mobile M04 (3382:214), desktop D04 (3351:66). Desktop adds the
 * subtitle and the percentage next to each count.
 */
export default function StatusBreakdown({ summary }: StatusBreakdownProps) {
  const rows = [
    { label: "Active", count: summary.active, color: "bg-status-active" },
    { label: "Expiring Soon", count: summary.expiring_soon, color: "bg-status-expiring" },
    { label: "Expired", count: summary.expired, color: "bg-status-expired" },
    { label: "No Warranty Info", count: summary.no_warranty, color: "bg-status-none" },
  ];

  return (
    <Card className="flex flex-col gap-3 px-[18px] py-3.5 md:gap-5 md:px-6 md:pt-[22px] md:pb-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-[3px]">
          <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground md:text-[17px] md:tracking-[-0.34px]">
            Warranties by Status
          </h2>
          <p className="hidden text-[12px] tracking-[-0.24px] text-muted-light md:block">
            Distribution across all registered assets
          </p>
        </div>
        <p className="shrink-0 text-[11px] font-semibold tracking-[-0.22px] text-muted-light md:text-[12px] md:tracking-[-0.24px]">
          {summary.total} total
        </p>
      </div>

      <ul className="flex flex-col gap-[11px] md:gap-[18px]">
        {rows.map((row) => {
          const share = percent(row.count, summary.total);

          return (
            <li key={row.label} className="flex flex-col gap-[7px] md:gap-[9px]">
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-[13px] font-medium tracking-[-0.26px] text-foreground md:gap-[9px] md:text-[14px] md:tracking-[-0.28px]">
                  <span className={`size-[9px] shrink-0 rounded-full md:size-2.5 ${row.color}`} />
                  {row.label}
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-[13px] font-bold text-foreground md:text-[15px]">
                    {row.count}
                  </span>
                  <span className="hidden text-[12px] tracking-[-0.24px] text-muted-light md:inline">
                    {share}%
                  </span>
                </span>
              </div>

              <div className="h-1.5 overflow-hidden rounded-full bg-track md:h-[7px]">
                <div className={`h-full rounded-full ${row.color}`} style={{ width: `${share}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

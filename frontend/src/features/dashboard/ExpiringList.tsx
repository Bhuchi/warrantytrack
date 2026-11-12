import Image from "next/image";
import Link from "next/link";

import Card from "@/components/Card";
import StatusBadge from "@/components/StatusBadge";
import type { ExpiringAsset } from "@/types";

import { formatDate } from "./format";

interface ExpiringListProps {
  items: ExpiringAsset[];
  /** How many assets expire in the next 30 days, for the desktop "8 assets" pill. */
  total: number;
}

/**
 * "Expiring in 30 days". Mobile is a short list (M04 3382:251), desktop is a
 * table (D04 3351:149). Both are rendered and the screen width picks one, so
 * they share the same data. Row counts match the frames: 2 on mobile, 3 on
 * desktop; "View all" leads to the rest.
 */
export default function ExpiringList({ items, total }: ExpiringListProps) {
  // TODO: show an EmptyState (FE-03) instead of hiding the section.
  if (items.length === 0) return null;

  return (
    <>
      {/* Mobile list */}
      <Card className="flex flex-col gap-[11px] px-[18px] py-3.5 md:hidden">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[16px] font-bold tracking-[-0.32px] text-foreground">
            Expiring in 30 days
          </h2>
          {/* Padding enlarges the tap area to 30px; the negative margin keeps the row height. */}
          <Link href="/assets" className="-my-1.5 shrink-0 py-1.5 text-[12px] font-semibold tracking-[-0.24px] text-brand">
            View all
          </Link>
        </div>

        <ul className="flex flex-col gap-[11px]">
          {items.slice(0, 2).map((item) => (
            <li key={item.asset_id}>
              <Link
                href={`/assets/${item.asset_id}`}
                className="flex items-center gap-3 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                <div className="flex size-9 shrink-0 items-center justify-center rounded-[9px] bg-brand-subtle">
                  <Image src="/icons/device-laptop.svg" alt="" width={17} height={17} />
                </div>
                <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  <p className="truncate text-[13px] font-semibold tracking-[-0.26px] text-foreground">
                    {item.name}
                  </p>
                  <p className="text-[11px] tracking-[-0.22px] text-muted-light">
                    Expires {formatDate(item.end_date)}
                  </p>
                </div>
                <StatusBadge status={item.status} />
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      {/* Desktop table */}
      <Card className="hidden flex-col gap-5 px-6 pt-[22px] pb-6 md:flex">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col gap-[3px]">
            <h2 className="text-[17px] font-bold tracking-[-0.34px] text-foreground">
              Expiring in the next 30 days
            </h2>
            <p className="text-[12px] tracking-[-0.24px] text-muted-light">
              Renew or file a claim before these warranties lapse
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-brand-subtle px-2.5 py-[5px] text-[11px] font-semibold tracking-[-0.22px] text-brand">
            {total} assets
          </span>
        </div>

        <table className="w-full table-fixed text-left">
          <thead className="border-b border-border">
            <tr className="text-[11px] font-semibold tracking-[0.44px] text-muted-light uppercase">
              <th className="w-[36%] pb-3 font-semibold">Asset</th>
              <th className="w-[16%] pb-3 font-semibold">Vendor</th>
              <th className="w-[21%] pb-3 font-semibold">Department</th>
              <th className="w-[14%] pb-3 font-semibold">Expiry date</th>
              <th className="pb-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-[14px] font-medium tracking-[-0.28px] text-foreground">
            {items.slice(0, 3).map((item) => (
              <tr key={item.asset_id}>
                <td className="truncate py-3.5 pr-4">
                  <Link
                    href={`/assets/${item.asset_id}`}
                    className="hover:text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {item.name}
                  </Link>
                </td>
                <td className="truncate py-3.5 pr-4">{item.vendor ?? "—"}</td>
                <td className="truncate py-3.5 pr-4">{item.department ?? "—"}</td>
                <td className="py-3.5 pr-4">{formatDate(item.end_date)}</td>
                <td className="py-3.5">
                  <StatusBadge status={item.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}

import Image from "next/image";

import Card from "@/components/Card";

type StatTone = "total" | "active" | "expiring" | "expired" | "none";

interface StatCardProps {
  label: string;
  value: number;
  /** Picks the icon and colours. */
  tone: StatTone;
  /** Small grey line under the number, e.g. "Within 30 days". Desktop only, as in D04. */
  caption?: string;
}

/** Icon, icon background and number colour for each tone, from D04 (3351:11). */
const toneStyles: Record<StatTone, { icon: string; iconBox: string; number: string }> = {
  total: { icon: "/icons/stat-total.svg", iconBox: "bg-brand-subtle", number: "text-brand" },
  active: { icon: "/icons/stat-active.svg", iconBox: "bg-status-active-soft", number: "text-status-active" },
  expiring: { icon: "/icons/stat-expiring.svg", iconBox: "bg-status-expiring-soft", number: "text-status-expiring" },
  expired: { icon: "/icons/stat-expired.svg", iconBox: "bg-status-expired-soft", number: "text-status-expired" },
  none: { icon: "/icons/stat-none.svg", iconBox: "bg-status-none-soft", number: "text-status-none" },
};

/**
 * One number on the Dashboard, e.g. "Total Assets 128".
 * Mobile M04 (3382:179), desktop D04 (3351:12).
 */
export default function StatCard({ label, value, tone, caption }: StatCardProps) {
  const { icon, iconBox, number } = toneStyles[tone];

  return (
    <Card className="flex flex-col gap-2 px-3.5 py-[13px] md:gap-3 md:rounded-[14px] md:px-5 md:py-[18px]">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold tracking-[-0.22px] text-muted md:text-[12px] md:tracking-[-0.24px]">
          {label}
        </p>
        <div
          className={`flex size-7 shrink-0 items-center justify-center rounded-lg md:size-[34px] md:rounded-[9px] ${iconBox}`}
        >
          <Image src={icon} alt="" width={17} height={17} className="size-3.5 md:size-[17px]" />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <p className={`text-[27px] font-bold tracking-[-0.81px] md:text-[34px] md:tracking-[-1.02px] ${number}`}>
          {value}
        </p>
        {caption && (
          <p className="hidden text-[11px] tracking-[-0.22px] text-muted-light md:block">
            {caption}
          </p>
        )}
      </div>
    </Card>
  );
}

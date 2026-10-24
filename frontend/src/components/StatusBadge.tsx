import type { WarrantyStatus } from "@/types";

interface StatusBadgeProps {
  status: WarrantyStatus;
}

/**
 * Label and colours for each status. The keys are the backend's values
 * (docs/api.md, "Warranty status"); `unknown` means the asset has no warranty.
 * Active, Expiring and Expired come from M05 Assets List (3382:382 / 3382:407 /
 * 3382:432). Figma has no "No warranty" badge yet, so it takes the purple from
 * the Dashboard status bar (3382:250).
 */
const statusStyles: Record<WarrantyStatus, { label: string; classes: string }> = {
  active: { label: "Active", classes: "bg-status-active-soft text-status-active" },
  expiring_soon: { label: "Expiring", classes: "bg-status-expiring-soft text-status-expiring" },
  expired: { label: "Expired", classes: "bg-status-expired-soft text-status-expired" },
  unknown: { label: "No warranty", classes: "bg-status-none-soft text-status-none" },
};

/** Small coloured pill showing a warranty's status. */
export default function StatusBadge({ status }: StatusBadgeProps) {
  const { label, classes } = statusStyles[status];

  return (
    <span
      className={`inline-flex items-center rounded-full px-[9px] py-1 text-[10px] font-semibold tracking-[-0.2px] whitespace-nowrap ${classes}`}
    >
      {label}
    </span>
  );
}

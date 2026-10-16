/** The four states a warranty can be in. Move to src/types/ once the /assets API defines it. */
export type WarrantyStatus = "active" | "expiring" | "expired" | "none";

interface StatusBadgeProps {
  status: WarrantyStatus;
}

/**
 * Label and colours for each status. Active, Expiring and Expired come from
 * M05 Assets List (3382:382 / 3382:407 / 3382:432). Figma has no "No warranty"
 * badge yet, so that one reuses the existing grey tokens.
 */
const statusStyles: Record<WarrantyStatus, { label: string; classes: string }> = {
  active: { label: "Active", classes: "bg-status-active-soft text-status-active" },
  expiring: { label: "Expiring", classes: "bg-status-expiring-soft text-status-expiring" },
  expired: { label: "Expired", classes: "bg-status-expired-soft text-status-expired" },
  none: { label: "No warranty", classes: "bg-canvas text-muted" },
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

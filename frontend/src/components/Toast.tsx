import Image from "next/image";

type ToastTone = "success" | "info" | "error";

interface ToastProps {
  /** Picks the icon and its tinted background. */
  tone: ToastTone;
  title: string;
  /** One line under the title; cut off with "…" if too long. */
  message?: string;
  /** Optional link-style button, e.g. "View", "Review" or "Retry". */
  action?: { label: string; onClick: () => void };
  /** Called by the × button. */
  onClose: () => void;
}

/** Icon and icon background for each tone, from N02b Toast variants (3488:286). */
const toneStyles: Record<ToastTone, { icon: string; iconBox: string }> = {
  success: { icon: "/icons/toast-success.svg", iconBox: "bg-status-active-soft" },
  info: { icon: "/icons/toast-info.svg", iconBox: "bg-brand-subtle" },
  error: { icon: "/icons/toast-error.svg", iconBox: "bg-status-expired-soft" },
};

/**
 * One toast card. It does not position itself or disappear on a timer: the
 * screen showing it decides where it sits and when it goes.
 */
export default function Toast({ tone, title, message, action, onClose }: ToastProps) {
  const { icon, iconBox } = toneStyles[tone];

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className="flex w-full items-center gap-3 rounded-[14px] border border-border bg-surface py-[13px] pr-3 pl-3.5 shadow-toast"
    >
      <div
        className={`flex size-9 shrink-0 items-center justify-center rounded-[10px] ${iconBox}`}
      >
        <Image src={icon} alt="" width={18} height={18} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="truncate text-[14px] font-bold tracking-[-0.28px] text-foreground">
          {title}
        </p>
        {message && (
          <p className="truncate text-[12px] tracking-[-0.24px] text-muted">
            {message}
          </p>
        )}
      </div>

      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="shrink-0 text-[13px] font-semibold tracking-[-0.26px] text-brand"
        >
          {action.label}
        </button>
      )}

      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss"
        className="flex size-6 shrink-0 items-center justify-center"
      >
        <Image src="/icons/close-small.svg" alt="" width={14} height={14} />
      </button>
    </div>
  );
}
